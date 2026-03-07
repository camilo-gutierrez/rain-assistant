# Rain Assistant — Agent OS Evolution Roadmap

> **Fecha:** 7 de marzo de 2026
> **Vision:** Evolucionar Rain de asistente personal a Agent OS — una plataforma completa para trabajo autonomo con agentes de IA.

---

## Tesis Central

En 5 anos los frameworks de agentes dejaran de ser "otro wrapper de LLM" y se convertiran en una nueva capa de software: algo entre middleware, runtime y sistema operativo para trabajo autonomo.

El valor competitivo se movera del modelo al runtime: planificacion, memoria, tracing, politicas, permisos, costos y coordinacion entre agentes. El modelo sera una pieza reemplazable.

Rain ya tiene las bases para competir en ese futuro. Este documento traza el camino.

---

## Donde Esta Rain Hoy

### Fortalezas actuales (lo que ya tenemos)

| Capacidad | Estado | Detalle |
|-----------|--------|---------|
| Modelo reemplazable | Listo | Factory pattern, 4 providers (Claude, OpenAI, Gemini, Ollama) |
| MCP como consumidor | Listo | Conectado a tools y datos externos via MCP |
| Agente personal/local | Listo | Gateway local conectado a archivos, calendar, email, smart home, browser |
| Sistema de permisos | Listo | GREEN/YELLOW/RED + aprobacion inline en Telegram |
| Multi-canal | Listo | Web + Telegram + voz + app mobile |
| Plugin system | Listo | YAML, 3 tipos de ejecucion, marketplace, hot-reload |
| Memoria semantica | Listo | Embeddings, encrypted, per-user |
| RAG/Documentos | Listo | Hybrid search, BM25, reranking, 30+ formatos |
| Computer Use | Listo | 8 fases, Windows, OCR, multi-monitor, recording |
| Directors (agentes autonomos) | Listo | Cron scheduling, inbox, delegacion |
| Alter Egos | Listo | Personalidades switcheables |
| i18n | Listo | en/es, 360+ keys |

### Gaps criticos (lo que nos falta)

| Capacidad | Estado | Impacto |
|-----------|--------|---------|
| Comunicacion agent-to-agent | No existe | Rain es un solo agente, no puede delegar ni recibir delegaciones de otros agentes |
| Autonomia por eventos | Parcial | Directors tienen cron, pero no hay event-driven triggers (webhooks, watchers) |
| Tracing/observabilidad | Basico | Metricas de tokens/costo pero sin trazas estructuradas (spans, logs auditables) |
| Sandbox/aislamiento | No existe | Computer Use y bash corren directo en la maquina del usuario |
| Memoria compartida | No existe | Memoria por instancia, sin federacion ni sync entre agentes |
| Policy engine | No existe | Permisos estaticos, sin politicas dinamicas (presupuesto, horarios, limites) |
| Rain como MCP server | No existe | Solo consumimos MCP, no exponemos capacidades a otros agentes |
| Fleet management | No existe | No hay gestion de multiples agentes coordinados |

---

## Roadmap por Fases

### FASE 0: Estabilizacion (Ahora — Q1 2026)

> **Objetivo:** Solidificar lo que ya existe antes de agregar nuevas capas.

**Ya documentado en** `docs/PROJECT_STATUS.md`. Resumen:

- [ ] Privacy policy + terms of service
- [ ] Crash reporting mobile (Crashlytics)
- [ ] iOS provisioning
- [ ] Fix test pollution rate limiter
- [ ] Tests: Computer Use, Telegram, UI Flutter, frontend
- [ ] Refactor agent_manager_sheet
- [ ] Security review plugins bash
- [ ] Publicar en Play Store

**Criterio de salida:** Tests >80% coverage en backend, app en Play Store, zero crashes criticos en 2 semanas.

---

### FASE 1: Fortalecer el Runtime (Q2-Q3 2026)

> **Objetivo:** Convertir Rain de "asistente que responde" a "runtime con gobierno".

#### 1.1 Tracing Estructurado

- [ ] Cada tool call registra: timestamp, duracion, costo, resultado, agent_id
- [ ] Formato compatible con OpenTelemetry (spans + traces)
- [ ] Endpoint `/api/traces` para consultar historial de ejecucion
- [ ] UI: timeline visual de ejecucion por conversacion
- [ ] Exportacion: JSON, CSV para analisis externo

