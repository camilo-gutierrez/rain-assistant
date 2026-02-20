# Rain Assistant — Auditoria Completa & Comparacion con Open WebUI

> Fecha: 2026-02-18 (auditoria inicial)
> Actualizado: 2026-02-18 (ronda 3: browser pool, scheduler ai_prompt, encryption keyring)

---

## 1. Estado Actual de Rain Assistant

### Numeros Reales del Proyecto

| Metrica | Valor |
|---|---|
| **LOC Backend Python** | ~14,643 |
| **LOC Frontend Next.js** | ~6,600 |
| **LOC Flutter App** | ~8,500 |
| **LOC Tests (Python)** | ~2,469 |
| **LOC Tests (Flutter)** | ~1,500 |
| **Total LOC** | **~33,700** |
| **Archivos Python** | 63 modulos |
| **Archivos TS/TSX** | 56 archivos |
| **Archivos Dart** | 38 archivos |
| **Archivos Test** | 21 archivos (10 pytest + 11 Flutter) |
| **Total Tests** | ~579 (374 pytest + 205 Flutter) |

### Madurez General

| Componente | Madurez | Score | Notas |
|---|---|---|---|
| **Backend (Python/FastAPI)** | 93% | 9/10 | 14,643 LOC, bien arquitectado, async, sandboxed |
| **Frontend Web (Next.js 16)** | 88% | 8.5/10 | 6,600 LOC, 56 archivos, hooks refactorizados |
| **Flutter App** | 84% | 8/10 | 8,500 LOC, 205 tests, Material 3, Riverpod |
| **Telegram Bot** | 90% | 8.5/10 | 687 LOC, voz, per-user sessions |
| **Plugin System** | 87% | 8.5/10 | YAML, 3 tipos, sandboxed, meta-tool chat |
| **Tests** | 75% | 7.5/10 | 579 tests totales, falta WebSocket/scheduler |
| **Seguridad** | 80% | 8/10 | PIN, permisos, sandbox, rate limiting auth |
| **DevOps** | 60% | 6/10 | Sin Docker, sin CI/CD, sin health checks |
| **Score General** | **83%** | **8/10** | |

---

### Backend — Componentes Detallados

| Componente | Archivo(s) | LOC | Estado |
|---|---|---|---|
| Server FastAPI | `server.py` | 2,767 | WebSocket, auth, rate limiting, CORS, security headers, failover, scheduler |
| Provider Claude | `providers/claude_provider.py` | 139 | Claude SDK nativo, streaming, session resumption, MCP, computer use |
| Provider OpenAI | `providers/openai_provider.py` | 222 | Agentic loop (50 iter), function calling, streaming, cost tracking |
| Provider Gemini | `providers/gemini_provider.py` | 203 | Async nativo (`send_message_async`), function calling, agentic loop |
| Provider Ollama | `providers/ollama_provider.py` | 259 | Streaming, tool calling con fallback graceful, costo $0, 8 modelos |
| Base Provider | `providers/base.py` | 79 | Abstract base, NormalizedEvent (8 tipos) |
| Factory + Failover | `providers/__init__.py` | ~50 | `get_provider()` + failover chain automatico |
| Tools Core | `tools/definitions.py` | 394 | 14 built-in tools (OpenAI format + Gemini converter) |
| Tools Executor | `tools/executor.py` | 138 | Permission checking, plugin handler loading |
| File Operations | `tools/file_ops.py` | 114 | read, write, edit, list_directory (path traversal protection) |
| Browser Operations | `tools/browser_ops.py` | 274 | Playwright: navigate, screenshot, click, type, extract, scroll, close |
| Bash/Shell | `tools/` | 64 | 300s timeout, 30K output limit, cross-platform |
| Plugin Schema | `plugins/schema.py` | 135 | Dataclass models, validation, 3 tipos ejecucion |
| Plugin Loader | `plugins/loader.py` | 133 | YAML parsing, enable/disable, env vars |
| Plugin Executor | `plugins/executor.py` | 246 | Sandboxed: env restringido, cwd protegido, memory limit 512MB |
| Plugin Meta-tool | `plugins/meta_tool.py` | 203 | create, list, enable, disable, delete, set_env |
| Permisos | `permission_classifier.py` | 199 | GREEN/YELLOW/RED/COMPUTER, 28 patrones peligrosos |
| Database | `database.py` | 578 | SQLite WAL, Fernet encryption, 6 tablas, indexes |
| Rate Limiter | `rate_limiter.py` | ~100 | 6 categorias (incl. AUTH 10/min), sliding window 60s |
| Transcripcion | `transcriber.py` | ~80 | faster-whisper, CPU int8, VAD, beam_size=5 |
| TTS | `synthesizer.py` | ~60 | edge-tts (gratis), 4 voces, preprocess markdown |
| Alter Egos | `alter_egos/storage.py` | ~120 | 5 built-in + custom, JSON storage |
| Memories Storage | `memories/storage.py` | 262 | JSON + semantic search + fallback substring |
| Memories Embeddings | `memories/embeddings.py` | 301 | sentence-transformers, SQLite, temporal decay |
| Prompt Composer | `prompt_composer.py` | 82 | ego.system_prompt + top 10 memories (semantic) |
| Scheduled Tasks | `scheduled_tasks/` | 305 | SQLite, croniter, 3 tipos, meta-tool, background loop |
| Computer Use | `computer_use.py` | ~500 | Screenshots, clicks, typing, scroll, 10+ acciones |
| Telegram Bot | `telegram_bot.py` | 687 | aiogram 3, voz, inline keyboards, per-user sessions |

