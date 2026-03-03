# Rain Assistant — Plan Open Core

## Resumen

Rain Assistant usa el modelo **Open Core**: el engine base es open source (AGPL-3.0),
y las features premium requieren una licencia comercial (de pago).

---

## Licenciamiento

| Componente | Licencia | Acceso |
|-----------|----------|--------|
| Core (repo publico) | AGPL-3.0 | Gratis, cualquiera puede usar/modificar |
| Premium features | Licencia comercial | Requiere suscripcion Rain Pro/Enterprise |
| App Flutter | Proprietary | Solo para suscriptores |

### Por que AGPL y no Apache/MIT?

- AGPL obliga a que si alguien usa Rain como servicio (SaaS), **debe publicar sus cambios**
- Las empresas que NO quieran publicar su codigo, **prefieren pagarte** por la licencia comercial
- Es el mismo modelo de MongoDB ($1.6B/year), GitLab, Grafana, n8n, etc.

---

## Estructura de Repositorios

```
GitHub PUBLICO: rain-assistant (AGPL-3.0)
├── server.py              (core server, con feature flags)
├── main.py                (CLI entry point)
├── database.py            (SQLite + encryption)
├── key_manager.py         (API key storage)
├── transcriber.py         (Whisper STT)
├── synthesizer.py         (Edge TTS)
├── recorder.py            (audio recording)
├── permission_classifier.py (GREEN/YELLOW/RED)
├── rate_limiter.py        (rate limiting)
├── shared_state.py        (global state)
├── prompt_composer.py     (prompt assembly, sin memories/egos)
├── logging_config.py      (logging)
├── metrics.py             (token tracking)
├── claude_client.py       (claude SDK client)
├── tunnel.py              (cloudflare tunnel)
├── telegram_config.py     (config stub)
│
├── providers/             TODO EL DIRECTORIO
│   ├── __init__.py        (factory pattern)
│   ├── base.py            (BaseProvider abstract)
│   ├── claude_provider.py
│   ├── openai_provider.py
│   ├── gemini_provider.py
│   └── ollama_provider.py
│
├── tools/                 TODO EL DIRECTORIO
│   ├── definitions.py     (tool schemas)
│   ├── executor.py        (tool dispatch)
│   ├── bash_ops.py
│   ├── file_ops.py
│   ├── browser_ops.py
│   └── search_ops.py
│
├── routes/                BASICOS
│   ├── __init__.py
│   ├── auth.py            (PIN + token auth)
│   ├── agents.py          (agent CRUD)
│   ├── files.py           (file browser)
│   ├── images.py          (image upload)
│   └── settings.py        (config endpoints)
│
├── voice/                 TODO EL DIRECTORIO
│   ├── vad.py             (voice activity detection)
│   ├── wake_word.py
│   └── talk_session.py
│
├── utils/                 TODO EL DIRECTORIO
│   ├── sanitize.py
│   └── __init__.py
│
├── frontend/              FRONTEND COMPLETO (Next.js)
│   └── (todo el codigo Next.js)
│
├── static/                BUILD OUTPUT
│
├── tests/                 TESTS DEL CORE
│   ├── conftest.py
│   ├── test_websocket.py
│   ├── test_server_api.py
│   ├── test_server_auth.py
│   └── test_permission_classifier.py
│
├── docs/                  DOCUMENTACION
├── .github/workflows/     CI/CD
├── pyproject.toml         (package config)
├── Dockerfile
├── docker-compose.yml
├── landing.html
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE (AGPL-3.0)
└── scripts de instalacion

PRIVADO (NO se publica):
├── documents/             PREMIUM - RAG system
│   ├── parser.py
│   ├── chunker.py
│   ├── storage.py
│   ├── query.py
│   └── meta_tool.py
│
├── memories/              PREMIUM - Semantic memories
│   ├── embeddings.py
│   ├── storage.py
│   ├── model_registry.py
│   └── meta_tool.py
│
├── alter_egos/            PREMIUM - Personalities
│   ├── storage.py
│   └── meta_tool.py
│
├── directors/             PREMIUM - Autonomous agents
│   ├── executor.py
│   ├── storage.py
│   ├── builtin.py
│   ├── task_queue.py
│   ├── inbox.py
│   ├── projects_tool.py
│   └── meta_tool.py
│
├── plugins/               PREMIUM - Plugin system
│   ├── executor.py
│   ├── loader.py
│   ├── schema.py
│   ├── converter.py
│   └── meta_tool.py
│
├── marketplace/           PREMIUM - Plugin store
│   ├── registry.py
│   ├── publisher.py
│   └── meta_tool.py
│
├── subagents/             PREMIUM - Multi-agent
│   ├── manager.py
│   └── meta_tool.py
│
├── scheduled_tasks/       PREMIUM - Cron scheduling
│   ├── storage.py
│   └── meta_tool.py
│
├── computer_use.py        PREMIUM - Desktop automation
├── computer_use_safety.py
├── computer_use_vision.py
├── computer_use_recorder.py
│
├── telegram_bot.py        PREMIUM - Telegram interface
│
├── rain_flutter/          PREMIUM - Mobile app
│   └── (todo el codigo Flutter)
│
├── routes/directors.py    PREMIUM - Director endpoints
│
└── tests/                 PREMIUM TESTS
    ├── test_documents.py
    ├── test_directors.py
    ├── test_plugins.py
    ├── test_alter_egos.py
    ├── test_memories.py
    └── test_smoke_e2e.py
```

