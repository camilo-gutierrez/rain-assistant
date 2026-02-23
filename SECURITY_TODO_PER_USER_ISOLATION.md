# Per-User Data Isolation — Implementation Plan

> **Status:** Pendiente. Este documento es la guía para implementar aislamiento de datos por usuario.
> **Prioridad:** HIGH — Necesario para despliegues multi-usuario (Telegram bot, web compartido).
> **Esfuerzo estimado:** Grande (~15 archivos, migraciones de DB, refactorización de storage).

---

## Problema Actual

Todos los datos del usuario se almacenan de forma **global y compartida**:
- `~/.rain-assistant/memories.json` — Memorias de TODOS los usuarios
- `~/.rain-assistant/active_ego.txt` — Un solo alter ego activo global
- `document_chunks` table en SQLite — Sin columna `user_id`
- `scheduled_tasks` table — Sin columna `user_id`

Si Alice y Bob usan el mismo servidor (ej. vía Telegram), Bob puede ver las memorias de Alice.

---

## Estrategia

1. **`user_id` como parámetro** en todas las funciones de storage (default: `"default"`)
2. **Migraciones automáticas** al arrancar (no-destructivas, verifican si ya se aplicaron)
3. **Backward compatible** — instalaciones existentes migran datos a `user_id="default"`
4. **Estructura de directorios por usuario:**

```
~/.rain-assistant/
  users/
    default/
      memories.json
      active_ego.txt
      alter_egos/
    alice/
      memories.json
      active_ego.txt
      alter_egos/
```

---

## Archivos a Modificar (orden sugerido)

### Fase 1: Schema + Storage Layer

#### 1. `database.py`
- Agregar columna `user_id TEXT DEFAULT 'default'` a `active_sessions`
- Crear tabla `users` (user_id, created_at, last_login, metadata)
- Agregar función `_get_user_id_from_token(token_hash) -> str`
- Crear índice `idx_sessions_user_id`

#### 2. `memories/storage.py`
- Agregar `user_id: str = "default"` a: `load_memories()`, `add_memory()`, `search_memories()`, `remove_memory()`, `clear_memories()`, `reindex_memories()`
- Ruta por usuario: `CONFIG_DIR / "users" / user_id / "memories.json"`
- Función de migración: `migrate_shared_to_user_isolated()`

#### 3. `memories/embeddings.py`
- Agregar `user_id` a: `store_embedding()`, `remove_embedding()`, `clear_embeddings()`, `semantic_search()`
- DB por usuario: `CONFIG_DIR / "users" / user_id / "embeddings.db"`

#### 4. `documents/storage.py`
- `ALTER TABLE document_chunks ADD COLUMN user_id TEXT DEFAULT 'default'`
- Agregar `user_id` a: `ingest_document()`, `list_documents()`, `remove_document()`, `get_document_chunks()`, `search_documents()`
- Agregar `WHERE user_id = ?` a todas las queries
- Función de migración: `migrate_legacy_documents()`

#### 5. `alter_egos/storage.py`
- Per-user `active_ego.txt`: `CONFIG_DIR / "users" / user_id / "active_ego.txt"`
- Per-user ego files: `CONFIG_DIR / "users" / user_id / "alter_egos/"`
- Agregar `user_id` a: `load_all_egos()`, `load_ego()`, `save_ego()`, `delete_ego()`, `get_active_ego_id()`, `set_active_ego_id()`
- `ensure_builtin_egos(user_id)` — copia egos built-in al directorio del usuario
- Función de migración: `migrate_shared_ego_to_user_isolated()`

#### 6. `scheduled_tasks/storage.py`
- `ALTER TABLE scheduled_tasks ADD COLUMN user_id TEXT DEFAULT 'default'`
- Agregar `user_id` a: `add_task()`, `list_tasks()`, `get_task()`, `update_task()`, `delete_task()`, `get_pending_tasks()`
- Función de migración: `migrate_legacy_scheduled_tasks()`

### Fase 2: Integración

#### 7. `prompt_composer.py`
- Agregar `user_id: str = "default"` a `compose_system_prompt()`
- Pasar `user_id` a `load_memories()`, `search_memories()`, `search_documents()`, `get_active_ego_id()`, `load_ego()`

#### 8. `tools/executor.py`
- Agregar `user_id: str = "default"` a `ToolExecutor.__init__()`
- Inyectar `_user_id` en los argumentos de handlers que lo necesiten:
  ```python
  if tool_name in ("manage_memories", "manage_alter_egos", "manage_documents", "manage_scheduled_tasks"):
      arguments = {**arguments, "_user_id": self.user_id}
  ```

#### 9. Meta-tools (4 archivos)
- `memories/meta_tool.py` — Extraer `_user_id` de args, pasar a funciones de storage
- `documents/meta_tool.py` — Ídem
- `alter_egos/meta_tool.py` — Ídem
- `scheduled_tasks/meta_tool.py` — Ídem

#### 10. `server.py`
- En `websocket_endpoint`: extraer `user_id` del token via `_get_user_id_from_token()`
- Pasar `user_id` a `ToolExecutor()` y `compose_system_prompt()`
- Llamar funciones de migración al arrancar

#### 11. `telegram_bot.py`
- Usar `str(telegram_user_id)` como `user_id`
- Pasar a `compose_system_prompt()` e inicialización de provider
- Pasar a tool handlers

### Fase 3: Testing

- [ ] Tests unitarios para cada storage con múltiples user_ids
- [ ] Tests de migración (datos legacy → user=default)
- [ ] Tests de integración WebSocket con aislamiento
- [ ] Tests de Telegram bot con múltiples usuarios simultáneos
- [ ] Verificar que `user_id="default"` funciona igual que antes (backward compat)

---

## Decisiones de Diseño

| Decisión | Resolución |
|----------|------------|
| Formato de user_id | `str` — flexible, compatible con "default", Telegram IDs, UUIDs |
| Egos built-in | Copia per-user (más simple, sin referencias cruzadas) |
| Un PIN o multi-PIN | Mantener un PIN por ahora, derivar user_id de device_id o config |
| Pasar user_id | Explícito como parámetro (no magia de contexto) |

---

## Notas de Migración

- Todas las migraciones son **idempotentes** (verifican con `PRAGMA table_info`)
- Se ejecutan automáticamente al arrancar el servidor
- Datos existentes se asignan a `user_id = "default"`
- El archivo legacy `memories.json` se mueve a `users/default/memories.json`
- El archivo legacy `active_ego.txt` se mueve a `users/default/active_ego.txt`
- No se borran archivos legacy hasta confirmar migración exitosa