### Frontend Web — Estructura Actual

```
frontend/src/ (~6,600 LOC, 56 archivos)
├── app/          layout.tsx, page.tsx, globals.css (2 temas, 244 LOC)
├── stores/       8 Zustand stores:
│   ├── useAgentStore.ts (577 LOC) — multi-agente, messages, streaming, computer use
│   ├── useConnectionStore.ts (138 LOC) — WebSocket, auth, reconnect
│   ├── useSettingsStore.ts (84 LOC) — tema, idioma, TTS, provider (persisted v4)
│   ├── useUIStore.ts (70 LOC) — panels, drawers, sidebar
│   ├── useToastStore.ts (50 LOC) — notificaciones auto-dismiss
│   ├── useMetricsStore.ts (42 LOC) — rate limits, usage (cached 1min)
│   ├── useHistoryStore.ts (27 LOC) — conversaciones
│   └── useRecorderStore.ts (24 LOC) — estado grabacion
├── hooks/        10 hooks (refactorizados):
│   ├── useWebSocket.ts (247 LOC) — router principal, delegacion a sub-hooks
│   ├── useToolMessages.ts (48 LOC) — tool_use, tool_result
│   ├── usePermissionMessages.ts (30 LOC) — permission_request
│   ├── useComputerUseMessages.ts (60 LOC) — screenshots, actions, mode
│   ├── useSubAgentMessages.ts (60 LOC) — spawn, completion
│   ├── useAudioRecorder.ts (190 LOC) — lazy mic, echo cancel, auto-release
│   ├── useHistory.ts (182 LOC) — save/load/delete conversaciones
│   ├── useNotifications.ts (140 LOC) — browser notifications, PWA-ready
│   ├── useTTS.ts (112 LOC) — reproduccion, blob cleanup
│   └── useTranslation.ts (18 LOC) — i18n wrapper
├── components/
│   ├── chat/     MessageBubble, ChatInput, ChatMessages, ToolUseBlock, ToolResultBlock,
│   │             PermissionRequestBlock, RecordButton, InterruptButton, SubAgentIndicator
│   ├── panels/   PinPanel, ApiKeyPanel, FileBrowserPanel, ChatPanel, MetricsPanel,
│   │             SettingsPanel, MemoriesPanel, AlterEgosPanel, MarketplacePanel (9 panels)
│   ├── computer-use/  ScreenshotViewer, ComputerActionBubble, ModeToggle,
│   │                  EmergencyStopButton, ComputerUseToolbar
│   └── (otros)   StatusBar, TabBar, SidebarNav, HistorySidebar, MobileBottomNav,
│                  DrawerOverlay, ModelSwitcher, EgoSwitcher, McpToolsSection,
│                  SecurityBanner, Toast, RateLimitBadge
├── lib/
│   ├── types.ts (447 LOC) — tipos completos, discriminated unions
│   ├── api.ts (349 LOC) — fetchWithRetry, rate limit handling
│   ├── translations.ts (464 LOC) — en/es, ~60+ keys
│   ├── historyUtils.ts (184 LOC) — auto-save, loadHistoryForAgent
│   └── constants.ts (25 LOC) — API/WS URLs, secure context
```

### Flutter App — Estado por Fase

| Fase | Descripcion | Estado | Tests |
|---|---|---|---|
| 1. Scaffold + Auth | Server URL, PIN, token storage, HTTP client | COMPLETA | 8 tests |
| 2. WebSocket | Conexion, heartbeat, reconnect, close codes | COMPLETA | — |
| 3. Chat Core | Messages, markdown, streaming, tools | COMPLETA | 45 tests |
| 4. Audio | Record, upload, TTS, auto-play | COMPLETA | — |
| 5. Permisos | YELLOW/RED dialogs, countdown, PIN | COMPLETA | incluido en messages |
| 6. Multi-Agent | Tabs, create/destroy, unread badges | COMPLETA | 35 tests |
| 7. Funcionalidades Sec. | File browser, settings, metrics, history | COMPLETA | 46 tests |
| 8. Computer Use | Mode switch, screenshots, actions | 80% | incluido en messages |
| 9. Polish | Animaciones, temas, i18n, toasts | COMPLETA | 34 tests |
| 10. Testing | Unit + widget tests | NUEVA | 205 tests total |

**Flutter test breakdown**:

| Archivo Test | Tests | Cobertura |
|---|---|---|
| `test/models/message_test.dart` | ~45 | 8 tipos de mensaje, JSON roundtrip, enums |
| `test/providers/agent_provider_test.dart` | ~35 | CRUD agentes, streaming, permisos, computer use |
| `test/l10n/translations_test.dart` | ~20 | 120+ keys en/es, params, meses, dias |
| `test/providers/settings_provider_test.dart` | ~18 | Defaults, toggles, provider switch con model reset |
| `test/models/rate_limits_test.dart` | ~16 | Calculos porcentaje, division by zero, hasData |
| `test/widget_test.dart` | ~14 | Theme Material 3, Riverpod integration |
| `test/models/provider_info_test.dart` | ~12 | Enum values, modelos por provider, formatModelName |
| `test/models/metrics_test.dart` | ~12 | MetricsTotals, MetricsData, time series |
| `test/models/auth_test.dart` | ~8 | AuthResponse, success computed, locked state |
| `test/models/agent_test.dart` | ~20 | Agent creation, enums, DisplayInfo |
| `test/models/conversation_test.dart` | ~5 | ConversationMeta, JSON, defaults |

---

## 2. Open WebUI — Datos Verificados (Feb 2026)

> **NOTA**: En auditorias anteriores se referencio "OpenClaw" — la comparacion real es con
> **Open WebUI** (github.com/open-webui/open-webui), el competidor principal en el espacio
> de interfaces AI open-source.

### Datos GitHub (verificados via API, 2026-02-18)

| Metrica | Valor |
|---|---|
| **Stars** | 124,286 |
| **Forks** | 17,564 |
| **Contributors** | 391 (1 dominante: tjbck con 10,740 contributions) |
| **Open Issues** | 268 |
| **Closed Issues** | 7,457 |
| **Merged PRs** | 3,188 |
| **Repo Size** | ~327 MB |
| **Lenguaje** | Python 34%, Svelte 31%, JavaScript 27% |
| **Licencia** | Custom (NO MIT/Apache — restrictiva, enterprise de pago) |
| **Ultimo push** | 2026-02-18 (activo diariamente) |
| **Releases** | 50+ desde enero 2025 (release cadence agresivo) |

### Arquitectura Open WebUI

- **Backend**: Python 3.11+ con FastAPI (v0.128.5)
- **Frontend**: SvelteKit (v2.5.27+) — NO React/Next.js
- **ORM**: SQLAlchemy v2 + Alembic migrations + Peewee (legacy)
- **Real-time**: Socket.IO (python-socketio)
- **RAG**: LangChain v1.2.9 + ChromaDB v1.4.1 (default)
- **Embeddings**: Sentence Transformers v5.2.2
- **MCP**: MCP SDK v1.26.0
- **Deployment**: Docker (primary), Kubernetes (Helm charts), pip install

### Features Open WebUI

**Proveedores IA**: Ollama (nativo, deep integration), OpenAI-compatible (OpenAI, LMStudio, GroqCloud, Mistral, OpenRouter, etc.), Open Responses protocol (experimental v0.8.0)

**RAG (Retrieval Augmented Generation)**:
- 11+ vector databases: ChromaDB, PGVector, Qdrant, Milvus, Elasticsearch, OpenSearch, Pinecone, S3Vector, Oracle 23ai, Weaviate, openGauss
- 15+ web search providers: SearXNG, Google PSE, Brave, Kagi, Tavily, Perplexity, DuckDuckGo, Bing, Jina, Exa, Yandex
- Content extraction: Tika, Docling, Document Intelligence, Mistral OCR

**Enterprise**:
- Auth: LDAP/Active Directory, SCIM 2.0, OAuth/SSO, trusted headers
- RBAC: roles, user groups, per-resource sharing
- Cloud: Google Drive, OneDrive/SharePoint file picking
- Observability: OpenTelemetry (traces, metrics, logs)
- Storage: S3, GCS, Azure Blob
- Database: SQLite o PostgreSQL
- Redis sessions para multi-worker

**Extensibilidad**:
- Python Tools/Functions en editor web (Valves system)
- Pipelines (microservicio separado, 2,286 stars)
- MCP + OpenAPI tool servers
- mcpo (MCP-to-OpenAPI proxy, 3,980 stars)
- Community marketplace en openwebui.com

**Lo que NO tiene (verificado)**:
- NO tiene app movil nativa (solo PWA)
- NO tiene smart home integration
- NO tiene email integration
- NO tiene calendar integration
- NO tiene browser automation (solo RAG web search)
- NO tiene voice-first design (texto primero)
- NO tiene Telegram bot integrado
- NO tiene alter egos / personalidades
- NO tiene computer use nativo

### Debilidades Open WebUI (verificadas)

1. **Bus factor = 1**: tjbck tiene 10,740 de todas las contributions
2. **Database migration pain**: v0.8.0 requirio migracion "long-running"
3. **Connection pool exhaustion**: Bug mayor en v0.8.0, 13+ PRs para fix
4. **MCP tools regression**: v0.7.2 rompio MCP completamente (pickle errors)
5. **Licencia custom restrictiva**: No es OSI-approved, enterprise de pago
6. **Frontend en Svelte**: Ecosistema mas pequeno que React para contributors

---

## 3. Comparacion Detallada (Datos Corregidos)

