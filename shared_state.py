"""Shared state, constants, and helpers used by server.py and route modules.

This module exists to break circular imports: route modules import from here
instead of from server.py, and server.py populates the mutable state at
startup.
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path

import bcrypt

import database

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ALLOWED_ROOT = Path.home()
CONFIG_DIR = Path.home() / ".rain-assistant"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Compiled pattern for validating agent IDs (alphanumeric, hyphens, underscores)
_AGENT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")

# Token / session constants
TOKEN_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# TTS / audio daily quotas
DAILY_TTS_CHAR_LIMIT = 100_000       # 100K chars/day
DAILY_AUDIO_SECONDS_LIMIT = 3_600    # 60 minutes/day
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
AUDIO_READ_CHUNK_SIZE = 64 * 1024          # 64 KB chunks

# Image upload constants
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024       # 10 MB per image
IMAGE_READ_CHUNK_SIZE = 64 * 1024               # 64 KB chunks
IMAGE_PENDING_TTL_SECONDS = 300                 # 5 minutes
MAX_PENDING_IMAGES_PER_TOKEN = 20               # prevent memory abuse
_VALID_IMAGE_MEDIA_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})

# WebSocket field limits
WS_MAX_MESSAGE_BYTES = 16 * 1024        # 16 KB raw message
WS_MAX_IMAGE_MESSAGE_BYTES = 5 * 1024 * 1024  # 5 MB safety net (legacy base64 path)
WS_MAX_TEXT_LENGTH = 10_000              # send_message text
WS_MAX_PATH_LENGTH = 500                 # set_cwd path
WS_MAX_KEY_LENGTH = 500                  # set_api_key key
WS_MAX_MSG_TYPE_LENGTH = 50              # type field
WS_MAX_AGENT_ID_LENGTH = 100             # agent_id field
MAX_BROWSE_PATH_LENGTH = 500             # /api/browse path
MAX_CWD_LENGTH = 500                     # /api/messages cwd
WS_MAX_TOOL_RESULT_WS = 500_000         # 500 KB max tool_result sent to frontend
WS_HEARTBEAT_INTERVAL = 30              # seconds between pings
WS_IDLE_TIMEOUT = 600                   # 10 minutes without activity -> disconnect
WS_MAX_CONCURRENT_AGENTS = 5            # max agents per connection
_VALID_PROVIDERS = {"claude", "openai", "gemini", "ollama"}

# Rate limiting: track failed PIN attempts per IP
MAX_PIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 5 * 60  # 5 minutes

# Conversation history
HISTORY_DIR = CONFIG_DIR / "history"
HISTORY_GLOB = "*.json"
MAX_CONVERSATIONS = 5

# File browser
MAX_ENTRIES = 200

# ---------------------------------------------------------------------------
# Mutable shared state (populated by server.py at startup)
# ---------------------------------------------------------------------------

# Token storage: { token_string: expiry_timestamp }
active_tokens: dict[str, float] = {}

# Map device_id -> WebSocket for active connections (for remote revocation)
_active_ws_by_device: dict = {}

# Map token_hash -> device_id for WS connection lookup
_token_device_map: dict[str, str] = {}

# Rate limiting: track failed PIN attempts per IP
# { ip: { "attempts": int, "locked_until": float } }
_auth_attempts: dict[str, dict] = {}

# Active OAuth login process tracker (only one at a time)
_oauth_login_process: dict | None = None

# Config dict (loaded at startup by server.py, updated in-place)
config: dict = {}

# MAX_DEVICES (set from config after load)
MAX_DEVICES: int = 2

# MCP server status tracking
# Each entry: { "status": "ok"|"disabled"|"error", "error": str|None }
# Example: { "rain-email": {"status": "ok", "error": None},
#            "rain-browser": {"status": "error", "error": "Server binary not found"} }
mcp_server_status: dict[str, dict] = {}

# MCP tool-to-server mapping (populated when config is loaded)
# Maps MCP tool name prefixes to server names
# Example: { "mcp__rain-email": "rain-email", "mcp__rain-browser": "rain-browser" }
mcp_tool_server_map: dict[str, str] = {}

# Pending image uploads: { image_id: { "data": bytes, "media_type": str, "token_prefix": str, "uploaded_at": float } }
pending_images: dict[str, dict] = {}

# WebSocket push: map user_id -> list of async send callables for real-time notifications
_active_user_senders: dict[str, list] = {}


async def notify_user(user_id: str, message: dict):
    """Send a push message to all active WebSocket connections for a user."""
    senders = _active_user_senders.get(user_id, [])
    for send_fn in list(senders):
        try:
            await send_fn(message)
        except Exception:
            # Remove stale sender
            try:
                senders.remove(send_fn)
            except ValueError:
                pass

# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


def _json_loads_safe(raw: str, max_depth: int = 10, max_size: int = 1_048_576) -> dict:
    """Parse JSON with depth and size limits to prevent DoS."""
    if len(raw) > max_size:
        raise ValueError(f"JSON payload too large ({len(raw)} bytes, max {max_size})")
    depth = 0
    for char in raw:
        if char in '{[':
            depth += 1
            if depth > max_depth:
                raise ValueError("JSON nesting too deep")
        elif char in '}]':
            depth -= 1
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Trusted proxy detection
# ---------------------------------------------------------------------------

_TRUSTED_PROXIES: set[str] = {"127.0.0.1", "::1"}


def _get_real_ip(request) -> str:
    """Extract client IP, trusting X-Forwarded-For only from local reverse proxy."""
    client_ip = request.client.host if request.client else "unknown"
    if client_ip in _TRUSTED_PROXIES:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            candidate = xff.split(",")[0].strip()
            try:
                import ipaddress
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                return client_ip
    return client_ip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _secure_chmod(path: Path, mode: int) -> None:
    """Best-effort chmod. Windows has limited support, so errors are ignored."""
    try:
        os.chmod(str(path), mode)
    except OSError:
        pass


def verify_token(token: str | None) -> bool:
    """Check if a token exists and has not expired."""
    if token is None or token not in active_tokens:
        return False
    expiry = active_tokens[token]
    if time.time() > expiry:
        active_tokens.pop(token, None)
        return False
    return True


def get_token(request) -> str | None:
    """Extract token from Authorization header."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _get_user_id_from_request(request) -> str:
    """Extract user_id from the request's Bearer token via session lookup."""
    token = get_token(request)
    if not token:
        return "default"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return database.get_user_id_from_token(token_hash)


def _find_claude_cli() -> str | None:
    """Find the Claude Code CLI binary (bundled in claude-agent-sdk or system)."""
    import shutil as _shutil

    try:
        import claude_agent_sdk
        import platform as _plat

        cli_name = "claude.exe" if _plat.system() == "Windows" else "claude"
        bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / cli_name
        if bundled.exists():
            return str(bundled)
    except ImportError:
        pass

    found = _shutil.which("claude")
    if found:
        return found

    return None
