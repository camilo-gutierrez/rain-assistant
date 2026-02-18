# Rain Assistant — Flutter Client Specification

> Documento de referencia para implementar el cliente Flutter de Rain Assistant.
> El backend (FastAPI + WebSocket) no requiere modificaciones.
> Flutter es un cliente alternativo que consume la misma API que el frontend web.

---

## 1. Arquitectura General

```
┌─────────────────────────────────────────────────┐
│               Rain Backend (Python)             │
│  FastAPI · WebSocket · Whisper · SQLite · Claude │
│  Puerto: 8000                                    │
├──────────────┬──────────────────────────────────┤
│  REST API    │  WebSocket /ws                    │
│  /api/*      │  JSON bidireccional               │
└──────┬───────┴──────────┬───────────────────────┘
       │                  │
  ┌────▼────┐      ┌──────▼──────┐
  │ Web     │      │ Flutter     │
  │ Next.js │      │ (este doc)  │
  └─────────┘      └─────────────┘
```

**Principio**: El backend es completamente agnóstico del cliente. Ambos clientes
hablan el mismo protocolo JSON sobre WebSocket + REST con Bearer token.

---

## 2. Flujo de Conexión

```
 Flutter App                          Backend
     │                                   │
     │  1. POST /api/auth {pin}          │
     │ ─────────────────────────────────>│
     │  ← {token}                        │
     │                                   │
     │  2. WebSocket /ws?token=xxx       │
     │ ═════════════════════════════════>│
     │  ← {type:"status", text:"..."}   │
     │  ← {type:"api_key_loaded",...}    │ (si hay key en config)
     │                                   │
     │  3. set_api_key (si no hay)       │
     │ ─────────────────────────────────>│
     │                                   │
     │  4. set_cwd {path, agent_id}      │
     │ ─────────────────────────────────>│
     │  ← {type:"status", cwd:"..."}    │
     │                                   │
     │  5. send_message {text}           │
     │ ─────────────────────────────────>│
     │  ← assistant_text (chunks)        │
     │  ← tool_use                       │
     │  ← tool_result                    │
     │  ← result (final + métricas)      │
     │                                   │
     │  ↔ ping/pong cada 30s             │
     └───────────────────────────────────┘
```

---

## 3. Autenticación

### POST /api/auth

Obtiene un token Bearer a partir del PIN.

**Request:**
```json
{
  "pin": "123456"
}
```

**Responses:**

| Status | Body | Descripción |
|--------|------|-------------|
| 200 | `{"token": "abc123..."}` | Token válido por 24h |
| 401 | `{"error": "Invalid PIN", "remaining_attempts": 2}` | PIN incorrecto |
| 429 | `{"error": "Too many failed attempts...", "locked": true, "remaining_seconds": 300}` | IP bloqueada 5 min |

**Notas:**
- PIN: string, 1-20 caracteres
- Token: URL-safe base64, ~43 caracteres
- Máximo 3 intentos fallidos → lockout 5 minutos por IP
- El token debe almacenarse en secure storage (no en texto plano)

### POST /api/logout

Revoca el token actual.

```
Authorization: Bearer {token}
```
→ `{"logged_out": true}`

### POST /api/logout-all

Revoca TODOS los tokens activos. Requiere PIN.

```
Authorization: Bearer {token}
Body: {"pin": "123456"}
```
→ `{"logged_out_all": true, "tokens_revoked": 3}`

---

## 4. Protocolo WebSocket

### Conexión

```
URL: ws://{host}:{port}/ws?token={urlEncoded(token)}
     wss:// para HTTPS
```

### Códigos de cierre

| Código | Significado | Acción del cliente |
|--------|-------------|-------------------|
| 4001 | Token inválido/expirado | Borrar token → pantalla de PIN |
| 4002 | Idle timeout (10 min sin actividad) | Auto-reconectar en 1s |
| Otro | Error de red | Reconectar con backoff (3s), max 3 intentos |

### Heartbeat

- El servidor envía `{"type": "ping", "ts": 1234567890.123}` cada **30 segundos**
- El cliente DEBE responder `{"type": "pong"}` inmediatamente
- Si no hay actividad por **10 minutos**, el servidor cierra con código 4002

---

## 5. Mensajes WebSocket: Cliente → Servidor

### send_message
Envía texto del usuario a un agente.
```json
{
  "type": "send_message",
  "text": "Hola Rain, crea un archivo hello.py",
  "agent_id": "agent_abc123"
}
```
- `text`: máx 10,000 caracteres
- `agent_id`: máx 100 caracteres

### set_cwd
Establece el directorio de trabajo de un agente. Crea el agente si no existe.
```json
{
  "type": "set_cwd",
  "path": "/home/user/projects/myapp",
  "agent_id": "agent_abc123",
  "session_id": "ses_xyz789"
}
```
- `path`: máx 500 caracteres
- `session_id`: opcional, para reanudar conversación previa