### Tabla Principal

| Aspecto | Rain | Open WebUI | Ventaja |
|---|---|---|---|
| **Stack** | Python FastAPI + Next.js 16 | Python FastAPI + SvelteKit | Empate |
| **LOC** | ~33,700 | Millones (~327 MB repo) | Rain (simplicidad) |
| **Proveedores IA** | 4 (Claude, OpenAI, Gemini, Ollama) | 15+ (Ollama nativo + OpenAI-compatible) | Open WebUI |
| **RAG** | No tiene | 11+ vector DBs, 15+ search providers | Open WebUI |
| **Canales** | Web + Flutter + Telegram (3) | Solo Web (responsive + PWA) | Rain |
| **App Movil** | Flutter nativa (iOS + Android, 205 tests) | Solo PWA (sin app nativa) | Rain |
| **Tools built-in** | 14 (7 core + 7 browser) | Built-in tools (web search, code exec, etc.) | Empate |
| **Plugins** | YAML (chat-creation, sandboxed) | Python editor web + Pipelines + MCP | Open WebUI (escala), Rain (simplicidad) |
| **Memoria** | Embeddings + temporal decay + JSON fallback | Knowledge bases + RAG | Open WebUI (mas completo) |
| **TTS** | edge-tts (4 voces, gratis) | Azure, ElevenLabs, OpenAI, Transformers, WebAPI | Open WebUI |
| **STT** | Whisper local (faster-whisper, integrado) | Local Whisper, OpenAI, Deepgram, Azure | Open WebUI (mas opciones) |
| **Computer Use** | Nativo (screenshots, clicks, typing, scroll) | No tiene | Rain |
| **Smart Home** | MCP (Home Assistant, Google Home) | No tiene | Rain |
| **Email** | MCP Gmail (read, send, search, labels) | No tiene | Rain |
| **Calendar** | MCP Google Calendar (CRUD eventos) | No tiene | Rain |
| **Browser Control** | MCP browser + Playwright tool (7 ops) | No tiene (solo RAG web search) | Rain |
| **Seguridad** | PIN + GREEN/YELLOW/RED + plugin sandbox | LDAP/SCIM + RBAC + tool policy | Open WebUI (enterprise) |
| **Multi-usuario** | Single-user (PIN) | Multi-user (RBAC, grupos, channels) | Open WebUI |
| **Multi-agente** | Tabs paralelos independientes | Modelo por chat (no multi-agent) | Rain |
| **Alter Egos** | 5 built-in + custom | Model Builder (similar pero basico) | Rain |
| **MCP** | First-class (Claude SDK + 4 MCP servers) | MCP SDK v1.26.0 (reciente) | Empate |
| **Metricas/Costos** | Dashboard completo (hora/dia/semana/mes) | Analytics dashboard (v0.8.0, nuevo) | Empate |
| **Plugin creation** | Natural language via chat | Manual Python editor | Rain |
| **Failover** | Automatico con replay de mensaje | No tiene (manual) | Rain |
| **Tests** | 579 (374 pytest + 205 Flutter) | Cypress E2E + unit tests | Empate |
| **i18n** | 2 idiomas (en/es) | 60 idiomas | Open WebUI |
| **Licencia** | Apache 2.0 (libre) | Custom restrictiva (enterprise pago) | Rain |
| **Comunidad** | Personal | 124k stars, 391 contributors | Open WebUI |

### Donde Rain GANA (ventajas reales)

1. **Asistente personal de vida real** — Email + Calendar + Smart Home + Browser. Open WebUI es solo chat con LLMs; Rain controla tu vida digital
2. **App movil nativa** — Flutter con 205 tests, Riverpod, Material 3, i18n. Open WebUI solo tiene PWA
3. **Plugin creation por chat** — Dices "crea un plugin para X" y Rain genera el YAML. Open WebUI requiere escribir Python
4. **Computer Use dedicado** — Modo explicito con screenshots, clicks, typing. Open WebUI no lo tiene
5. **Voice-first** — Whisper integrado + TTS. Rain fue disenado para voz; Open WebUI es texto con voz como extra
6. **Alter Egos** — Personalidades switcheables con system prompts custom. Concepto unico
7. **Multi-agente con tabs** — Agentes paralelos con CWD independiente. Open WebUI tiene 1 modelo por chat
8. **Model failover automatico** — Si Claude falla, salta a OpenAI → Gemini → Ollama con replay
9. **Simplicidad** — `pip install` + 1 API key. Open WebUI necesita Docker + Redis + PostgreSQL para produccion
10. **Licencia libre** — Apache 2.0 sin restricciones vs licencia custom enterprise

### Donde Open WebUI GANA (ventajas reales)

