# Rain Assistant — Estado del Proyecto v1.0.13

> **Fecha:** 28 de febrero de 2026
> **Propósito:** Congelar nuevas integraciones. Estabilizar, pulir y monetizar lo existente.

---

## Resumen Ejecutivo

Rain Assistant es un asistente de IA multi-plataforma (web, mobile, desktop, Telegram) con soporte para 4 proveedores de IA, sistema de plugins, RAG de documentos, computer use, voice, y agentes autónomos (Directors). El proyecto está en **v1.0.13** con ~70+ features implementadas.

**Veredicto:** El 90% funciona bien. El 10% restante son bordes sin pulir, features sin tests, y UX que se puede mejorar. No se necesitan más integraciones — se necesita **estabilidad, tests y monetización**.

---

## 1. Estado por Plataforma

### Backend (Python/FastAPI) — 9/10

| Componente | Estado | Notas |
|-----------|--------|-------|
| Server (FastAPI + WS) | ✅ Sólido | Middleware, CSRF, rate limiting, security headers |
| Claude Provider | ✅ Completo | MCP, session resumption, computer use |
| OpenAI Provider | ✅ Completo | Agentic loop, function calling, cost tracking |
| Gemini Provider | ✅ Completo | Async nativo, function calling |
| Ollama Provider | ✅ Completo | Local, tool support opcional |
| Plugins | ✅ Funcional | HTTP/bash/python, sandbox, audit log |
| RAG/Documentos | ✅ Completo | Hybrid search, BM25, reranking, 30+ formatos |
| Computer Use | ✅ 8 fases | Windows only, OCR, multi-monitor, recording |
| Memories | ✅ Funcional | Encrypted, semantic search, per-user |
| Telegram Bot | ✅ Funcional | Per-user sessions, voice, inline keyboards |
| Directors | ✅ Funcional | Cron scheduling, inbox, delegación |
| Auth/Security | ✅ Sólido | PIN+bcrypt, tokens, device management |
| Tests | ⚠️ Parcial | 70+ tests pero faltan computer use y telegram |

### Frontend Web (Next.js 16) — 9/10

| Componente | Estado | Notas |
|-----------|--------|-------|
| Chat multi-agente | ✅ Completo | Tabs, streaming, sub-agents, interrupt |
| Voice (4 modos) | ✅ Completo | Push-to-talk, VAD, talk-mode, wake-word |
| TTS | ✅ Completo | Azure, auto-play, 4 voces |
| Computer Use UI | ✅ Completo | Screenshots, zoom, multi-monitor, emergency stop |
| Permissions UX | ✅ Completo | Yellow/Red con PIN |
| Settings | ✅ Completo | Theme, lang, TTS, voice, devices |
| Metrics/Charts | ✅ Completo | Spend, tokens, rate limits, charts |
| History | ✅ Completo | Save/load/delete conversaciones |
| Memories UI | ✅ Completo | CRUD, categorías |
| Alter Egos | ✅ Completo | Switch, custom, emoji |
| Marketplace | ✅ Completo | Search, install, update, verified |
| Directors | ✅ Completo | Create, schedule, run, templates |
| Inbox | ✅ Completo | Approve/reject, filter, archive |
| i18n (en/es) | ✅ 100% | 360+ keys, sin strings hardcodeados |
| Responsive | ✅ Completo | Desktop sidebar + mobile drawer |
| Tests | ⚠️ Básico | 3 test files, falta cobertura de UI |

### App Mobile Flutter — 8.5/10