### set_api_key
Configura la clave de API y el proveedor.
```json
{
  "type": "set_api_key",
  "key": "sk-ant-...",
  "provider": "claude",
  "model": "auto"
}
```
- `provider`: `"claude"` | `"openai"` | `"gemini"`
- `key`: máx 500 caracteres
- `model`: ID del modelo (ver sección 12)

### set_transcription_lang
Cambia el idioma de transcripción de audio.
```json
{
  "type": "set_transcription_lang",
  "lang": "es"
}
```

### interrupt
Cancela la operación en curso de un agente.
```json
{
  "type": "interrupt",
  "agent_id": "agent_abc123"
}
```

### destroy_agent
Destruye un agente y libera sus recursos.
```json
{
  "type": "destroy_agent",
  "agent_id": "agent_abc123"
}
```

### permission_response
Responde a una solicitud de permiso.
```json
{
  "type": "permission_response",
  "request_id": "perm_a1b2c3d4",
  "agent_id": "agent_abc123",
  "approved": true,
  "pin": "123456"
}
```
- `pin`: requerido solo para permisos nivel RED
- Timeout: 5 minutos para responder (si no, se deniega automáticamente)

### set_mode
Cambia el modo de un agente.
```json
{
  "type": "set_mode",
  "agent_id": "agent_abc123",
  "mode": "computer_use"
}
```
- `mode`: `"coding"` | `"computer_use"`

### emergency_stop
Detención de emergencia del modo computer use.
```json
{
  "type": "emergency_stop",
  "agent_id": "agent_abc123"
}
```

### pong
Respuesta al ping del servidor.
```json
{
  "type": "pong"
}
```

---

## 6. Mensajes WebSocket: Servidor → Cliente

### status
Estado de conexión o del agente.
```json
{
  "type": "status",
  "text": "Connected to Claude SDK",
  "cwd": "/home/user/projects",
  "agent_id": "agent_abc123"
}
```
- `cwd`: puede ser `null` si aún no se ha establecido
- `agent_id`: puede ser `null` en el mensaje inicial

### api_key_loaded
El servidor ya tiene una API key configurada (del archivo de config).
```json
{
  "type": "api_key_loaded",
  "provider": "claude"
}
```
- Si llega este mensaje, saltar la pantalla de API key → ir directo a file browser

### assistant_text
Chunk de texto de la respuesta del asistente (streaming).
```json
{
  "type": "assistant_text",
  "text": "Claro, voy a crear ",
  "agent_id": "agent_abc123"
}
```
- Llegan múltiples mensajes que se van **acumulando** para formar la respuesta completa
- Cada chunk es un fragmento parcial (puede ser una palabra, una línea, etc.)

### tool_use
El agente va a ejecutar una herramienta.
```json
{
  "type": "tool_use",
  "tool": "write",
  "input": {"file_path": "/tmp/hello.py", "content": "print('hello')"},
  "id": "toolu_abc123",
  "agent_id": "agent_abc123"
}
```

### tool_result
Resultado de la ejecución de una herramienta.
```json
{
  "type": "tool_result",
  "content": "File written successfully",
  "is_error": false,
  "tool_use_id": "toolu_abc123",
  "agent_id": "agent_abc123"
}
```
- `tool_use_id` vincula con el `id` del `tool_use` correspondiente

### permission_request
El agente necesita permiso para ejecutar una herramienta.
```json
{
  "type": "permission_request",
  "request_id": "perm_a1b2c3d4",
  "agent_id": "agent_abc123",
  "tool": "bash",
  "input": {"command": "rm -rf /tmp/old"},
  "level": "red",
  "reason": "Comando destructivo que elimina archivos"
}
```

**Niveles de permiso:**

| Nivel | Comportamiento | UI esperada |
|-------|---------------|-------------|
| `green` | Auto-aprobado (nunca llega al cliente) | — |
| `yellow` | Requiere aprobación del usuario | Dialog con Aprobar/Denegar |
| `red` | Requiere aprobación + PIN | Dialog con input de PIN + Aprobar/Denegar |
| `computer` | Acción de computer use | Dialog con preview de la acción |

### result
La conversación/turno terminó. Incluye métricas.
```json
{
  "type": "result",
  "text": "completed",
  "usage": {
    "input_tokens": 1523,
    "output_tokens": 487
  },
  "cost": 0.0234,
  "duration_ms": 4521,
  "num_turns": 3,
  "is_error": false,
  "session_id": "ses_xyz789",
  "agent_id": "agent_abc123"
}
```
- `session_id`: guardar para reanudar conversación en reconexión
- `cost`: en USD, redondeado a 4 decimales (puede ser `null`)
- Todos los campos excepto `type`, `text`, `is_error`, `agent_id` son opcionales