1. **RAG** — 11+ vector DBs + 15+ search providers. Rain no tiene RAG sobre documentos
2. **Enterprise** — LDAP, SCIM, SSO, RBAC, grupos, channels. Rain es single-user
3. **Comunidad** — 124k stars, 391 contributors, marketplace activo
4. **i18n** — 60 idiomas vs 2
5. **Multi-TTS/STT** — Azure, ElevenLabs, OpenAI, Deepgram vs solo edge-tts
6. **Mas proveedores** — 15+ vs 4 (aunque Rain cubre los principales)
7. **Madurez** — 2+ anos, 50+ releases en 2025-2026, battle-tested
8. **Observability** — OpenTelemetry nativo (traces, metrics, logs)
9. **Storage cloud** — S3, GCS, Azure Blob para archivos

### Donde estan empatados

- Backend stack (ambos FastAPI/Python)
- MCP support (ambos lo tienen)
- Memory/embeddings (ambos sentence-transformers + decay)
- Analytics/metricas (ambos tienen dashboards)
- Testing (ambos tienen cobertura, diferente enfoque)

---

## 4. Mejoras Implementadas — Historial Completo

### Ronda 1 (2026-02-18) — Cierre de brechas criticas

| # | Mejora | Estado | Detalle |
|---|---|---|---|
| 1 | **Tests unitarios backend** | COMPLETADA | 374 tests en 10 archivos (pytest) |
| 2 | **Memoria con embeddings** | COMPLETADA | sentence-transformers + all-MiniLM-L6-v2, SQLite, cosine similarity |
| 3 | **Ollama como provider** | COMPLETADA | Streaming, agentic loop, tool calling, 8 modelos, $0 |
| 4 | **Browser tool (Playwright)** | COMPLETADA | 7 tools, headless, lazy-load, URL blocking |
| 5 | **Cron/tareas programadas** | COMPLETADA | 3 tipos, croniter, meta-tool, background loop 30s |
| 6 | **Temporal decay memories** | COMPLETADA | Exponencial, half-life 30d, 85% semantic + 15% decay |
| 7 | **Model failover** | COMPLETADA | Init + streaming, chain configurable, replay, notificacion |

### Ronda 2 (2026-02-18) — Problemas medios

| # | Mejora | Estado | Detalle |
|---|---|---|---|
| 8 | **Refactor useWebSocket** | COMPLETADA | 557 → 247 LOC (-56%). 4 sub-hooks: Tool, Permission, ComputerUse, SubAgent |
| 9 | **Gemini async nativo** | COMPLETADA | `send_message_async()` nativo en vez de `run_in_executor` |
| 10 | **Rate limiting en /api/auth** | COMPLETADA | Categoria AUTH (10/min), removido de paths exentos, rate limit por IP |
| 11 | **Plugin sandboxing** | COMPLETADA | Env vars restringido (allowlist), cwd protegido, memory limit 512MB (Linux) |
| 12 | **Flutter tests** | COMPLETADA | 205 tests en 11 archivos: models, providers, l10n, widgets |

### Ronda 3 (2026-02-18) — Problemas criticos

| # | Mejora | Estado | Detalle |
|---|---|---|---|
| 13 | **Browser pool** | COMPLETADA | BrowserPool class: per-agent pages, max 5, asyncio.Lock, auto-cleanup, lazy launch |
| 14 | **Scheduler ai_prompt** | COMPLETADA | Provider temporal, timeout 120s, solo GREEN tools, last_result/last_error en DB |
| 15 | **Encryption → OS keyring** | COMPLETADA | key_manager.py, auto-migracion desde config.json, fallback graceful |

### Detalle Ronda 3

**Browser Pool** — De singleton a pool por agente:
- `BrowserPool` class en `browser_ops.py`: `acquire(agent_id)` / `release(agent_id)`
- Un browser Chromium compartido, pero cada agente tiene su propia pagina (tab) aislada
- Max 5 paginas concurrentes (retorna error claro si se excede)
- `asyncio.Lock` para thread safety en creacion de browser
- Auto-shutdown: cuando el ultimo agente libera su pagina, se cierra Playwright
- Lazy launch: browser solo se inicia cuando el primer agente lo necesita
- `ToolExecutor` inyecta `_agent_id` en args de browser tools (invisible al LLM)
- `BaseProvider.initialize()` ahora recibe `agent_id` y lo pasa al executor
- `destroy_agent()` llama `cleanup()` para liberar la pagina del agente

**Scheduler ai_prompt** — Tareas AI ahora se ejecutan:
- `_scheduler_execute_ai_prompt()` en server.py: crea provider temporal con config default
- Usa `compose_system_prompt()` para contexto + memories
- Solo auto-aprueba GREEN tools (read-only): read_file, list_dir, search, grep
- Deniega YELLOW/RED tools por seguridad (sin supervision humana)
- `asyncio.wait_for()` con timeout 120s para prevenir tareas colgadas
- Provider se crea y destruye por ejecucion (no persiste)
- `storage.py`: columnas `last_result` TEXT y `last_error` TEXT con migracion automatica
- `meta_tool.py`: `list` muestra `[LAST RUN: OK/ERROR]`, `show` muestra resultado completo
- Bash tasks mejoradas: manejo de exit codes, timeout, kill en timeout