| Componente | Estado | Notas |
|-----------|--------|-------|
| Chat + streaming | ✅ Completo | Multi-agent, tool display, A2UI |
| Voice recording | ✅ Completo | WAV/M4A, Whisper transcription |
| TTS | ✅ Completo | Azure, auto-play |
| Voice call mode | ✅ Completo | PCM streaming, VAD, 4 modos |
| Image upload | ✅ Completo | Gallery + camera, multi-image |
| History | ✅ Completo | Browse, restore, delete |
| Memories | ✅ Completo | CRUD |
| Alter Egos | ✅ Completo | Switch, custom |
| Marketplace | ✅ Completo | Discover, install |
| Directors | ✅ Completo | Manage + inbox |
| Settings | ✅ Completo | Theme, lang, provider, model, TTS, voice |
| Computer Use | ✅ Completo | Screenshots, actions, monitor select |
| Android | ✅ Release-ready | Signing configurado |
| iOS | ⚠️ Requiere config | Provisioning profiles pendientes |
| Tests | ⚠️ Solo unit | 31 tests, faltan integration/UI tests |
| Crash reporting | ❌ No integrado | Sin Crashlytics/Sentry |
| Analytics | ❌ No integrado | Sin Firebase Analytics |
| Privacy policy | ❌ Falta | Necesario para stores |

### Distribución & DevOps — 9/10

| Componente | Estado | Notas |
|-----------|--------|-------|
| PyPI | ✅ Publicado | `pip install rain-assistant` |
| Docker | ✅ Production-ready | Multi-stage, non-root, healthcheck |
| Installers (Win/Linux/Mac) | ✅ Funcionales | One-liner, zero deps |
| CI/CD | ✅ Excelente | Matrix testing, security scan, auto-publish |
| GitHub Actions | ✅ 3 workflows | CI, Release, Sync Installers |
| Docs | ✅ Completos | README, CONTRIBUTING, DEPLOYMENT, RELEASE, CHANGELOG |
| License | ✅ Apache 2.0 | Correcto |

---

## 2. Problemas Conocidos (Qué Arreglar)

### Prioridad ALTA (Bloquean monetización)

| # | Problema | Dónde | Impacto |
|---|---------|-------|---------|
| 1 | **Sin privacy policy / terms of service** | Flutter app | Bloquea publicación en Play Store / App Store |
| 2 | **Sin crash reporting** en mobile | Flutter app | No podemos diagnosticar crashes en producción |
| 3 | **iOS provisioning no configurado** | flutter_app/ios/ | No se puede publicar en App Store |
| 4 | **Test pollution en rate limiter** | tests/test_server_auth.py | Tests intermitentes en CI |
| 5 | **Errores de transcripción silenciosos** | Flutter audio_service.dart:66 | Usuario no sabe si falló el audio |

### Prioridad MEDIA (Mejoran calidad)

| # | Problema | Dónde | Impacto |
|---|---------|-------|---------|
| 6 | **Computer Use solo Windows** | computer_use.py | Limita mercado Linux/Mac |
| 7 | **Sin tests para Computer Use** | tests/ | Regresiones silenciosas |
| 8 | **Sin tests para Telegram bot** | tests/ | Regresiones silenciosas |
| 9 | **Regex frágil para costos** en history | Flutter history_screen.dart:83 | Parsing incorrecto ocasional |
| 10 | **Sin accessibility labels (Semantics)** | Flutter main.dart | Falla audit de accesibilidad |
| 11 | **agent_manager_sheet muy grande** | Flutter widgets/ | Dificulta mantenimiento |
| 12 | **MCP paths hardcodeados** | .mcp.json | No portable entre máquinas |

### Prioridad BAJA (Nice-to-have)

| # | Problema | Dónde | Impacto |
|---|---------|-------|---------|
| 13 | **Sin session resumption** para OpenAI/Gemini | providers/ | Pierden contexto al reconectar |
| 14 | **Plugin bash hereda privilegios del server** | plugins/executor.py | Riesgo si plugin malicioso |
| 15 | **ErrorBoundary usa inline styles** | frontend ErrorBoundary.tsx | Inconsistencia menor |
| 16 | **Frontend test coverage baja** | frontend/__tests__/ | Solo 3 archivos de test |

---

## 3. Plan de Estabilización (Sin Nuevas Features)

### Fase 1: Requisitos para Monetización (1-2 semanas)