**Archivos a modificar:** `tools/executor.py`, `providers/base.py`, nuevo `tracing/` module, frontend panel.

#### 1.2 Policy Engine Basico

- [ ] Reglas configurables en YAML/JSON (`~/.rain-assistant/policies.yaml`)
- [ ] Politicas soportadas:
  - Presupuesto maximo por dia/semana/mes (en USD)
  - Horarios permitidos de ejecucion
  - Tools bloqueados por contexto
  - Limites de tokens por conversacion
  - Restricciones por provider (ej: "solo Ollama para tareas internas")
- [ ] Enforcement en el tool executor y en el provider loop
- [ ] Notificacion al usuario cuando se alcanza un limite
- [ ] UI: panel de politicas en Settings

**Archivos nuevos:** `policies/engine.py`, `policies/rules.py`

#### 1.3 Sandbox para Ejecucion

- [ ] Modo sandbox para bash: ejecucion en contenedor Docker efimero
- [ ] Modo sandbox para Computer Use: VM ligera o contenedor con display virtual
- [ ] Filesystem isolation: directorio de trabajo aislado por tarea
- [ ] Network isolation opcional (sin acceso a internet para tareas sensibles)
- [ ] Rollback: snapshot antes de ejecutar, restaurar si falla
- [ ] Flag `--sandbox` en CLI para activar modo seguro

**Archivos nuevos:** `sandbox/container.py`, `sandbox/snapshot.py`

#### 1.4 Audit Log Completo

- [ ] Log inmutable de todas las acciones (tool calls, permisos, cambios de config)
- [ ] Formato estructurado con hash chain (cada entrada referencia la anterior)
- [ ] Retencion configurable (30/60/90 dias)
- [ ] Endpoint `/api/audit` con filtros por fecha, tipo, agente
- [ ] Exportacion para compliance

**Archivos nuevos:** `audit/logger.py`, `audit/storage.py`

---

### FASE 2: Autonomia Real (Q4 2026 — Q1 2027)

> **Objetivo:** Rain hace cosas sin que el usuario inicie conversacion.

#### 2.1 Event-Driven Triggers

- [ ] Webhook receiver: endpoint `/api/webhooks/{trigger_id}` que dispara un Director
- [ ] File watcher: monitorear cambios en directorios y ejecutar acciones
- [ ] Email trigger: nuevo email con cierto subject/label activa un agente
- [ ] Calendar trigger: X minutos antes de un evento, ejecutar preparacion
- [ ] Git trigger: push/PR en un repo dispara revision automatica
- [ ] Custom triggers via plugins

**Archivos a modificar:** `directors/executor.py`, nuevo `triggers/` module.

#### 2.2 Directors Avanzados

- [ ] Templates pre-construidos:
  - "Morning briefing": resume emails, calendar, noticias relevantes
  - "Repo watcher": revisa PRs, issues, sugiere acciones
  - "Expense tracker": categoriza gastos de emails/receipts
  - "Learning digest": resume articulos guardados
  - "Meeting prep": antes de cada reunion, prepara contexto
- [ ] Encadenamiento de Directors: output de uno alimenta al siguiente
- [ ] Conditional logic: if/else basado en resultados intermedios
- [ ] Retry con backoff: si falla, reintentar con delay exponencial
- [ ] Dead letter queue: tareas que fallan N veces van a revision manual

**Archivos a modificar:** `directors/executor.py`, `directors/builtin.py`, `directors/task_queue.py`

#### 2.3 Estado Persistente por Tarea

- [ ] Cada tarea autonoma tiene su propio contexto (no comparte conversacion)
- [ ] Checkpoints: guardar estado intermedio para resume despues de fallos
- [ ] Variables de tarea: key-value store por ejecucion
- [ ] Historial de ejecuciones con diff de resultados

**Archivos nuevos:** `directors/state.py`, `directors/checkpoints.py`

---

### FASE 3: Multi-Agente (Q2-Q3 2027)

> **Objetivo:** Multiples agentes Rain que se comunican y delegan trabajo entre si.

#### 3.1 Rain como MCP Server