**Encryption Key → OS Keyring**:
- `key_manager.py` nuevo modulo: `ensure_encryption_key()`, `get_encryption_key()`, `store_encryption_key()`, `migrate_key_from_config()`
- Orden de resolucion: 1) OS keyring → 2) config.json (auto-migra) → 3) genera nueva
- Keyring backends: Windows Credential Locker, macOS Keychain, Linux SecretService
- `_is_keyring_available()` detecta backend inutilizable (headless Linux) con cache
- Migracion automatica: mueve key de config.json a keyring, deja nota `_encryption_key_migrated`
- Fallback graceful: si keyring no disponible, sigue usando config.json con warning
- `database.py`: `_get_fernet()` ahora usa `ensure_encryption_key()` en vez de leer config directo
- `server.py`: llama `ensure_encryption_key()` en lifespan antes de `_ensure_db()`
- `pyproject.toml`: `keyring>=24.0` en dependencias core
- Tests: `conftest.py` deshabilita keyring en tests (`_keyring_available = False`)

### Detalle Ronda 2

**Refactor useWebSocket.ts** — De monolito a chain-of-responsibility:
- `useWebSocket.ts` — 247 LOC, router principal + core messages (ping, status, streaming, result, error)
- `useToolMessages.ts` — 48 LOC, `tool_use` + `tool_result`
- `usePermissionMessages.ts` — 30 LOC, `permission_request`
- `useComputerUseMessages.ts` — 60 LOC, `mode_changed` + `computer_screenshot` + `computer_action`
- `useSubAgentMessages.ts` — 60 LOC, `subagent_spawned` + `subagent_completed`
- `historyUtils.ts` — `loadHistoryForAgent()` extraido (67 → 184 LOC)
- TypeScript compila sin errores, zero cambios en imports externos

**Gemini Provider Async**:
- Antes: `loop.run_in_executor(None, lambda: self._chat.send_message(...))`
- Ahora: `await self._chat.send_message_async(current_content)`
- Eliminado `import asyncio` innecesario

**Rate Limiting Auth**:
- `rate_limiter.py`: Nueva categoria `AUTH = "auth"` con limite 10/min
- `server.py`: `/api/auth` removido de `_EXEMPT_PATHS`
- Requests sin token usan `ip:{client_ip}` como rate limit key
- Proteccion en capas: HTTP (10/min por IP) + App (3 PIN fails → 5min lockout)

**Plugin Sandboxing**:
- `_build_sandboxed_env(plugin_env)`: Solo 14 vars de sistema esenciales (PATH, HOME, TEMP, etc.) + plugin env vars
- `_get_safe_cwd(cwd)`: Si cwd es directorio del server o subdirectorio, redirige a `Path.home()`
- `_get_preexec_fn()`: En Linux, `resource.RLIMIT_AS` = 512 MB max por subprocess
- Aplicado a bash Y python plugins. HTTP ya esta sandboxed por naturaleza

**Flutter Tests** (205 tests en 11 archivos):
- Models: message (45), agent (20), conversation (5), metrics (12), rate_limits (16), auth (8), provider_info (12)
- L10n: translations (20) — 120+ keys en/es, params, meses, dias
- Providers: settings (18), agent (35)
- Widgets: theme + Riverpod integration (14)
- Sin dependencias extra (solo flutter_test + shared_preferences mock)

---

## 5. Problemas Conocidos (Pendientes)

### Criticos (TODOS RESUELTOS en Ronda 3)

| Problema | Estado |
|---|---|
| ~~Browser singleton~~ | RESUELTO: BrowserPool con paginas por agente, max 5, auto-cleanup |
| ~~Scheduler ai_prompt no ejecuta~~ | RESUELTO: Provider temporal, timeout 120s, GREEN-only tools |
| ~~Encryption key plaintext~~ | RESUELTO: OS keyring con auto-migracion y fallback graceful |

### Medios (RESUELTOS en Ronda 2)

| Problema | Estado |
|---|---|
| ~~useWebSocket monolito (557 LOC)~~ | RESUELTO: 247 LOC + 4 sub-hooks |
| ~~Gemini blocking (run_in_executor)~~ | RESUELTO: async nativo |
| ~~Sin rate limit en /api/auth~~ | RESUELTO: AUTH 10/min |
| ~~Plugins sin sandbox~~ | RESUELTO: env restringido, cwd protegido, memory limit |
| ~~Flutter sin tests~~ | RESUELTO: 205 tests |

### Bajos

| Problema | Detalle |
|---|---|
| Session resumption solo Claude | OpenAI/Gemini/Ollama no pueden reanudar sesiones |
| Flutter sin tests de WebSocket | Services no testeados (websocket_service, audio_service) |
| Tests backend sin WebSocket | El core WebSocket (60% del uso) no tiene tests |
| Translations en archivo flat | 464 LOC sin organizacion, deberia separarse |
| Sin error boundaries React | Crash en un componente crashea todo el chat |

---

## 6. Posicionamiento Estrategico