### error
Error durante el procesamiento.
```json
{
  "type": "error",
  "text": "API key is invalid",
  "agent_id": "agent_abc123"
}
```

### model_info
Información del modelo activo.
```json
{
  "type": "model_info",
  "model": "claude-sonnet-4-5-20250929",
  "agent_id": "agent_abc123"
}
```

### rate_limits
Límites de la API de Anthropic (solo provider Claude).
```json
{
  "type": "rate_limits",
  "limits": {
    "requests-limit": 50,
    "requests-remaining": 48,
    "requests-reset": "2024-01-15T10:30:00Z",
    "input-tokens-limit": 100000,
    "input-tokens-remaining": 95000,
    "input-tokens-reset": "2024-01-15T10:30:00Z",
    "output-tokens-limit": 50000,
    "output-tokens-remaining": 47000,
    "output-tokens-reset": "2024-01-15T10:30:00Z"
  },
  "agent_id": "agent_abc123"
}
```

### agent_destroyed
Confirmación de que un agente fue destruido.
```json
{
  "type": "agent_destroyed",
  "agent_id": "agent_abc123"
}
```

### mode_changed
Confirmación de cambio de modo.
```json
{
  "type": "mode_changed",
  "agent_id": "agent_abc123",
  "mode": "computer_use",
  "display_info": {
    "screen_width": 1920,
    "screen_height": 1080,
    "scaled_width": 1280,
    "scaled_height": 720,
    "scale_factor": 1.5
  }
}
```

### computer_screenshot
Screenshot del modo computer use.
```json
{
  "type": "computer_screenshot",
  "agent_id": "agent_abc123",
  "image": "iVBORw0KGgo...",
  "action": "left_click",
  "description": "Click en el botón Submit",
  "iteration": 3
}
```
- `image`: PNG codificado en base64
- `action`: `"initial"`, `"left_click"`, `"type"`, `"scroll"`, `"key"`, etc.

### computer_action
Acción que se va a ejecutar en computer use.
```json
{
  "type": "computer_action",
  "agent_id": "agent_abc123",
  "tool": "computer",
  "action": "left_click",
  "input": {"coordinate": [640, 480]},
  "description": "Click en coordenadas (640, 480)",
  "iteration": 3
}
```

### ping
Heartbeat del servidor.
```json
{
  "type": "ping",
  "ts": 1705312200.123
}
```
→ El cliente debe responder con `{"type": "pong"}`

---

## 7. API REST

Todas las rutas requieren `Authorization: Bearer {token}` excepto `/api/auth`.

### File Browser

**GET /api/browse?path={path}**

```json
// Response 200
{
  "current": "/home/user/projects",
  "entries": [
    {"name": "..", "path": "/home/user", "is_dir": true, "size": 0},
    {"name": "src", "path": "/home/user/projects/src", "is_dir": true, "size": 0},
    {"name": "main.py", "path": "/home/user/projects/main.py", "is_dir": false, "size": 1234}
  ]
}
```
- `path` default: `"~"` (home del usuario)
- Máximo 200 entries
- Los archivos ocultos (`.xxx`) se excluyen
- Seguridad: solo permite rutas bajo el home del usuario

### Audio Upload

**POST /api/upload-audio**

- Content-Type: `multipart/form-data`
- Campo: `audio` (archivo)
- Formatos: `.webm`, `.wav`, `.ogg`, `.mp4`
- Tamaño máximo: **25 MB**
- Cuota diaria: **60 minutos** de audio por token

```json
// Response 200
{"text": "Texto transcrito del audio"}

// Response 429 (cuota excedida)
{"error": "Daily audio quota exceeded (60 min/day)"}

// Response 413 (archivo muy grande)
{"error": "File too large (max 25MB)"}
```

### Text-to-Speech

**POST /api/synthesize**

```json
// Request
{
  "text": "Hola, soy Rain tu asistente",
  "voice": "es-MX-DaliaNeural",
  "rate": "+0%"
}
```

- `text`: máx 5,000 caracteres
- `rate`: ajuste de velocidad, ej: `"+10%"`, `"-20%"`, `"+0%"`
- Cuota diaria: **100,000 caracteres** por token
- Response: `audio/mpeg` (MP3 binario) o `204 No Content` (si el texto es mayormente código)

**Voces disponibles:**

| ID | Idioma | Género |
|----|--------|--------|
| `es-MX-DaliaNeural` | Español (México) | Femenina |
| `es-MX-JorgeNeural` | Español (México) | Masculina |
| `en-US-JennyNeural` | Inglés (US) | Femenina |
| `en-US-GuyNeural` | Inglés (US) | Masculina |

### Message History

**GET /api/messages?cwd={cwd}&agent_id={agentId}**

Carga mensajes persistidos de una sesión anterior.