- [ ] Exponer capacidades de Rain via MCP (tools, memoria, documentos)
- [ ] Otros agentes (Claude Code, Cursor, custom) pueden llamar a Rain
- [ ] Autenticacion MCP: tokens por agente externo
- [ ] Rate limiting por agente consumidor
- [ ] Scoping: definir que tools/datos expone cada endpoint MCP

**Archivos nuevos:** `mcp_server/` module

#### 3.2 Handoffs Entre Agentes

- [ ] Protocolo de delegacion: agente A envia tarea a agente B con contexto
- [ ] Handoff con contexto: memoria relevante, archivos, instrucciones
- [ ] Callback: agente B notifica a agente A cuando termina
- [ ] Supervision: el usuario ve la cadena de delegaciones y puede intervenir
- [ ] Timeout + fallback: si agente B no responde en X tiempo, escalar

**Archivos nuevos:** `agents/handoff.py`, `agents/protocol.py`

#### 3.3 Memoria Compartida

- [ ] Store de memoria federado: multiples instancias de Rain comparten conocimiento
- [ ] Namespaces: memoria privada vs compartida vs por-equipo
- [ ] Sync protocol: conflict resolution para escrituras concurrentes
- [ ] Permisos por namespace (quien puede leer/escribir que)

**Archivos a modificar:** `memories/storage.py`, nuevo `memories/federation.py`

#### 3.4 Comunicacion Agent-to-Agent

- [ ] Protocolo de mensajeria entre agentes (basado en MCP o custom)
- [ ] Discovery: un agente puede encontrar otros agentes disponibles
- [ ] Negociacion: agentes acuerdan formato de entrada/salida
- [ ] Logging completo de todas las comunicaciones inter-agente

**Archivos nuevos:** `agents/messaging.py`, `agents/discovery.py`

---

### FASE 4: Plataforma y Gobierno (Q4 2027 — Q2 2028)

> **Objetivo:** Gestionar flotas de agentes con identidad, gobierno y SLAs.

#### 4.1 Fleet Management

- [ ] Dashboard central: ver todos los agentes activos, su estado, carga
- [ ] Deploy de agentes: crear nuevas instancias desde templates
- [ ] Scheduling inteligente: asignar tareas al agente menos cargado
- [ ] Cuotas: limites de recursos por agente (tokens, CPU, storage)
- [ ] Health checks: detectar agentes caidos, reiniciar automaticamente

**Archivos nuevos:** `fleet/manager.py`, `fleet/scheduler.py`, `fleet/health.py`

#### 4.2 Identidad y Roles

- [ ] Cada agente tiene identidad unica (certificado o API key)
- [ ] Roles: admin, operator, viewer, executor
- [ ] RBAC: permisos granulares por rol (que tools, que datos, que acciones)
- [ ] Multi-tenant: aislamiento completo entre organizaciones
- [ ] SSO integration (SAML, OIDC) para empresas

**Archivos nuevos:** `identity/` module

#### 4.3 Evaluacion y Calidad

- [ ] Evals automaticos: correr benchmarks periodicos contra los agentes
- [ ] Scoring: calidad de respuestas, tiempo de ejecucion, costo
- [ ] A/B testing: comparar configuraciones de agentes
- [ ] Regression detection: alertar si la calidad baja
- [ ] Dashboard de metricas de calidad

**Archivos nuevos:** `evals/` module

#### 4.4 Marketplace de Agentes

- [ ] Ademas de plugins, publicar agentes completos (Director templates + config)
- [ ] Rating y reviews de agentes
- [ ] Categorias: productividad, desarrollo, marketing, finanzas, etc.
- [ ] Revenue share para creadores de agentes
- [ ] Verificacion de seguridad antes de publicar

**Archivos a modificar:** `marketplace/registry.py`, nuevo `marketplace/agents.py`

---

### FASE 5: Agent OS (Q3 2028 — 2031)

> **Objetivo:** Rain es una capa de software reconocida — un OS para agentes de IA.

#### 5.1 Stack Completo

```
+--------------------------------------------------+
|              Interfaz Humana                      |
|   Web / Mobile / Telegram / Voice / API           |
+--------------------------------------------------+
|              Observabilidad                        |
|   Tracing / Metricas / Audit / Evals              |
+--------------------------------------------------+
|              Tools y Plugins                       |
|   Built-in / Marketplace / MCP / Custom           |
+--------------------------------------------------+
|              Policy & Security                     |
|   Permisos / Sandbox / RBAC / Policies / Audit    |
+--------------------------------------------------+
|              Runtime                               |
|   Scheduling / State / Checkpoints / Handoffs     |
+--------------------------------------------------+
|              Protocolo                             |
|   MCP / Agent-to-Agent / Discovery / Federation   |
+--------------------------------------------------+
|              Modelo                                |
|   Claude / GPT / Gemini / Ollama / Custom         |
+--------------------------------------------------+
```