| | **Open WebUI** | **Rain Assistant** |
|---|---|---|
| **Que es** | Chat UI enterprise para LLMs | Asistente personal de IA con integraciones de vida real |
| **Target** | Empresas que quieren dar acceso a LLMs internamente | Personas que quieren su propio Jarvis/Friday |
| **Filosofia** | "Habla con cualquier modelo" | "Tu hub de IA controla tu vida digital" |
| **Complejidad** | Alta (Docker, Redis, PostgreSQL, LDAP) | Media (`pip install` + 1 API key) |
| **Killer feature** | RAG + Enterprise + Comunidad | Email + Calendar + Smart Home + Browser + Voice |
| **Licencia** | Custom restrictiva (enterprise pago) | Apache 2.0 (100% libre) |
| **Analogia** | Slack para IA — muchos usuarios, muchos modelos, canales | Jarvis — una IA personal que controla tu casa, email, y calendario |

### Conclusion

**Rain y Open WebUI NO son competidores directos.** Son productos para casos de uso diferentes:

- Si necesitas dar acceso a LLMs a 500 empleados con LDAP → **Open WebUI**
- Si quieres un asistente personal que lea tu email, maneje tu calendario, controle tus luces, y navegue web por ti → **Rain**

Rain tiene **6 integraciones de vida real** que Open WebUI no tiene y probablemente nunca tendra (Email, Calendar, Smart Home, Browser automation, Computer Use, Flutter app). Esa es la ventaja competitiva real.

---

## 7. Funcionalidades Disponibles en Rain (inventario completo)

### Core
1. **Multi-agente** — Tabs paralelos, cada uno con su CWD
2. **4 proveedores IA** — Claude, OpenAI, Gemini, Ollama + failover automatico
3. **Streaming** — Respuestas en tiempo real via WebSocket
4. **Agentic loops** — Hasta 50 iteraciones de tool calling por mensaje

### Herramientas (14 built-in)
5. **File ops** — read, write, edit, list_directory (path traversal protected)
6. **Bash/Shell** — Cross-platform, 300s timeout, 30K output limit
7. **Browser** — Playwright: navigate, screenshot, click, type, extract, scroll, close
8. **Search** — glob patterns + regex grep

### Integraciones de Vida Real (MCP)
9. **Email (Gmail)** — Leer inbox, enviar, buscar, responder, borradores, etiquetas
10. **Calendar (Google)** — Listar, crear, editar, borrar eventos, quick add
11. **Smart Home** — Home Assistant + Google Home: luces, termostato, escenas, dispositivos
12. **Browser MCP** — Navegacion web controlada por Rain

### Personalidad & Memoria
13. **Alter Egos** — 5 built-in (rain, professor, speed, security, rubber_duck) + custom
14. **Memories** — Rain recuerda entre sesiones (semantic search + temporal decay)
15. **Prompt Composer** — ego + top 10 memories relevantes por mensaje

### Plugins
16. **Plugin system** — YAML, 3 tipos (http/bash/python), sandboxed
17. **Plugin creation** — Crear via chat natural, sin codigo
18. **Marketplace panel** — Buscar, instalar, actualizar plugins

### Audio & Voz
19. **STT** — Whisper local (faster-whisper, CPU int8, VAD)
20. **TTS** — edge-tts gratis, 4 voces, auto-play
21. **Voice input** — Grabacion lazy, echo cancellation, min 3s

### Computer Use
22. **Computer Use** — Screenshots, clicks, typing, scroll, modo dedicado
23. **Emergency stop** — Boton de parada en permiso RED

### Operaciones
24. **Model failover** — Automatico con replay de mensaje
25. **Tareas programadas** — Cron: reminders, bash, ai_prompt
26. **Metricas** — Dashboard: costo, sesiones, tokens, por periodo
27. **Permisos** — GREEN/YELLOW/RED/COMPUTER con 28 patrones peligrosos
28. **Rate limiting** — 6 categorias incluyendo AUTH (10/min)

### Plataformas
29. **Web** — Next.js 16, responsive, 2 temas, i18n en/es
30. **Flutter** — iOS + Android nativo, Material 3, Riverpod, 205 tests
31. **Telegram Bot** — Voz, inline keyboards, per-user sessions

### Testing
32. **Backend tests** — 374 tests pytest (permisos, DB, plugins, auth, API, memories, egos, prompt)
33. **Flutter tests** — 205 tests (models, providers, l10n, widgets)

---

## 8. Proximas Prioridades (ordenadas por impacto/esfuerzo)

### Alta Prioridad

| # | Mejora | Por que | Esfuerzo |
|---|---|---|---|
| 1 | ~~**Fix browser singleton**~~ | ~~Concurrencia rota~~ | COMPLETADA (Ronda 3) |
| 2 | **Tests WebSocket** | Es el 60% de la app con 0 tests | 4-6 horas |
| 3 | **RAG sobre documentos** | Brecha mas grande vs competidores | 1-2 dias |
| 4 | ~~**Fix scheduler ai_prompt**~~ | ~~No se ejecutaban~~ | COMPLETADA (Ronda 3) |
| 5 | ~~**Encryption key → OS keyring**~~ | ~~Riesgo de seguridad~~ | COMPLETADA (Ronda 3) |

### Media Prioridad