---

## Feature Flags (server.py)

Para que el core funcione sin los modulos premium, `server.py` necesita un sistema
de feature flags. Los imports premium deben ser condicionales:

```python
# En server.py (inicio del archivo)
import os

FEATURES = {
    "plugins":        os.getenv("RAIN_FEATURE_PLUGINS", "false").lower() == "true",
    "documents":      os.getenv("RAIN_FEATURE_DOCUMENTS", "false").lower() == "true",
    "memories":       os.getenv("RAIN_FEATURE_MEMORIES", "false").lower() == "true",
    "alter_egos":     os.getenv("RAIN_FEATURE_ALTER_EGOS", "false").lower() == "true",
    "directors":      os.getenv("RAIN_FEATURE_DIRECTORS", "false").lower() == "true",
    "computer_use":   os.getenv("RAIN_FEATURE_COMPUTER_USE", "false").lower() == "true",
    "telegram":       os.getenv("RAIN_FEATURE_TELEGRAM", "false").lower() == "true",
    "subagents":      os.getenv("RAIN_FEATURE_SUBAGENTS", "false").lower() == "true",
    "marketplace":    os.getenv("RAIN_FEATURE_MARKETPLACE", "false").lower() == "true",
    "scheduled":      os.getenv("RAIN_FEATURE_SCHEDULED", "false").lower() == "true",
}

# Imports condicionales
if FEATURES["plugins"]:
    from plugins import loader, executor as plugin_executor, meta_tool as plugin_meta
if FEATURES["documents"]:
    from documents import meta_tool as docs_meta
# ... etc
```

---

## Tiers de Producto

### Tier 1: Community (Free / AGPL)

**Target**: Developers individuales, estudiantes, hobbyistas

| Feature | Estado |
|---------|--------|
| 4 AI providers (Claude, GPT, Gemini, Ollama) | Incluido |
| Voice input/output (Whisper + Edge TTS) | Incluido |
| 17 built-in tools (read, write, bash, search...) | Incluido |
| Permission system (GREEN/YELLOW/RED) | Incluido |
| Web UI completa (Next.js) | Incluido |
| File browser | Incluido |
| Conversation history (SQLite) | Incluido |
| Remote access (Cloudflare Tunnel) | Incluido |
| Rate limiting | Incluido |
| Docker support | Incluido |
| Self-hosted, 100% privado | Incluido |

### Tier 2: Pro ($15/mes)

