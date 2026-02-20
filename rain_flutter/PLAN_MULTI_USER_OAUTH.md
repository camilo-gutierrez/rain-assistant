# Plan: OAuth multi-usuario dinámico

## Objetivo
Permitir que cada usuario de la app Flutter use su propia cuenta Claude Max/Pro, no solo la del servidor.

## Enfoque: HOME aislado + token upload

### Flujo
1. Usuario abre la app → pantalla de auth muestra opción "Usar tu cuenta Claude"
2. Usuario pega su `accessToken` y `refreshToken` (copiados de su `~/.claude/.credentials.json`)
3. Server recibe tokens vía WS → crea directorio aislado `/tmp/rain_users/{session_id}/.claude/`
4. Server escribe `.credentials.json` con los tokens del usuario
5. Al inicializar `ClaudeProvider`, se pasa `HOME=/tmp/rain_users/{session_id}` en el `env`
6. El CLI lee las credenciales de ese directorio aislado

### Cambios necesarios

**Backend (`server.py` + `claude_provider.py`)**
- Nuevo campo `oauth_tokens` en `set_api_key` message
- Crear directorio temporal per-session con `.credentials.json`
- Pasar `HOME` override en `ClaudeAgentOptions.env`
- Limpiar directorios temporales al desconectar

**Flutter (`api_key_screen.dart`)**
- Opción "Pegar token OAuth" con campos para access/refresh token
- O: leer `.credentials.json` del dispositivo si existe (desktop)
- Instrucciones para el usuario de cómo obtener sus tokens

### Alternativa futura: OAuth flow nativo
Si Anthropic documenta sus endpoints OAuth públicos:
- Abrir browser a `claude.ai/oauth/authorize`
- Callback con tokens → enviar al server
- Mejor UX, sin copiar tokens manualmente

### Consideraciones
- Seguridad: tokens en tránsito deben ir sobre WSS (ya se usa)
- Limpieza: borrar credenciales temporales al cerrar sesión
- Refresh: el CLI maneja refresh automático
- Scope: tokens solo permiten `user:inference`, `user:sessions:claude_code`