| # | Mejora | Por que | Esfuerzo |
|---|---|---|---|
| 6 | Discord channel | Segundo canal mas demandado | 1 dia |
| 7 | WhatsApp channel | Masivo en Latam (baileys) | 1-2 dias |
| 8 | Sub-agentes reales | Agent spawning con A2A | 2-3 dias |
| 9 | Image generation tool | DALL-E o Stability | Medio dia |
| 10 | Mas proveedores | Bedrock, HuggingFace, Together | 1 dia |

### Baja Prioridad

| # | Mejora | Impacto |
|---|---|---|
| 11 | PWA/Service Worker | Push notifications web |
| 12 | Voice Wake | Always-on wake word |
| 13 | Docker sandbox | Aislamiento de sesiones |
| 14 | Canvas/drawing tool | Diagramas por IA |
| 15 | Mas idiomas | Expansion i18n mas alla de en/es |

---

## 9. Brechas vs Open WebUI — Estado

### Cerradas (13 brechas)

| Brecha | Fecha | Solucion |
|---|---|---|
| Tests backend | 2026-02-18 | 374 tests pytest |
| Tests Flutter | 2026-02-18 | 205 tests (models, providers, l10n, widgets) |
| Memoria con embeddings | 2026-02-18 | sentence-transformers + SQLite + temporal decay |
| Ollama/modelos locales | 2026-02-18 | Provider completo con streaming + tool calling |
| Browser tool | 2026-02-18 | Playwright (7 tools) |
| Cron/scheduling | 2026-02-18 | Modulo scheduled_tasks/ completo |
| Temporal decay | 2026-02-18 | Decay exponencial (half-life 30d) |
| Model failover | 2026-02-18 | Failover automatico init + streaming |
| Gemini blocking | 2026-02-18 | Async nativo (send_message_async) |
| Plugin sandbox | 2026-02-18 | Env restringido + cwd protegido + memory limit |
| Browser concurrencia | 2026-02-18 | BrowserPool: paginas por agente, max 5, auto-cleanup |
| Scheduler ai_prompt | 2026-02-18 | Provider temporal, timeout 120s, GREEN-only, result/error en DB |
| Encryption key segura | 2026-02-18 | OS keyring (Win/Mac/Linux) con auto-migracion |

### Abiertas (donde Open WebUI aun gana)

| Brecha | Severidad | Notas |
|---|---|---|
| **RAG** | Alta | 11+ vector DBs — Rain no tiene RAG sobre documentos |
| **Enterprise/Multi-user** | Alta | LDAP, SCIM, RBAC, grupos — Rain es single-user |
| **i18n** | Media | 60 idiomas vs 2 |
| **Mas proveedores** | Media | 15+ vs 4 |
| **TTS/STT opciones** | Baja | Azure, ElevenLabs, Deepgram vs edge-tts/Whisper |
| **Observability** | Baja | OpenTelemetry nativo |

### Donde Rain YA supera a Open WebUI (y siempre lo hara)

| Ventaja Rain | Open WebUI |
|---|---|
| Email (Gmail MCP) | No tiene |
| Calendar (Google Calendar MCP) | No tiene |
| Smart Home (Home Assistant / Google Home MCP) | No tiene |
| Browser automation (Playwright + MCP) | No tiene (solo RAG search) |
| Computer Use nativo | No tiene |
| Flutter app nativa | Solo PWA |
| Alter Egos | No tiene |
| Plugin creation por chat | Requiere Python manual |
| Licencia Apache 2.0 | Licencia custom restrictiva |
| Voice-first design | Texto con voz como extra |

---

## 10. Changelog Completo

### 2026-02-18 — Ronda 1: Cierre de brechas criticas

- Test Suite: 374 tests en 10 archivos pytest
- Memoria con Vector Embeddings: sentence-transformers + SQLite + cosine similarity
- Ollama Provider: streaming, agentic loop, tool calling, 8 modelos
- Browser Tool: Playwright, 7 operaciones, URL blocking
- Cron/Scheduler: croniter, 3 tipos, meta-tool, background loop
- Temporal Decay: exponencial, half-life 30d, formula combinada
- Model Failover: init + streaming, chain configurable, replay

### 2026-02-18 — Ronda 2: Problemas medios

- Refactor useWebSocket: 557 → 247 LOC, 4 sub-hooks (chain-of-responsibility)
- Gemini async nativo: `send_message_async()` en vez de `run_in_executor`
- Rate limiting auth: categoria AUTH 10/min, removido de exempt paths
- Plugin sandboxing: env allowlist (14 vars), cwd protection, memory limit 512MB
- Flutter tests: 205 tests en 11 archivos (models, providers, l10n, widgets)

### 2026-02-18 — Ronda 3: Problemas criticos

- Browser pool: BrowserPool class, per-agent pages (max 5), asyncio.Lock, auto-cleanup, lazy launch
- Scheduler ai_prompt: provider temporal, compose_system_prompt, GREEN-only tools, timeout 120s, last_result/last_error en DB
- Encryption keyring: key_manager.py, OS keyring (Win/Mac/Linux), auto-migracion desde config.json, fallback graceful