**Target**: Developers profesionales, freelancers

| Feature | Estado |
|---------|--------|
| Todo de Community | Incluido |
| Plugin system (YAML, sin codigo) | PREMIUM |
| Plugin Marketplace | PREMIUM |
| RAG / Documents (PDF, DOCX, EPUB, Markdown...) | PREMIUM |
| Semantic memories (embeddings) | PREMIUM |
| Alter Egos (personalidades) | PREMIUM |
| Telegram Bot | PREMIUM |
| Metrics & analytics | PREMIUM |
| App movil (Flutter) | PREMIUM |

### Tier 3: Enterprise ($39/mes/usuario)

**Target**: Equipos, empresas, agencias

| Feature | Estado |
|---------|--------|
| Todo de Pro | Incluido |
| Computer Use (automatizacion de escritorio) | PREMIUM |
| Directors (agentes autonomos con schedule) | PREMIUM |
| Sub-agentes multi-LLM | PREMIUM |
| Scheduled tasks (cron) | PREMIUM |
| Project management | PREMIUM |
| Multi-user isolation | PREMIUM |
| Licencia comercial (no AGPL) | PREMIUM |
| Soporte prioritario | PREMIUM |

---

## Mecanismo de Activacion Premium

### Opcion A: License Key (Recomendada para v1)

```python
# En rain_license.py
import hashlib
import json
from datetime import datetime

def verify_license(key: str) -> dict:
    """Verifica la license key y retorna las features habilitadas."""
    # Decodifica la key (firma HMAC)
    # Retorna: {"tier": "pro", "features": [...], "expires": "2026-12-31"}
    pass

def get_enabled_features(license_key: str = None) -> dict:
    """Retorna features activas basado en la licencia."""
    if not license_key:
        return {f: False for f in PREMIUM_FEATURES}

    license_data = verify_license(license_key)
    if not license_data or datetime.fromisoformat(license_data["expires"]) < datetime.now():
        return {f: False for f in PREMIUM_FEATURES}

    return {f: f in license_data["features"] for f in PREMIUM_FEATURES}
```

### Opcion B: Cloud Verification (Para v2)

- API call a `api.rain-assistant.com/verify`
- Cacheo local de 24h
- Graceful degradation si no hay internet

---

## Cambios Necesarios para la Separacion

### 1. server.py
- [ ] Agregar sistema de feature flags
- [ ] Hacer imports de modulos premium condicionales
- [ ] Agregar endpoint `/api/features` que retorne features habilitadas
- [ ] En `get_all_tool_definitions()`: filtrar tools premium segun licencia

### 2. Frontend (Next.js)
- [ ] Agregar estado de licencia en `useSettingsStore`
- [ ] Mostrar badge "PRO" en panels premium
- [ ] Gate de UI: mostrar panel pero con overlay "Upgrade to Pro"
- [ ] Agregar pagina/modal de pricing in-app

### 3. pyproject.toml
- [ ] Mover deps premium a optional extras
- [ ] Ya esta parcialmente hecho (computer-use, telegram, etc.)

### 4. CI/CD
- [ ] Crear workflow separado para builds premium
- [ ] Tests del core deben pasar SIN modulos premium instalados
- [ ] Agregar matrix testing: core-only vs all-features

### 5. Licencia
- [ ] Cambiar LICENSE de Apache-2.0 a AGPL-3.0
- [ ] Agregar header AGPL en cada archivo del core
- [ ] Crear COMMERCIAL_LICENSE.md para premium
- [ ] Actualizar pyproject.toml con nueva licencia

---

## Prioridades de Implementacion

1. **Fase 1** (Ahora): Documentar la separacion (este archivo)
2. **Fase 2**: Implementar feature flags en server.py
3. **Fase 3**: Crear repo publico con solo el core
4. **Fase 4**: Sistema de license keys
5. **Fase 5**: Pricing page funcional + checkout (Stripe/Lemon Squeezy)
6. **Fase 6**: Dashboard de licencias para usuarios