#### 5.2 Objetivos a 5 Anos

- [ ] Rain maneja flotas de 100+ agentes coordinados
- [ ] Agentes negocian entre si sin intervencion humana (con supervision)
- [ ] Interoperabilidad total via MCP y estandares abiertos (AAIF)
- [ ] Sandbox obligatorio por defecto en toda ejecucion
- [ ] Policy engine con compliance (SOC2, GDPR)
- [ ] Marketplace con ecosistema activo de creadores
- [ ] Self-healing: agentes que detectan y reparan sus propios fallos
- [ ] Cost optimization: routing inteligente al modelo mas barato que cumpla

---

## Prediccion de la Industria

### Timeline del mercado de Agent OS

| Periodo | Lo que pasara | Donde debe estar Rain |
|---------|---------------|----------------------|
| 2026 | Explosion de frameworks y clones | Estable, diferenciado por runtime y multi-canal |
| 2027 | Estandarizacion (MCP, AAIF, protocolos) | Compatible con estandares, MCP server + consumer |
| 2028 | Consolidacion en plataformas con gobierno | Fleet management, identidad, policies |
| 2029 | Agent-to-agent como norma | Comunicacion inter-agente nativa |
| 2030 | "Agent OS" es termino normal en empresas | Rain como plataforma reconocida |
| 2031 | Stack completo: modelo + protocolo + runtime + policy + tools + observabilidad | Dominar al menos 2-3 capas del stack |

### Dos familias de agentes

1. **Agente personal/local** (donde Rain empezo): gateway siempre encendido, conectado a tus apps, archivos, dispositivos. Reactivo + semi-autonomo.

2. **Agent runtime/OS** (hacia donde Rain evoluciona): procesos autonomos por eventos, horarios, pipelines y objetivos persistentes.

Rain puede cubrir ambas familias porque empezo como agente personal y tiene la arquitectura para escalar a runtime.

---

## Principios de Diseno

Estos principios guian todas las decisiones de este roadmap:

1. **Autonomia util > demos impresionantes.** Solo sobreviven los que resuelven cosas aburridas pero criticas: confiabilidad, costo, recuperacion de errores, trazabilidad.

2. **Seguridad es requisito, no feature.** Permisos granulares, sandbox obligatorio, firmas de plugins, auditoria completa, policy engine, rollback.

3. **Interoperabilidad sobre ecosistema cerrado.** Protocolos abiertos (MCP, AAIF). Rain habla el mismo idioma que el resto del mundo.

4. **El modelo es reemplazable, el runtime no.** La ventaja esta en planificacion, memoria, tracing, politicas, permisos y coordinacion.

5. **Incremental, no big-bang.** Cada fase entrega valor por si sola. No hay que esperar 5 anos para que Rain sea util — ya lo es.

---

## Como Usar Este Documento

- Cada fase tiene checkboxes. Marcarlos conforme se completen.
- Los "archivos a modificar/crear" son orientativos. La implementacion puede cambiar.
- Revisar este documento cada 3-6 meses y ajustar segun el estado del mercado.
- Las fases no son rigidas: si una oportunidad de Fase 3 se vuelve urgente, se puede adelantar.

---

## Documentos Relacionados

- [PROJECT_STATUS.md](PROJECT_STATUS.md) — Estado actual del proyecto y plan de estabilizacion
- [OPEN_CORE_PLAN.md](OPEN_CORE_PLAN.md) — Modelo de negocio y monetizacion
- [RAG_ROADMAP.md](RAG_ROADMAP.md) — Evolucion del sistema RAG/documentos
- [COMPUTER_USE_ROADMAP.md](COMPUTER_USE_ROADMAP.md) — Evolucion de Computer Use

---

*Este roadmap es un documento vivo. Refleja nuestra vision de hacia donde va la industria y como Rain se posiciona para estar ahi. Se actualiza conforme avanzamos.*