```json
// Response
{
  "messages": [
    {
      "id": 1,
      "role": "user",
      "type": "text",
      "content": {"text": "Hola"},
      "timestamp": 1705312200
    },
    {
      "id": 2,
      "role": "assistant",
      "type": "assistant_text",
      "content": {"text": "¡Hola! Soy Rain..."},
      "timestamp": 1705312205
    },
    {
      "id": 3,
      "role": "tool",
      "type": "tool_use",
      "content": {"tool": "bash", "input": {"command": "ls"}, "id": "toolu_xxx"},
      "timestamp": 1705312210
    },
    {
      "id": 4,
      "role": "tool",
      "type": "tool_result",
      "content": {"content": "file1.txt\nfile2.txt", "is_error": false, "tool_use_id": "toolu_xxx"},
      "timestamp": 1705312211
    },
    {
      "id": 5,
      "role": "assistant",
      "type": "result",
      "content": {"cost": 0.0123, "duration_ms": 3200, "num_turns": 2, "session_id": "ses_abc"},
      "timestamp": 1705312215
    }
  ]
}
```

**Tipos de mensajes en historial:**

| type | role | content |
|------|------|---------|
| `text` | `user` | `{text: string}` |
| `assistant_text` | `assistant` | `{text: string}` |
| `tool_use` | `tool` | `{tool: string, input: object, id: string}` |
| `tool_result` | `tool` | `{content: string, is_error: bool, tool_use_id: string}` |
| `result` | `assistant` | `{cost?, duration_ms?, num_turns?, session_id?}` |
| `error` | `assistant` | `{text: string}` |

**DELETE /api/messages?cwd={cwd}&agent_id={agentId}**
→ `{"deleted": 15}`

### Metrics

**GET /api/metrics**

```json
{
  "totals": {
    "all_time": {
      "cost": 12.50,
      "sessions": 45,
      "avg_duration_ms": 5200,
      "avg_cost": 0.278,
      "total_turns": 320,
      "total_input_tokens": 1500000,
      "total_output_tokens": 750000
    },
    "today": { /* misma estructura */ },
    "this_week": { /* misma estructura */ },
    "this_month": { /* misma estructura */ }
  },
  "by_hour": [{"hour": 14, "cost": 0.50, "sessions": 3}],
  "by_dow": [{"name": "Monday", "cost": 2.10, "sessions": 8}],
  "by_day": [{"day": "2024-01-15", "cost": 1.20, "sessions": 5, "duration_ms": 25000}],
  "by_month": [{"month": "2024-01", "cost": 12.50, "sessions": 45, "duration_ms": 234000}]
}
```

### Conversation History

**GET /api/history**

Lista conversaciones guardadas (máximo 5).

```json
{
  "conversations": [
    {
      "id": "conv_1705312200000",
      "createdAt": 1705312200000,
      "updatedAt": 1705315800000,
      "label": "Crear API REST",
      "cwd": "/home/user/projects/api",
      "messageCount": 24,
      "preview": "Hola Rain, necesito crear una API...",
      "totalCost": 0.0567
    }
  ]
}
```

**POST /api/history**

Guarda una conversación completa.

```json
// Request
{
  "id": "conv_1705312200000",
  "createdAt": 1705312200000,
  "updatedAt": 1705315800000,
  "label": "Crear API REST",
  "cwd": "/home/user/projects/api",
  "messageCount": 24,
  "preview": "Hola Rain, necesito crear una API...",
  "totalCost": 0.0567,
  "version": 1,
  "agentId": "agent_abc123",
  "sessionId": "ses_xyz789",
  "messages": [ /* array de AnyMessage */ ]
}
```

→ `{"saved": true, "id": "conv_1705312200000", "deleted": ["conv_old1"]}`

**GET /api/history/{conversationId}**
→ Conversación completa (mismo formato del POST)

**DELETE /api/history/{conversationId}**
→ `{"deleted": true}`

---

## 8. Modelos de Datos (para Dart)

### Mensaje Base
```dart
abstract class Message {
  final String id;          // UUID
  final String type;        // "user", "assistant", "system", etc.
  final int timestamp;      // milliseconds since epoch
  final bool animate;       // para animaciones de entrada en UI
}
```

### Tipos de Mensaje