- [ ] Crear **privacy policy** y **terms of service** (página web + in-app)
- [ ] Integrar **Firebase Crashlytics** en Flutter (Android + iOS)
- [ ] Configurar **iOS code signing** y provisioning profiles
- [ ] Surfacear errores de transcripción al usuario (TODO audit#6)
- [ ] Arreglar test pollution del rate limiter en CI

### Fase 2: Testing y Estabilidad (2-3 semanas)

- [ ] Tests para Computer Use (mock pyautogui/mss)
- [ ] Tests para Telegram bot (mock aiogram)
- [ ] Tests de UI/integration en Flutter (widget tests para chat, permissions)
- [ ] Tests frontend: chat rendering, voice state, store persistence
- [ ] Fix regex de costos en Flutter history (usar datos estructurados)
- [ ] Agregar Semantics/accessibility labels en Flutter

### Fase 3: Pulido (2 semanas)

- [ ] Refactorizar agent_manager_sheet en widgets más pequeños
- [ ] Hacer .mcp.json portable (env vars o config discovery)
- [ ] Documentar troubleshooting común en deployment
- [ ] Review de seguridad de plugins bash (sandbox más estricto)
- [ ] Optimizar bundle size frontend (lazy loading de panels pesados)

---

## 4. Estrategias de Monetización

### Opción A: SaaS Hosted (Recomendada)

**Modelo:** Rain Assistant como servicio cloud.

```
Plan Free:     $0/mes  — 50 mensajes/día, 1 agente, sin directors
Plan Pro:     $15/mes  — Ilimitado, 5 agentes, directors, marketplace
Plan Team:    $40/mes  — Todo Pro + 5 usuarios, shared memories, audit log
Plan Enterprise: Custom — Self-hosted, SSO, SLA, soporte dedicado
```

**Ventajas:**
- El usuario no necesita API keys propias
- Control total sobre costos (proxy a Claude/OpenAI con markup)
- Métricas de uso para pricing inteligente
- Onboarding simplificado (no hay que explicar qué es una API key)

**Requisitos:**
- Servidor central con multi-tenancy (ya existe `user_id` isolation)
- Billing integration (Stripe)
- Landing page con pricing
- Dashboard de admin

**Margen estimado:** Si el costo promedio por usuario es ~$3/mes en API calls, el margen es 80% en Plan Pro.

### Opción B: Marketplace de Plugins/Skills

**Modelo:** Rain es gratis, los plugins premium cuestan.

```
Plugins Free:    Comunidad, open source
Plugins Pro:     $2-10/plugin (one-time o subscription)
Plugin Bundles:  $20/bundle (ej: "Marketing Pack", "DevOps Pack")
Revenue share:   70% creador / 30% Rain
```

**Ventajas:**
- Ya existe el Marketplace y el sistema de plugins
- Bajo costo operacional (los plugins corren en la máquina del usuario)
- Crea ecosistema y comunidad
- Escala con la cantidad de creadores

**Requisitos:**
- Sistema de pagos en el marketplace
- Verificación de plugins (security review)
- Portal para creadores de plugins
- Sistema de reviews/ratings

### Opción C: API/Platform (B2B)

**Modelo:** Rain como plataforma para empresas.

```
API Access:        $0.01/request (metered)
White-label:       $500/mes (tu marca, nuestro engine)
Custom Deployment: $2000+ setup + $200/mes hosting
```

**Ventajas:**
- Revenue alto por cliente
- Contratos largos (12+ meses)
- El código ya soporta multi-provider y multi-user

**Requisitos:**
- API documentation (OpenAPI/Swagger ya incluido por FastAPI)
- SDKs o ejemplos de integración
- SLAs y uptime guarantees
- Soporte técnico dedicado

### Opción D: Modelo Híbrido (Más Realista)

**Combinación recomendada para empezar:**

1. **Core gratuito** (self-hosted, open source, Apache 2.0) — trae usuarios
2. **Rain Cloud** ($15/mes) — hosted version sin fricción
3. **Plugins premium** en marketplace — ingresos adicionales
4. **Soporte/consultoría** para empresas — high-ticket

**Primer paso:** Lanzar **Rain Cloud** con Stripe. Es el camino más rápido a revenue.

### Opción E: Licencia Dual / Open Core

**Modelo:** Community Edition (gratis, limitada) vs Pro Edition (paga, completa).

```
Community (Apache 2.0):
  - Chat básico, 1 provider, sin directors, sin computer use
  - Plugins comunitarios

Pro ($99/año o $12/mes):
  - Multi-provider, directors, computer use, marketplace completo
  - Prioridad en soporte
  - Features avanzados (RAG, memories, alter egos)
```

**Ventajas:**
- El código ya existe, solo se limitan features por licencia
- Sin infraestructura cloud necesaria
- Los usuarios pagan por desbloquear, no por hosting

---

## 5. Análisis Competitivo Rápido

| Competidor | Precio | Diferenciador de Rain |
|-----------|--------|----------------------|
| **Cursor** | $20/mes | Rain es multi-provider, tiene plugins, directors, voice |
| **Continue.dev** | Gratis (OSS) | Rain tiene TTS, computer use, marketplace, mobile app |
| **Aider** | Gratis (OSS) | Rain tiene UI web, Flutter app, directors, alter egos |
| **Windsurf** | $15/mes | Rain es self-hostable, extensible via plugins |
| **ChatGPT** | $20/mes | Rain ejecuta código local, tiene computer use, es customizable |

**Ventaja competitiva principal:** Rain es el único que combina:
- Self-hosted + Cloud option
- 4 providers de IA
- Voice con 4 modos
- Computer Use
- Plugin system extensible
- App mobile nativa
- Agentes autónomos (Directors)
- Todo open source (Apache 2.0)

---

## 6. Métricas Actuales del Proyecto

| Métrica | Valor |
|---------|-------|
| Versión | 1.0.13 |
| Commits totales | 100+ |
| Releases | 13 |
| Tests backend | 70+ |
| Tests Flutter | 31 |
| Tests frontend | 3 archivos |
| Líneas server.py | 2600+ |
| Componentes React | 40+ |
| Screens Flutter | 14 |
| Providers Flutter | 9 |
| Traducciones (i18n) | 360+ keys × 2 idiomas |
| Formatos RAG soportados | 30+ |
| Tools disponibles | 20+ (core + meta-tools) |
| CI/CD workflows | 3 |
| Plataformas | Web, Android, iOS, Telegram, Desktop (via browser) |

---

## 7. Decisión Recomendada

### Qué hacer AHORA:

1. **Congelar features** — No más integraciones nuevas
2. **Ejecutar Fase 1** — Privacy policy, crash reporting, iOS signing, fix tests
3. **Ejecutar Fase 2** — Aumentar test coverage en las 3 plataformas
4. **Publicar en Play Store** — Android está listo, solo falta privacy policy
5. **Preparar Rain Cloud** — Landing page + Stripe + servidor hosted
6. **Lanzar beta privada** — 10-20 usuarios, medir uso y costos reales

### Qué NO hacer:

- ❌ Agregar más providers de IA
- ❌ Nuevas features en el frontend
- ❌ Más tipos de plugins
- ❌ Expandir computer use a Linux/Mac (todavía)
- ❌ Agregar más idiomas (todavía)

### Timeline sugerido:

```
Semana 1-2:   Fase 1 (requisitos legales + crash reporting)
Semana 3-4:   Fase 2 (testing + estabilidad)
Semana 5-6:   Fase 3 (pulido) + Play Store submit
Semana 7-8:   Rain Cloud MVP (landing + Stripe + hosting)
Semana 9-10:  Beta privada + iteración sobre feedback
Semana 11-12: Lanzamiento público
```

---

*Este documento es el punto de partida para la fase de estabilización. Cada item tiene un estado claro y una prioridad. No se agrega nada nuevo — solo se mejora lo que ya existe.*
