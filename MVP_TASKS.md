# Rain Assistant — MVP Tasks (Power Users)

Estado al 2026-02-19. Tareas pendientes para cerrar el MVP v1 para power users.

---

## COMPLETADO en este chat

### 1. Onboarding / Primera experiencia
- [x] README con instalacion, setup, primeros pasos — YA EXISTIA completo
- [x] `rain --help` con argparse — YA EXISTIA con doctor, setup, flags
- [x] Setup wizard automatico en primer run — YA EXISTIA
- [x] Install scripts (bash + PowerShell) — YA EXISTIAN

### 2. Estabilidad / Edge cases
- [x] **Rate limiter: token collision** — Cambiado de `token[:8]` a SHA-256 hash para evitar colisiones entre usuarios
- [x] **Rate limiter: memory leak** — Agregado MAX_WINDOWS (10,000) cap y cleanup forzado
- [x] **Rate limiter: public API** — Agregado metodo `reset()` para tests (ya no hackean `_windows`)
- [x] **server.py: JSON parse** — Agregado try-catch en WebSocket loop para mensajes malformados
- [x] **server.py: bare except** — Cambiado `except Exception: pass` a logging con traceback + security event
- [x] **server.py: send()** — Agregado logging cuando falla (log-once para no spamear)
- [x] **server.py: cleanup** — Await para tasks canceladas, limpieza de pending_permissions, try-except en subagent cleanup
- [x] **Providers: tool execution** — Protegido `execute()` con try-except en los 4 providers (Claude, OpenAI, Gemini, Ollama)
- [x] **Providers: streaming** — Claude y OpenAI ahora tienen try-except alrededor del streaming loop
- [x] **Tests** — Migrados a usar `rl.reset()` en vez de `rl._windows.clear()`

---

## PENDIENTE para otros chats

### 3. MCP Graceful Degradation
- [ ] Cada MCP server (email, browser, calendar, smart home) debe funcionar/fallar independientemente
- [ ] Si un MCP no esta configurado, no debe crashear — solo desactivar esas tools
- [ ] Verificar que `mcp_config_path` corrupto no tumba el server
- [ ] Agregar mensaje claro al usuario cuando un MCP falla ("Email no configurado, usa rain setup")

### 4. Plugin Marketplace
- [ ] Verificar flujo completo: buscar → instalar → usar → desinstalar
- [ ] Crear 5-10 plugins de ejemplo utiles (weather, translator, summarizer, etc.)
- [ ] Verificar que plugins del marketplace se integran correctamente con los 4 providers
- [ ] Documentar como crear plugins en el README o wiki

### 5. PyPI Packaging
- [ ] Verificar que `pip install .` funciona limpio desde cero
- [ ] Verificar que las dependencias opcionales (`[telegram]`, `[all]`, etc.) instalan correctamente
- [ ] Probar instalacion en Linux, macOS, y Windows
- [ ] Publicar en PyPI como `rain-assistant`
- [ ] Verificar que `rain doctor` detecta correctamente dependencias faltantes

### 6. Security Review
- [ ] Verificar que no hay secrets hardcodeados en el codigo
- [ ] Crear `.env.example` si es necesario (actualmente todo va por `~/.rain-assistant/config.json`)
- [ ] Verificar que el PIN bcrypt funciona correctamente (migracion de plain text)
- [ ] Revisar que tokens de API nunca se loguean completos (solo prefix)
- [ ] Verificar CORS settings para produccion

### 7. Landing Page
- [ ] Crear una pagina estatica minima explicando que es Rain
- [ ] Incluir: que es, features, instalacion rapida, screenshots
- [ ] Hosting: GitHub Pages o similar (gratis)
- [ ] Dominio (opcional): rain-assistant.dev o similar

### 8. Smoke Test End-to-End
- [ ] Probar cada provider con key real:
  - [ ] Claude: chat + tool use + computer use + session resumption
  - [ ] OpenAI: chat + tool use + streaming
  - [ ] Gemini: chat + tool use + streaming
  - [ ] Ollama: chat + tool use + graceful degradation sin tools
- [ ] Probar MCP servers individuales:
  - [ ] Email (Gmail OAuth)
  - [ ] Browser (Playwright)
  - [ ] Calendar (Google Calendar OAuth)
  - [ ] Smart Home (Home Assistant)
- [ ] Probar plugin lifecycle: create → enable → use → disable → delete
- [ ] Probar Telegram bot: /start, voice messages, permissions
- [ ] Probar RAG: ingest document → search → remove

---

## MODELO DE DISTRIBUCION (despues de cerrar MVP)

### Target: Power Users
- **Canal principal**: GitHub releases + PyPI (`pip install rain-assistant`)
- **Descubrimiento**:
  - Hacker News (Show HN)
  - Reddit: r/selfhosted, r/LocalLLaMA, r/ChatGPT, r/ClaudeAI
  - Twitter/X: AI community
  - Product Hunt
- **Modelo de negocio inicial**:
  - Open source (Apache 2.0) — atrae early adopters
  - Freemium futuro: base gratis, Pro con integraciones premium
  - Lifetime deal para early adopters ($79-149)
- **Comunidad**: Discord o GitHub Discussions
- **Metricas**: GitHub stars, PyPI downloads, Discord members

### Expansion futura: Usuarios no-tecnicos
- Sistema de niveles (Simple/Intermedio/Avanzado)
- App Flutter en stores (Android/iOS)
- Hosted version (no BYOK, subscription)
- Marketing: "Siri que realmente funciona"

---

## NOTAS TECNICAS

### Arquitectura actual (referencia rapida)
- Backend: FastAPI + WebSocket (`server.py`, ~3,200 lineas)
- Frontend: Next.js 16 + Zustand 5 + Tailwind CSS 4
- Providers: Claude SDK, OpenAI, Gemini, Ollama
- Tools: 17 built-in + plugins YAML + MCP servers
- Storage: SQLite (conversations.db, memories.db)
- Voice: Whisper + VAD + wake word + TTS
- Deploy: `pip install rain-assistant` → `rain`

### Issues conocidos NO criticos
- `server.py` tiene 3,200+ lineas — funcional pero dificil de mantener. Considerar modularizar en futuro
- Cognitive complexity alta en `stream_response()` de todos los providers — funcional, refactor opcional
- Flutter app completa pero no es parte del MVP v1 (mantener, no priorizar)
- `test_server_auth.py` tiene rate limiter bleed issues preexistentes (no nuestro)