```dart
class UserMessage extends Message {
  final String text;
}

class AssistantMessage extends Message {
  final String text;
  final bool isStreaming;   // true mientras se acumulan chunks
}

class SystemMessage extends Message {
  final String text;        // info como "3.2s | 2 turns | $0.0234"
}

class ToolUseMessage extends Message {
  final String tool;        // nombre de la herramienta
  final Map<String, dynamic> input;
  final String toolUseId;   // para vincular con ToolResultMessage
}

class ToolResultMessage extends Message {
  final String content;
  final bool isError;
  final String toolUseId;   // vincula con ToolUseMessage.toolUseId
}

class PermissionRequestMessage extends Message {
  final String requestId;   // para enviar permission_response
  final String tool;
  final Map<String, dynamic> input;
  final String level;       // "yellow" | "red" | "computer"
  final String reason;
  final String status;      // "pending" | "approved" | "denied" | "expired"
}

class ComputerScreenshotMessage extends Message {
  final String image;       // base64 PNG
  final String action;
  final String description;
  final int iteration;
}

class ComputerActionMessage extends Message {
  final String tool;
  final String action;
  final Map<String, dynamic> input;
  final String description;
  final int iteration;
}
```

### Estado del Agente
```dart
class Agent {
  final String id;
  String? cwd;
  String currentBrowsePath;
  String label;
  AgentStatus status;       // idle, working, done, error
  int unread;
  List<Message> messages;
  double scrollPos;
  String streamText;        // texto acumulado durante streaming
  String? streamMessageId;
  bool isProcessing;
  bool interruptPending;
  bool historyLoaded;
  String? sessionId;        // para reanudar conversación
  AgentPanel activePanel;   // fileBrowser, chat
  AgentMode mode;           // coding, computer_use
  DisplayInfo? displayInfo;
  String? lastScreenshot;   // base64 PNG
  int computerIteration;
}

enum AgentStatus { idle, working, done, error }
enum AgentMode { coding, computerUse }
enum AgentPanel { fileBrowser, chat }

class DisplayInfo {
  final int screenWidth;
  final int screenHeight;
  final int scaledWidth;
  final int scaledHeight;
  final double scaleFactor;
}
```

### Rate Limits
```dart
class RateLimits {
  int? requestsLimit;
  int? requestsRemaining;
  String? requestsReset;
  int? inputTokensLimit;
  int? inputTokensRemaining;
  String? inputTokensReset;
  int? outputTokensLimit;
  int? outputTokensRemaining;
  String? outputTokensReset;
}
```

---

## 9. Comportamientos Clave a Replicar

### 9.1 Streaming de Texto

Los mensajes `assistant_text` llegan como chunks parciales que se **acumulan**:

```
← {"type": "assistant_text", "text": "Claro, ", "agent_id": "a1"}
← {"type": "assistant_text", "text": "voy a ", "agent_id": "a1"}
← {"type": "assistant_text", "text": "crear el archivo.", "agent_id": "a1"}
```

**Implementación:**
1. Al recibir el primer chunk, crear un `AssistantMessage` con `isStreaming: true`
2. Acumular texto en `agent.streamText`
3. Actualizar el `AssistantMessage.text` con el texto acumulado
4. Al recibir `tool_use`, `result`, o `error`: finalizar streaming
   - Setear `isStreaming: false`
   - Limpiar `streamText`

### 9.2 Vinculación Tool Use → Tool Result

Los mensajes `tool_use` y `tool_result` se vinculan por `toolUseId`:

```
← tool_use  {id: "toolu_123", tool: "bash", input: {command: "ls"}}
← tool_result {tool_use_id: "toolu_123", content: "file1.txt\n", is_error: false}
```

En la UI, mostrar el `tool_result` dentro o debajo del `tool_use` correspondiente.

### 9.3 Flujo de Permisos

```
← permission_request {request_id: "perm_abc", level: "yellow", tool: "bash", ...}
   UI: Mostrar dialog con detalles de la herramienta
   Usuario: Aprueba o deniega
→ permission_response {request_id: "perm_abc", approved: true}
   El agente continúa
```

Para nivel RED, el dialog debe incluir un campo de PIN.

**Timeout**: Si no se responde en 5 minutos, el servidor deniega automáticamente.

### 9.4 Auto-Reconexión

```dart
// Pseudocódigo
void onDisconnect(int code) {
  if (code == 4001) {
    // Token inválido → borrar token → mostrar pantalla PIN
    clearToken();
    navigateTo(PinScreen);
  } else if (code == 4002) {
    // Idle timeout → reconectar en 1 segundo
    Future.delayed(Duration(seconds: 1), reconnect);
  } else {
    // Error de red → backoff exponencial
    if (consecutiveFailures < 3) {
      Future.delayed(Duration(seconds: 3), reconnect);
      consecutiveFailures++;
    } else {
      // Demasiados fallos → reset a pantalla PIN
      clearToken();
      navigateTo(PinScreen);
    }
  }
}
```

### 9.5 Reinicio de Agentes en Reconexión

Cuando el WebSocket se reconecta, el cliente debe:
1. Re-enviar `set_api_key` con el provider/model/key almacenados
2. Para cada agente activo, re-enviar `set_cwd` con su `path` y `session_id`

### 9.6 Texto de Resultado

