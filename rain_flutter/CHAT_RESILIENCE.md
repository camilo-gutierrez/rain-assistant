# Chat Resilience — Flutter Session Persistence

## Problema original

Cuando el usuario cerraba la app (accidentalmente o no), al volver:
1. Se mostraba el **file browser** en vez del chat
2. Todos los **agents y mensajes se perdian** (solo existian en RAM)
3. El **auto-save creaba duplicados** en el historial (ID con timestamp = nueva entrada cada vez)
4. La **reanudacion de sesion estaba rota** (intentaba resumir agents que ya no existian en memoria)

## Solucion implementada: "Persistent Session Recovery"

### Estrategia

Persistencia ligera en **SharedPreferences** (metadata de agents) + recovery de mensajes desde el **server history** (que ya existia). Sin nuevas dependencias.

### Diagrama de flujo

```
App cerrada → Reabre → _init()
  ├── Carga settings, auth (ya existia)
  ├── restoreSession() → SharedPreferences → agents {id, label, cwd, sessionId}
  │   └── _hasRestoredSession = true
  └── _connectWebSocket()
       └── WS connected
            ├── Si _hasRestoredSession:
            │   ├── _resumeRestoredSession()
            │   │   ├── send set_cwd + session_id por cada agent
            │   │   └── _restoreMessagesFromHistory(agentId)
            │   │       └── GET /history/conv_{agentId}_active → setMessages()
            │   └── → pantalla Chat (skip file browser)
            └── Si no:
                └── → pantalla FileBrowser (flujo normal)
```

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `lib/providers/agent_provider.dart` | +`persistSession()`, `restoreSession()`, `clearSession()` |
| `lib/main.dart` | Skip file browser si hay sesion restaurada, auto-load mensajes, auto-save con ID estable |
| `lib/services/lifecycle_observer.dart` | Persiste sesion al ir a background (paused/detached) |

### Cambios clave

#### 1. Persistencia de metadata de agents (`agent_provider.dart`)
- `persistSession()` — Guarda `{id, label, cwd, sessionId}` por agent en SharedPreferences
- `restoreSession()` — Restaura agents desde SharedPreferences (sin mensajes, son pesados)
- `clearSession()` — Limpia al expirar sesion

#### 2. Skip file browser (`main.dart`)
- En `_init()`: intenta `restoreSession()` antes de conectar WS
- En `_connectWebSocket()`: si `_hasRestoredSession`, va directo a Chat
- En `api_key_loaded`: misma logica (caso donde la API key llega despues)

#### 3. Auto-save con ID estable (`main.dart`)
- **Antes**: `'id': 'conv_${agent.id}_$now'` → nueva entrada por cada result → duplicados
- **Ahora**: `'id': 'conv_${agent.id}_active'` → el server hace upsert → UNA entrada por agent
- El manual save (boton "Guardar" en History) sigue creando snapshot con timestamp

#### 4. Restauracion de mensajes (`main.dart`)
- `_restoreMessagesFromHistory(agentId)` → `GET /history/conv_{agentId}_active`
- Carga mensajes en el agent sin que el usuario tenga que ir a History

#### 5. Persist on background (`lifecycle_observer.dart`)
- Cuando la app va a `paused` o `detached`, persiste la sesion
- Tambien se persiste en: `status` (cwd recibido), `result` (session_id), y despues de auto-save exitoso

#### 6. Limpieza en unauthorized
- Al expirar token: `clearSession()` + `_hasRestoredSession = false`
- Evita restaurar datos stale de una sesion anterior

### Que NO se persiste localmente (y por que)
- **Mensajes**: Son pesados y ya estan en el server via auto-save. Se restauran via HTTP.
- **Estado de streaming**: Efimero por naturaleza, no tiene sentido persistir texto parcial.
- **Estado de procesamiento**: Se resetea en reconnect.

### Comparacion con Web

| Aspecto | Web | Flutter (despues del fix) |
|---|---|---|
| Mensajes en memoria | Zustand store | Riverpod agent.messages |
| Persistencia local | No (solo localStorage para settings) | SharedPreferences para metadata |
| Auto-save | `conv_{agentId}_active` (estable) | `conv_{agentId}_active` (estable) |
| Recovery despues de refresh/reopen | Manual (History sidebar) | Automatico (restore + auto-load) |
| WS reconnect | Auto con backoff | Auto con backoff |
| Session resume | Funciona (agents sobreviven en memoria) | Funciona (agents restaurados de SP) |

**Nota**: Web no tiene el problema de "app kill" porque el tab del browser no mata el proceso de la misma forma. El reconnect de WS preserva los agents en memoria. Flutter si tenia este problema, ahora resuelto.

### Alternativas consideradas y descartadas

1. **Hive/SQLite local para mensajes**: Requiere nueva dependencia, sincronizacion bidireccional compleja con el server. Overkill dado que el server ya guarda conversaciones.

2. **Persistir mensajes en SharedPreferences**: SharedPreferences tiene limite de ~1MB y los mensajes pueden ser grandes (tool results, screenshots). No escalable.

3. **Service Worker / background fetch**: Solo aplica para web, no resuelve Flutter.

La solucion elegida (metadata local + mensajes en server) es la mas simple, no requiere dependencias nuevas, y aprovecha la infraestructura existente.