Cuando llega un mensaje `result` con métricas, construir un `SystemMessage`:
```dart
String info = "";
if (durationMs != null) info += "${(durationMs / 1000).toStringAsFixed(1)}s";
if (numTurns != null) info += " | $numTurns turns";
if (cost != null) info += " | \$${cost.toStringAsFixed(4)}";
// Agregar como SystemMessage al chat
```

---

## 10. Rate Limiting del Backend

### HTTP Endpoints
- Sliding window por token, por categoría de endpoint
- Response header `Retry-After` cuando se excede el límite
- El cliente debe leer `Retry-After` y reintentar después de ese tiempo

### WebSocket
- **60 mensajes/minuto** por token
- **Tamaño máximo de mensaje**: 16 KB
- **Agentes concurrentes**: máximo 5 por conexión

### Cuotas Diarias
| Recurso | Límite | Identificador |
|---------|--------|---------------|
| Audio (transcripción) | 60 min/día | por token |
| TTS (síntesis) | 100,000 chars/día | por token |

---

## 11. Seguridad

### Headers HTTP del servidor
- `Strict-Transport-Security: max-age=31536000` (solo HTTPS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

### CORS
El servidor acepta orígenes configurados en `~/.rain-assistant/config.json`:
```json
{
  "cors_origins": ["https://my-tunnel.trycloudflare.com"]
}
```
Para Flutter, agregar la URL del backend a `cors_origins`.

> **Nota**: Las apps Flutter nativas no pasan por CORS (solo aplica a web).
> Las apps nativas se conectan directamente sin restricciones de origen.

### Almacenamiento Seguro
- **Token**: usar `flutter_secure_storage` (no SharedPreferences)
- **API keys**: almacenar encriptadas, nunca en texto plano
- **PIN**: nunca almacenar, pedir al usuario cada vez

---

## 12. Proveedores de IA

### Modelos Disponibles

```dart
const providers = {
  'claude': [
    {'id': 'auto', 'name': 'Auto (SDK)'},
  ],
  'openai': [
    {'id': 'gpt-4o', 'name': 'GPT-4o'},
    {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini'},
    {'id': 'gpt-4.1', 'name': 'GPT-4.1'},
    {'id': 'gpt-4.1-mini', 'name': 'GPT-4.1 Mini'},
    {'id': 'gpt-4.1-nano', 'name': 'GPT-4.1 Nano'},
    {'id': 'o3-mini', 'name': 'o3-mini'},
    {'id': 'o4-mini', 'name': 'o4-mini'},
  ],
  'gemini': [
    {'id': 'gemini-2.5-pro', 'name': 'Gemini 2.5 Pro'},
    {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash'},
    {'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash'},
    {'id': 'gemini-2.0-flash-lite', 'name': 'Gemini 2.0 Flash Lite'},
  ],
};

const providerInfo = {
  'claude': {
    'name': 'Claude',
    'keyPlaceholder': 'sk-ant-...',
    'consoleUrl': 'https://console.anthropic.com',
  },
  'openai': {
    'name': 'OpenAI',
    'keyPlaceholder': 'sk-...',
    'consoleUrl': 'https://platform.openai.com/api-keys',
  },
  'gemini': {
    'name': 'Gemini',
    'keyPlaceholder': 'AIza...',
    'consoleUrl': 'https://aistudio.google.com/apikey',
  },
};
```

### Nombres Cortos de Modelos Claude
```dart
const modelShortNames = {
  'claude-sonnet-4-5-20250929': 'Sonnet 4.5',
  'claude-sonnet-4-20250514': 'Sonnet 4',
  'claude-opus-4-20250514': 'Opus 4',
  'claude-opus-4-6': 'Opus 4.6',
  'claude-haiku-3-5-20241022': 'Haiku 3.5',
  'claude-3-5-sonnet-20241022': 'Sonnet 3.5',
};
```

---

## 13. Temas y Localización

### Temas
El frontend web usa 2 temas: `light` y `dark`.
Flutter debe implementar equivalentes con Material 3 `ThemeData`.

### Idiomas
Dos idiomas soportados: `"en"` (English) y `"es"` (Español).
Ver `frontend/src/lib/translations.ts` para la lista completa de strings.

### TTS
Configuración de TTS almacenada en settings:
- `ttsEnabled`: bool
- `ttsAutoPlay`: bool (reproducir automáticamente al terminar respuesta)
- `ttsVoice`: string (ID de voz, ver sección 7)

---

## 14. Estructura Flutter Propuesta

```
rain_flutter/
├── pubspec.yaml
├── lib/
│   ├── main.dart
│   ├── app/
│   │   ├── router.dart                 # GoRouter
│   │   ├── theme.dart                  # ThemeData light/dark
│   │   └── l10n.dart                   # Strings en/es
│   ├── models/
│   │   ├── message.dart                # Todos los tipos de mensaje
│   │   ├── agent.dart                  # Agent, AgentStatus, AgentMode
│   │   ├── rate_limits.dart            # RateLimits
│   │   ├── metrics.dart                # MetricsData, MetricsTotals
│   │   ├── file_entry.dart             # FileEntry, BrowseResponse
│   │   └── conversation.dart           # ConversationMeta, ConversationFull
│   ├── services/
│   │   ├── auth_service.dart           # POST /api/auth, secure storage
│   │   ├── websocket_service.dart      # Conexión, heartbeat, reconexión
│   │   ├── api_service.dart            # Llamadas REST (browse, audio, TTS, etc.)
│   │   └── audio_service.dart          # Grabar audio, enviar, reproducir TTS
│   ├── providers/                      # Riverpod
│   │   ├── connection_provider.dart    # Estado de conexión + WebSocket
│   │   ├── agent_provider.dart         # Multi-agente + mensajes
│   │   ├── settings_provider.dart      # Tema, idioma, TTS, provider IA
│   │   ├── metrics_provider.dart       # Rate limits, modelo, uso
│   │   └── ui_provider.dart            # Panel activo, drawer states
│   ├── screens/
│   │   ├── pin_screen.dart             # Ingreso de PIN
│   │   ├── api_key_screen.dart         # Configurar API key + provider
│   │   ├── file_browser_screen.dart    # Selector de directorio (CWD)
│   │   ├── chat_screen.dart            # Pantalla principal de chat
│   │   ├── settings_screen.dart        # Configuraciones
│   │   └── metrics_screen.dart         # Métricas de uso
│   └── widgets/
│       ├── message_bubble.dart         # Burbuja de texto (user/assistant)
│       ├── tool_use_block.dart         # Bloque expandible de tool_use
│       ├── tool_result_block.dart      # Resultado de tool (con color error)
│       ├── permission_dialog.dart      # Dialog de aprobación (yellow/red)
│       ├── record_button.dart          # Botón push-to-talk
│       ├── interrupt_button.dart       # Botón de interrupción
│       ├── computer_screenshot.dart    # Imagen de screenshot
│       ├── computer_action_block.dart  # Acción de computer use
│       ├── rate_limit_badge.dart       # Indicador de rate limits
│       ├── model_switcher.dart         # Selector de modelo/provider
│       └── status_bar.dart             # Barra de estado (conexión, modelo)
├── android/
├── ios/
└── test/
```

---

## 15. Paquetes Flutter Recomendados

```yaml
dependencies:
  # UI
  flutter_markdown: ^0.7.0       # Renderizar markdown en mensajes
  lucide_icons: ^0.0.1           # Iconos (consistencia con web)
  google_fonts: ^6.0.0           # Tipografía

  # Estado
  flutter_riverpod: ^2.5.0       # State management
  riverpod_annotation: ^2.3.0    # Code generation

  # Red
  web_socket_channel: ^3.0.0     # WebSocket
  dio: ^5.4.0                    # HTTP client con interceptors
  connectivity_plus: ^6.0.0      # Detectar estado de red

  # Audio
  record: ^5.1.0                 # Grabar audio del micrófono
  just_audio: ^0.9.0             # Reproducir TTS (MP3)

  # Almacenamiento
  flutter_secure_storage: ^9.0.0 # Token y API keys
  shared_preferences: ^2.2.0     # Settings no sensibles (tema, idioma)

  # Utilidades
  uuid: ^4.3.0                   # Generar IDs de mensajes
  intl: ^0.19.0                  # Formateo de fechas/números
  path: ^1.9.0                   # Manipulación de rutas
```

---

## 16. Configuración Inicial del Backend para Flutter

Para que la app Flutter se conecte al backend:

### Opción A: Red local (desarrollo)
El backend corre en `http://192.168.x.x:8000`. La app se conecta directamente.
No requiere CORS (las apps nativas no pasan por restricciones de origen).

### Opción B: Túnel público (producción ligera)
Usar Cloudflare Tunnel o ngrok para exponer el backend:
```bash
cloudflared tunnel --url http://localhost:8000
```
La URL resultante se usa en la app Flutter.

### Opción C: Deploy en VPS
El backend se despliega en un servidor con IP/dominio público.
Configurar HTTPS con Let's Encrypt + nginx reverse proxy.

**En todos los casos**, el usuario solo necesita ingresar:
1. La URL del servidor (ej: `https://rain.midominio.com`)
2. El PIN

---

## 17. Diferencias con el Frontend Web

| Aspecto | Web (Next.js) | Flutter |
|---------|---------------|---------|
| Audio | `getUserMedia` Web API | `record` package (nativo) |
| Storage | `sessionStorage` | `flutter_secure_storage` |
| Notificaciones | `Notification` Web API | `flutter_local_notifications` |
| URL del server | Se infiere de `window.location` | El usuario la ingresa manualmente |
| CORS | Aplica (browser) | No aplica (app nativa) |
| Temas | CSS variables + `data-theme` | `ThemeData` de Material 3 |
| Markdown | `react-markdown` | `flutter_markdown` |
| Service Worker | Para push notifications | No aplica (usar FCM si se desea) |
| Viewport | `100dvh`, safe-area CSS | `SafeArea` widget |

---

## 18. Pantallas y Flujo de Navegación

```
┌──────────────┐     ┌───────────────┐     ┌─────────────────┐
│  Server URL  │────>│   PIN Entry   │────>│  API Key Setup  │
│  (primera    │     │               │     │  (si no hay key │
│   vez)       │     │               │     │   en config)    │
└──────────────┘     └───────────────┘     └────────┬────────┘
                                                     │
                           ┌─────────────────────────▼──────┐
                           │         File Browser           │
                           │   (seleccionar CWD del agente) │
                           └─────────────┬──────────────────┘
                                         │
                           ┌─────────────▼──────────────────┐
                           │            Chat                │
                           │  ┌─────────────────────────┐   │
                           │  │    Messages list         │   │
                           │  │    (scroll + streaming)  │   │
                           │  ├─────────────────────────┤   │
                           │  │    Input bar             │   │
                           │  │    [mic] [text] [send]   │   │
                           │  └─────────────────────────┘   │
                           │                                 │
                           │  Bottom nav / Drawer:           │
                           │  [Chat] [Files] [Settings]      │
                           │  [Metrics] [History]            │
                           └─────────────────────────────────┘
```

**Nota extra (Server URL)**: A diferencia del web, la app Flutter necesita que el usuario
ingrese la URL del backend la primera vez (ej: `https://rain.example.com`).
Esta URL se persiste en `SharedPreferences` y se reutiliza en siguientes sesiones.

---

## 19. Checklist de Implementación

- [ ] **Fase 1: Scaffold + Auth**
  - [ ] Crear proyecto Flutter con estructura de carpetas
  - [ ] Pantalla de Server URL (input + persistir)
  - [ ] Pantalla de PIN (con manejo de errores y lockout)
  - [ ] Secure storage para token
  - [ ] Servicio HTTP base con Bearer token

- [ ] **Fase 2: WebSocket**
  - [ ] Conexión WebSocket con token en query string
  - [ ] Parseo de mensajes JSON (todos los tipos)
  - [ ] Heartbeat (ping/pong)
  - [ ] Auto-reconexión con backoff
  - [ ] Manejo de códigos de cierre (4001, 4002)

- [ ] **Fase 3: Chat Core**
  - [ ] Lista de mensajes scrollable
  - [ ] Burbuja de texto con markdown rendering
  - [ ] Streaming de assistant_text (acumulación de chunks)
  - [ ] Input de texto + envío
  - [ ] Bloques de tool_use y tool_result
  - [ ] Sistema de mensajes (SystemMessage para métricas)

- [ ] **Fase 4: Audio**
  - [ ] Grabación de audio con `record` package
  - [ ] Upload a `/api/upload-audio` (multipart)
  - [ ] Botón push-to-talk (hold to record)
  - [ ] TTS: llamar `/api/synthesize`, reproducir con `just_audio`
  - [ ] Auto-play TTS al terminar respuesta (si está habilitado)

- [ ] **Fase 5: Permisos**
  - [ ] Dialog para permiso YELLOW (Aprobar/Denegar)
  - [ ] Dialog para permiso RED (con input de PIN)
  - [ ] Actualizar estado del mensaje (pending → approved/denied)
  - [ ] Timeout visual (5 min countdown)

- [ ] **Fase 6: Multi-agente**
  - [ ] Estado por agente (mensajes, streaming, status)
  - [ ] Tabs de agentes
  - [ ] Crear/destruir agentes
  - [ ] Badge de unread por agente

- [ ] **Fase 7: Funcionalidades Secundarias**
  - [ ] File browser (GET /api/browse)
  - [ ] Settings (tema, idioma, TTS, provider/modelo)
  - [ ] Métricas (GET /api/metrics)
  - [ ] Historial de conversaciones (CRUD /api/history)
  - [ ] Rate limit badge
  - [ ] Model switcher

- [ ] **Fase 8: Computer Use** (opcional, avanzado)
  - [ ] Cambio de modo (coding ↔ computer_use)
  - [ ] Mostrar screenshots en base64
  - [ ] Mostrar acciones de computer
  - [ ] Emergency stop

- [ ] **Fase 9: Pulido**
  - [ ] Animaciones de entrada de mensajes
  - [ ] Tema dark/light con Material 3
  - [ ] i18n (español/inglés)
  - [ ] Manejo de errores de red (offline, timeout)
  - [ ] Toast notifications
  - [ ] App icon y splash screen
