import asyncio
import hashlib
import json
import bcrypt
import os
import secrets
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import httpx
import uvicorn

import database
from key_manager import ensure_encryption_key

from starlette.background import BackgroundTask

from transcriber import Transcriber
from synthesizer import Synthesizer
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
from claude_agent_sdk.types import StreamEvent

from permission_classifier import PermissionLevel, classify, get_danger_reason
from rate_limiter import rate_limiter, categorize_endpoint, EndpointCategory
from providers import get_provider, NormalizedEvent

# Computer Use imports (lazy — only used when mode is activated)
try:
    from anthropic import AsyncAnthropic
    from computer_use import (
        ComputerUseExecutor,
        describe_action,
        COMPUTER_USE_BETA,
        COMPUTER_USE_MODEL,
        COMPUTER_USE_MAX_TOKENS,
        COMPUTER_USE_MAX_ITERATIONS,
        COMPUTER_USE_SYSTEM_PROMPT,
    )
    COMPUTER_USE_AVAILABLE = True
except ImportError:
    COMPUTER_USE_AVAILABLE = False

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

# Prevent "nested session" error when launched from within Claude Code
os.environ.pop("CLAUDECODE", None)

# When running as a PyInstaller frozen exe, resources are in sys._MEIPASS
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys._MEIPASS)
else:
    _BASE_DIR = Path(__file__).parent

STATIC_DIR = _BASE_DIR / "static"
ALLOWED_ROOT = Path.home()
CONFIG_DIR = Path.home() / ".rain-assistant"
CONFIG_FILE = CONFIG_DIR / "config.json"
OLD_CONFIG_DIR = Path.home() / ".voice-claude"

# ---------------------------------------------------------------------------
# MCP config loader (graceful degradation)
# ---------------------------------------------------------------------------

_MCP_CONFIG_PATH = Path(__file__).parent / ".mcp.json"


def _load_mcp_config() -> dict | str:
    """Load MCP server configuration from .mcp.json with graceful error handling.

    Returns the config file path as a string (for the Claude SDK) if valid,
    or an empty dict if the file is missing or corrupted.
    """
    if not _MCP_CONFIG_PATH.exists():
        return {}
    try:
        # Validate that the JSON is parseable before passing the path to the SDK
        raw = _MCP_CONFIG_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            print(f"  [MCP] Warning: .mcp.json is not a JSON object, MCP servers disabled", flush=True)
            return {}
        return str(_MCP_CONFIG_PATH)
    except json.JSONDecodeError as e:
        print(f"  [MCP] Warning: .mcp.json has invalid JSON ({e}), MCP servers disabled", flush=True)
        return {}
    except OSError as e:
        print(f"  [MCP] Warning: Could not read .mcp.json ({e}), MCP servers disabled", flush=True)
        return {}


from prompt_composer import compose_system_prompt
from alter_egos.storage import (
    load_all_egos, load_ego, save_ego, delete_ego,
    get_active_ego_id, set_active_ego_id, ensure_builtin_egos,
)
from memories.storage import (
    load_memories, add_memory, remove_memory, clear_memories,
)

# Ensure built-in alter egos exist on startup
ensure_builtin_egos()

transcriber = Transcriber(model_size="base", language="es")
synthesizer = Synthesizer()

# Voice processing (lazy — only loaded when voice features are used)
try:
    from voice import VoiceActivityDetector, VADEvent, WakeWordDetector, TalkSession, TalkState

    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Rate limit fetching (Anthropic API headers via lightweight GET /v1/models)
# ---------------------------------------------------------------------------

_rate_limit_cache: dict = {"data": None, "last_fetch": 0.0}
_RATE_LIMIT_FETCH_INTERVAL = 30  # seconds between fetches


async def fetch_rate_limits(api_key: str) -> dict | None:
    """Fetch rate-limit info from Anthropic via a zero-cost GET /v1/models call.

    Returns a dict with cleaned header keys (e.g. "requests-limit") or None.
    Results are cached and the call is throttled to once per 30 s.
    """
    now = time.time()
    if (now - _rate_limit_cache["last_fetch"]) < _RATE_LIMIT_FETCH_INTERVAL:
        return _rate_limit_cache["data"]

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=5.0,
            )

        headers = resp.headers
        rate_limits: dict = {}

        prefixes = [
            "anthropic-ratelimit-requests",
            "anthropic-ratelimit-tokens",
            "anthropic-ratelimit-input-tokens",
            "anthropic-ratelimit-output-tokens",
        ]
        for prefix in prefixes:
            for suffix in ("limit", "remaining", "reset"):
                key = f"{prefix}-{suffix}"
                val = headers.get(key)
                if val is not None:
                    clean_key = key.replace("anthropic-ratelimit-", "")
                    if suffix != "reset":
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            pass
                    rate_limits[clean_key] = val

        if rate_limits:
            _rate_limit_cache["data"] = rate_limits
            _rate_limit_cache["last_fetch"] = now
            return rate_limits
    except Exception as exc:
        print(f"  [RATE_LIMIT] fetch failed: {exc}", flush=True)

    return _rate_limit_cache["data"]  # stale cache on failure


# ---------------------------------------------------------------------------
# PIN & token management
# ---------------------------------------------------------------------------

# Token storage: { token_string: expiry_timestamp }
TOKEN_TTL_SECONDS = 24 * 60 * 60  # 24 hours
active_tokens: dict[str, float] = {}

# TTS / audio daily quotas
DAILY_TTS_CHAR_LIMIT = 100_000       # 100K chars/day
DAILY_AUDIO_SECONDS_LIMIT = 3_600    # 60 minutes/day
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

# ---------------------------------------------------------------------------
# Input validation models (Pydantic)
# ---------------------------------------------------------------------------

class AuthRequest(BaseModel):
    pin: str = Field(..., min_length=1, max_length=20)

class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = Field(default="es-MX-DaliaNeural", max_length=100)
    rate: str = Field(default="+0%", max_length=20)

# WebSocket field limits
WS_MAX_MESSAGE_BYTES = 16 * 1024        # 16 KB raw message
WS_MAX_TEXT_LENGTH = 10_000              # send_message text
WS_MAX_PATH_LENGTH = 500                 # set_cwd path
WS_MAX_KEY_LENGTH = 500                  # set_api_key key
WS_MAX_MSG_TYPE_LENGTH = 50              # type field
WS_MAX_AGENT_ID_LENGTH = 100             # agent_id field
MAX_BROWSE_PATH_LENGTH = 500             # /api/browse path
MAX_CWD_LENGTH = 500                     # /api/messages cwd
WS_MAX_TOOL_RESULT_WS = 500_000         # 500 KB max tool_result sent to frontend
WS_HEARTBEAT_INTERVAL = 30              # seconds between pings
WS_IDLE_TIMEOUT = 600                   # 10 minutes without activity → disconnect
WS_MAX_CONCURRENT_AGENTS = 5            # max agents per connection

# Rate limiting: track failed PIN attempts per IP
# { ip: { "attempts": int, "locked_until": float } }
MAX_PIN_ATTEMPTS = 3
LOCKOUT_SECONDS = 5 * 60  # 5 minutes
_auth_attempts: dict[str, dict] = {}


def load_or_create_config() -> dict:
    """Load config from ~/.rain-assistant/config.json or create with new PIN.

    The PIN is stored as a bcrypt hash. On first creation or migration from
    a legacy plain-text PIN, the actual PIN is kept in a transient
    ``_display_pin`` key (never persisted) so it can be printed once at
    startup.
    """
    # Migrate from old config directory
    if OLD_CONFIG_DIR.exists() and not CONFIG_DIR.exists():
        import shutil
        shutil.copytree(str(OLD_CONFIG_DIR), str(CONFIG_DIR))
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

            # Already migrated to hashed PIN
            if "pin_hash" in cfg:
                return cfg

            # Legacy: plain-text PIN — migrate to bcrypt hash
            if "pin" in cfg:
                plain_pin = str(cfg["pin"])
                hashed = bcrypt.hashpw(
                    plain_pin.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")
                cfg["pin_hash"] = hashed
                del cfg["pin"]
                CONFIG_FILE.write_text(
                    json.dumps(cfg, indent=2), encoding="utf-8"
                )
                print(f"\n  [SECURITY] PIN migrated to bcrypt hash.", flush=True)
                print(f"  [SECURITY] Your existing PIN is: {plain_pin}", flush=True)
                print(f"  [SECURITY] This is the LAST TIME it will be shown.\n", flush=True)
                return cfg

        except (json.JSONDecodeError, OSError):
            pass

    # Generate new PIN
    pin = f"{secrets.randbelow(900000) + 100000}"
    hashed = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    cfg = {"pin_hash": hashed}
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    # Store pin temporarily for display at startup only (NOT persisted)
    cfg["_display_pin"] = pin
    return cfg


config = load_or_create_config()


def verify_token(token: str | None) -> bool:
    """Check if a token exists and has not expired."""
    if token is None or token not in active_tokens:
        return False
    expiry = active_tokens[token]
    if time.time() > expiry:
        # Token expired — remove it
        active_tokens.pop(token, None)
        return False
    return True


async def _cleanup_expired_tokens():
    """Periodically remove expired tokens from memory."""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        now = time.time()
        expired = [t for t, exp in active_tokens.items() if now > exp]
        for t in expired:
            active_tokens.pop(t, None)
        if expired:
            print(f"  [AUTH] Cleaned up {len(expired)} expired token(s)", flush=True)


async def _scheduler_execute_ai_prompt(task_name: str, prompt: str) -> tuple[str | None, str | None]:
    """Execute an ai_prompt scheduled task using a temporary provider instance.

    Creates a fresh provider, sends the prompt, collects the full response
    (including any tool calls the AI may make), and tears down the provider.

    Returns:
        (result_text, error_text) -- one of them will be None.
    """
    import logging
    _sched_logger = logging.getLogger("rain.scheduler")

    # Load provider configuration from config
    provider_name = config.get("default_provider", "claude")
    provider_keys_cfg = config.get("provider_keys", {})
    api_key = config.get("default_api_key", "")

    # Resolve API key: check provider_keys first, then default_api_key
    if isinstance(provider_keys_cfg, dict) and provider_name in provider_keys_cfg:
        api_key = provider_keys_cfg[provider_name]

    if not api_key:
        msg = (
            f"No API key configured for provider '{provider_name}'. "
            "Cannot execute ai_prompt task. Set an API key in config.json "
            "(provider_keys or default_api_key)."
        )
        _sched_logger.warning("[SCHEDULER] %s", msg)
        return None, msg

    provider = None
    try:
        provider = get_provider(provider_name)

        # Use the composed system prompt for background tasks
        system_prompt = compose_system_prompt()

        # Use home directory as working directory for scheduled tasks
        cwd = str(Path.home())

        # Auto-approve GREEN tools only; deny everything else in background tasks
        async def _scheduler_permission_callback(tool_name: str, tool_input: dict = None, _ctx=None) -> bool:
            from tools.executor import GREEN_TOOLS
            return tool_name in GREEN_TOOLS

        await provider.initialize(
            api_key=api_key,
            model="auto",
            cwd=cwd,
            system_prompt=system_prompt,
            can_use_tool=_scheduler_permission_callback,
        )

        # Send the prompt
        await provider.send_message(prompt)

        # Collect the full response by iterating through the stream
        collected_text = ""
        async for event in provider.stream_response():
            if event.type == "assistant_text":
                collected_text += event.data.get("text", "")
            elif event.type == "result":
                # Use the final result text if available (may be more complete)
                result_text = event.data.get("text", "")
                if result_text:
                    collected_text = result_text
            elif event.type == "error":
                error_text = event.data.get("text", "Unknown provider error")
                _sched_logger.error(
                    "[SCHEDULER] AI prompt '%s' provider error: %s", task_name, error_text
                )
                return None, error_text

        if not collected_text:
            collected_text = "(empty response)"

        _sched_logger.info(
            "[SCHEDULER] AI prompt '%s' completed (%d chars)", task_name, len(collected_text)
        )
        return collected_text, None

    except Exception as e:
        error_msg = f"Provider error ({provider_name}): {e}"
        _sched_logger.error("[SCHEDULER] AI prompt '%s' failed: %s", task_name, error_msg)
        return None, error_msg
    finally:
        if provider:
            try:
                await provider.disconnect()
            except Exception:
                pass


async def _scheduler_loop():
    """Background loop for executing scheduled tasks (cron).

    Checks every 30 seconds for tasks whose next_run has passed,
    executes them, and reschedules. Supports three task types:

    - reminder: logs the message and stores it as last_result
    - bash: runs a shell command with timeout, stores stdout/stderr
    - ai_prompt: creates a temporary AI provider, sends the prompt, collects response
    """
    import logging
    _sched_logger = logging.getLogger("rain.scheduler")

    while True:
        await asyncio.sleep(30)
        try:
            from scheduled_tasks.storage import get_pending_tasks, mark_task_run
            pending = get_pending_tasks()
            for task in pending:
                task_type = task.get("task_type", "reminder")
                task_data = task.get("task_data", {})
                task_name = task.get("name", "")
                task_id = task["id"]
                result_text: str | None = None
                error_text: str | None = None

                if task_type == "reminder":
                    msg = task_data.get("message", task_name)
                    result_text = msg
                    _sched_logger.info("[SCHEDULER] Reminder: %s", msg)

                elif task_type == "bash":
                    cmd = task_data.get("command", "")
                    if cmd:
                        try:
                            proc = await asyncio.create_subprocess_shell(
                                cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            stdout, stderr = await asyncio.wait_for(
                                proc.communicate(), timeout=60
                            )
                            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
                            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

                            if proc.returncode == 0:
                                result_text = stdout_str or "(no output)"
                                _sched_logger.info(
                                    "[SCHEDULER] Bash '%s': exit=0, %d bytes output",
                                    task_name, len(stdout_str),
                                )
                            else:
                                error_text = (
                                    f"exit code {proc.returncode}\n"
                                    f"stdout: {stdout_str[:2000]}\n"
                                    f"stderr: {stderr_str[:2000]}"
                                )
                                _sched_logger.error(
                                    "[SCHEDULER] Bash '%s': exit=%d",
                                    task_name, proc.returncode,
                                )
                        except asyncio.TimeoutError:
                            error_text = "Command timed out after 60 seconds"
                            _sched_logger.error(
                                "[SCHEDULER] Bash '%s' timed out", task_name
                            )
                            try:
                                proc.kill()
                            except Exception:
                                pass
                        except Exception as e:
                            error_text = str(e)
                            _sched_logger.error(
                                "[SCHEDULER] Bash '%s' failed: %s", task_name, e
                            )
                    else:
                        error_text = "No command specified"

                elif task_type == "ai_prompt":
                    prompt = task_data.get("prompt", "")
                    if prompt:
                        _sched_logger.info(
                            "[SCHEDULER] AI prompt '%s': executing...", task_name
                        )
                        try:
                            result_text, error_text = await asyncio.wait_for(
                                _scheduler_execute_ai_prompt(task_name, prompt),
                                timeout=120,
                            )
                        except asyncio.TimeoutError:
                            error_text = "AI prompt execution timed out after 120 seconds"
                            _sched_logger.error(
                                "[SCHEDULER] AI prompt '%s' timed out", task_name
                            )
                    else:
                        error_text = "No prompt specified"

                # Mark the task as run and store result/error
                mark_task_run(task_id, result=result_text, error=error_text)

        except ImportError:
            pass  # croniter not installed
        except Exception as e:
            _sched_logger.error("[SCHEDULER] Unexpected error: %s", e)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Ensure the encryption key is in the OS keyring (auto-migrates from config.json)
    ensure_encryption_key(CONFIG_FILE)
    database._ensure_db()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, transcriber.load_model)
    cleanup_task = asyncio.create_task(_cleanup_expired_tokens())
    scheduler_task = asyncio.create_task(_scheduler_loop())
    yield
    cleanup_task.cancel()
    scheduler_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Rain Assistant", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)

        # Detect if request came through HTTPS (Cloudflare tunnel sets these)
        is_https = (
            request.headers.get("x-forwarded-proto") == "https"
            or request.url.scheme == "https"
        )

        if is_https:
            # HSTS: tell browser to always use HTTPS for this domain
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Basic XSS protection (legacy, but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy: restrict sensitive browser APIs
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), payment=()"
        )

        return response


app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Rate limiting middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-token sliding window rate limiting for HTTP endpoints."""

    _EXEMPT_PATHS = {"/", "/sw.js"}

    async def dispatch(self, request: StarletteRequest, call_next):
        path = request.url.path

        # Skip static files and exempt paths
        if path in self._EXEMPT_PATHS or path.startswith("/static"):
            return await call_next(request)

        # Extract token — for unauthenticated endpoints (e.g. /api/auth),
        # use the client IP as the rate-limit key instead of a Bearer token.
        auth_header = request.headers.get("authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
        if not token:
            # For auth endpoint, rate-limit by client IP
            category = categorize_endpoint(path)
            if category == EndpointCategory.AUTH:
                client_ip = request.client.host if request.client else "unknown"
                token = f"ip:{client_ip}"
            else:
                return await call_next(request)

        category = categorize_endpoint(path)
        result = rate_limiter.check(token, category)

        if not result.allowed:
            client_ip = request.client.host if request.client else ""
            database.log_security_event(
                "rate_limited", "warning",
                client_ip=client_ip, token_prefix=token[:8],
                details=f"category={category.value}, limit={result.limit}",
                endpoint=path,
            )
            response = JSONResponse(
                {"error": "Rate limit exceeded", "retry_after": result.retry_after},
                status_code=429,
            )
            response.headers["Retry-After"] = str(int(result.retry_after) + 1)
            response.headers["X-RateLimit-Limit"] = str(result.limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        # Update session activity
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            database.update_session_activity(token_hash)
        except Exception:
            pass

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response


app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------------
# Access logging middleware
# ---------------------------------------------------------------------------

class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests to the access_log table."""

    _SKIP_PATHS = {"/sw.js"}

    async def dispatch(self, request: StarletteRequest, call_next):
        path = request.url.path
        if path in self._SKIP_PATHS or path.startswith("/static"):
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000

        auth = request.headers.get("authorization", "")
        token_prefix = auth[7:15] if auth.startswith("Bearer ") and len(auth) > 15 else ""

        database.log_access(
            method=request.method, path=path,
            status_code=response.status_code,
            response_ms=round(elapsed_ms, 2),
            client_ip=request.client.host if request.client else "",
            token_prefix=token_prefix,
            user_agent=request.headers.get("user-agent", "")[:200],
        )
        return response


app.add_middleware(AccessLogMiddleware)


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

from fastapi.middleware.cors import CORSMiddleware

# SECURITY NOTE: These are local-development origins.  For production or
# public-facing deployments, restrict cors_origins in config.json to the
# exact domain(s) serving the frontend (e.g. "https://rain.example.com").
CORS_ORIGINS = [
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost:3000", "http://127.0.0.1:3000",
]
# Allow extra origins from config (e.g. Cloudflare tunnel URL)
_extra_origins = config.get("cors_origins", [])
if isinstance(_extra_origins, list):
    CORS_ORIGINS.extend(_extra_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)


# ---------------------------------------------------------------------------
# REST: Serve frontend
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/sw.js")
async def service_worker():
    return FileResponse(str(STATIC_DIR / "sw.js"), media_type="application/javascript")


# ---------------------------------------------------------------------------
# REST: Authentication
# ---------------------------------------------------------------------------


@app.post("/api/auth")
async def authenticate(request: Request):
    client_ip = request.client.host if request.client else "unknown"

    # Check if this IP is currently locked out
    record = _auth_attempts.get(client_ip)
    if record:
        remaining = record["locked_until"] - time.time()
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            print(f"  [AUTH] IP {client_ip} is locked out ({mins}m {secs}s remaining)", flush=True)
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": int(remaining),
            }, status_code=429)
        else:
            # Lockout expired — reset
            del _auth_attempts[client_ip]

    try:
        body = await request.json()
        auth_req = AuthRequest(**body)
    except Exception:
        database.log_security_event(
            "invalid_input", "info", client_ip=client_ip, endpoint="/api/auth",
        )
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    pin = auth_req.pin.strip()
    pin_hash = config.get("pin_hash", "")

    # Verify PIN against bcrypt hash (never log PIN values)
    try:
        pin_valid = bool(pin) and bcrypt.checkpw(
            pin.encode("utf-8"), pin_hash.encode("utf-8")
        )
    except Exception:
        pin_valid = False

    print(f"  [AUTH] attempt from ip={client_ip} valid={pin_valid}", flush=True)

    if not pin_valid:
        database.log_security_event(
            "auth_failed", "warning", client_ip=client_ip, endpoint="/api/auth",
        )
        # Track failed attempt
        if client_ip not in _auth_attempts:
            _auth_attempts[client_ip] = {"attempts": 0, "locked_until": 0}
        _auth_attempts[client_ip]["attempts"] += 1
        attempts = _auth_attempts[client_ip]["attempts"]
        remaining_attempts = MAX_PIN_ATTEMPTS - attempts

        if attempts >= MAX_PIN_ATTEMPTS:
            _auth_attempts[client_ip]["locked_until"] = time.time() + LOCKOUT_SECONDS
            print(f"  [AUTH] IP {client_ip} LOCKED OUT after {attempts} failed attempts", flush=True)
            database.log_security_event(
                "auth_locked", "critical", client_ip=client_ip, endpoint="/api/auth",
            )
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": LOCKOUT_SECONDS,
            }, status_code=429)

        return JSONResponse({
            "error": "Invalid PIN",
            "remaining_attempts": remaining_attempts,
        }, status_code=401)

    # Successful auth — clear any attempt tracking for this IP
    _auth_attempts.pop(client_ip, None)
    token = secrets.token_urlsafe(32)
    active_tokens[token] = time.time() + TOKEN_TTL_SECONDS

    # Track session in database
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user_agent = request.headers.get("user-agent", "")[:200]
    database.create_session(token_hash, client_ip, user_agent)

    return {"token": token}


def get_token(request: Request) -> str | None:
    """Extract token from Authorization header."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


# ---------------------------------------------------------------------------
# REST: Logout
# ---------------------------------------------------------------------------

@app.post("/api/logout")
async def logout(request: Request):
    """Revoke the current token."""
    token = get_token(request)
    if not token or not verify_token(token):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    client_ip = request.client.host if request.client else "unknown"
    active_tokens.pop(token, None)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    database.revoke_session(token_hash)
    database.log_security_event(
        "token_revoked", "info", client_ip=client_ip,
        token_prefix=token[:8], endpoint="/api/logout",
    )
    return {"logged_out": True}


@app.post("/api/logout-all")
async def logout_all(request: Request):
    """Revoke ALL tokens. Requires PIN confirmation."""
    token = get_token(request)
    if not token or not verify_token(token):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    client_ip = request.client.host if request.client else "unknown"

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    pin = str(body.get("pin", "")).strip()
    pin_hash = config.get("pin_hash", "")

    try:
        pin_valid = bool(pin) and bcrypt.checkpw(
            pin.encode("utf-8"), pin_hash.encode("utf-8")
        )
    except Exception:
        pin_valid = False

    if not pin_valid:
        database.log_security_event(
            "auth_failed", "warning", client_ip=client_ip,
            endpoint="/api/logout-all", details="invalid_pin_for_logout_all",
        )
        return JSONResponse({"error": "Invalid PIN"}, status_code=401)

    count = len(active_tokens)
    active_tokens.clear()
    sessions_cleared = database.revoke_all_sessions()
    database.log_security_event(
        "token_revoked", "critical", client_ip=client_ip,
        token_prefix=token[:8] if token else "",
        details=f"logout_all: {count} tokens, {sessions_cleared} sessions cleared",
        endpoint="/api/logout-all",
    )
    return {"logged_out_all": True, "tokens_revoked": count}


# ---------------------------------------------------------------------------
# REST: Check Claude OAuth credentials
# ---------------------------------------------------------------------------

@app.get("/api/check-oauth")
async def check_oauth(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    creds_path = Path.home() / ".claude" / ".credentials.json"
    if not creds_path.exists():
        return JSONResponse({"available": False})

    try:
        creds = json.loads(creds_path.read_text(encoding="utf-8"))
        oauth = creds.get("claudeAiOauth", {})

        if not oauth.get("accessToken"):
            return JSONResponse({"available": False})

        # Check if token is expired
        expires_at = oauth.get("expiresAt", 0)
        is_expired = expires_at < (time.time() * 1000)  # expiresAt is in ms

        return JSONResponse({
            "available": True,
            "subscriptionType": oauth.get("subscriptionType", "unknown"),
            "rateLimitTier": oauth.get("rateLimitTier", ""),
            "expired": is_expired,
        })
    except Exception:
        return JSONResponse({"available": False})


# ---------------------------------------------------------------------------
# REST: Filesystem browser
# ---------------------------------------------------------------------------

MAX_ENTRIES = 200


@app.get("/api/browse")
async def browse_filesystem(request: Request, path: str = "~"):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if len(path) > MAX_BROWSE_PATH_LENGTH:
        database.log_security_event(
            "invalid_input", "info",
            client_ip=request.client.host if request.client else "",
            endpoint="/api/browse", details=f"path_len={len(path)}",
        )
        return JSONResponse({"error": "Path too long"}, status_code=400)

    if path in ("~", ""):
        target = ALLOWED_ROOT
    else:
        target = Path(path)

    try:
        target = target.resolve(strict=True)
    except (OSError, ValueError):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    # Security: must be under allowed root
    try:
        target.relative_to(ALLOWED_ROOT)
    except ValueError:
        return JSONResponse({"error": "Access denied"}, status_code=403)

    if not target.is_dir():
        return JSONResponse({"error": "Not a directory"}, status_code=400)

    entries = []

    # Parent directory link (if not at root)
    if target != ALLOWED_ROOT:
        entries.append({
            "name": "..",
            "path": str(target.parent),
            "is_dir": True,
            "size": 0,
        })

    try:
        children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return JSONResponse({"error": "Permission denied"}, status_code=403)

    count = 0
    for child in children:
        if child.name.startswith("."):
            continue
        if count >= MAX_ENTRIES:
            break
        try:
            entries.append({
                "name": child.name,
                "path": str(child),
                "is_dir": child.is_dir(),
                "size": child.stat().st_size if child.is_file() else 0,
            })
            count += 1
        except (PermissionError, OSError):
            continue

    return {"current": str(target), "entries": entries}


# ---------------------------------------------------------------------------
# REST: Audio upload & transcription
# ---------------------------------------------------------------------------

@app.post("/api/upload-audio")
async def upload_audio(request: Request, audio: UploadFile = File(...)):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    suffix = ".webm"
    if audio.content_type and "wav" in audio.content_type:
        suffix = ".wav"
    elif audio.content_type and "ogg" in audio.content_type:
        suffix = ".ogg"
    elif audio.content_type and "mp4" in audio.content_type:
        suffix = ".mp4"

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        content = await audio.read()

        # Enforce upload size limit
        if len(content) > MAX_AUDIO_UPLOAD_BYTES:
            tmp.close()
            os.unlink(tmp.name)
            database.log_security_event(
                "invalid_input", "warning",
                client_ip=request.client.host if request.client else "",
                endpoint="/api/upload-audio",
                details=f"size={len(content)}, limit={MAX_AUDIO_UPLOAD_BYTES}",
            )
            return JSONResponse(
                {"error": f"File too large (max {MAX_AUDIO_UPLOAD_BYTES // (1024*1024)}MB)"},
                status_code=413,
            )

        # ── Quota check: audio seconds per day ──
        estimated_seconds = len(content) / 4000  # ~32kbps webm estimate
        token_str = get_token(request) or ""
        token_prefix = token_str[:8]
        date_key = date.today().isoformat()
        quota = database.get_or_create_quota(token_prefix, date_key)
        if quota["audio_seconds"] + estimated_seconds > DAILY_AUDIO_SECONDS_LIMIT:
            tmp.close()
            os.unlink(tmp.name)
            database.log_security_event(
                "quota_exceeded", "warning",
                client_ip=request.client.host if request.client else "",
                token_prefix=token_prefix,
                details=f"audio_seconds: current={quota['audio_seconds']:.0f}, estimated={estimated_seconds:.0f}, limit={DAILY_AUDIO_SECONDS_LIMIT}",
                endpoint="/api/upload-audio",
            )
            return JSONResponse(
                {"error": f"Daily audio quota exceeded ({DAILY_AUDIO_SECONDS_LIMIT // 60} min/day)"},
                status_code=429,
            )

        tmp.write(content)
        tmp.close()

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, transcriber.transcribe, tmp.name)

        # Record usage after success
        database.increment_audio_seconds(token_prefix, date_key, estimated_seconds)

        return {"text": text}
    except Exception as e:
        return JSONResponse({"text": "", "error": str(e)}, status_code=500)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# REST: Text-to-speech synthesis
# ---------------------------------------------------------------------------

@app.post("/api/synthesize")
async def synthesize_text(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
        synth_req = SynthesizeRequest(**body)
    except Exception:
        database.log_security_event(
            "invalid_input", "info",
            client_ip=request.client.host if request.client else "",
            endpoint="/api/synthesize",
        )
        return JSONResponse({"error": "Invalid JSON or text too long (max 5000 chars)"}, status_code=400)

    text = synth_req.text.strip()
    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)

    voice = synth_req.voice
    rate = synth_req.rate

    # ── Quota check: TTS chars per day ──
    token_str = get_token(request) or ""
    token_prefix = token_str[:8]
    date_key = date.today().isoformat()
    quota = database.get_or_create_quota(token_prefix, date_key)
    if quota["tts_chars"] + len(text) > DAILY_TTS_CHAR_LIMIT:
        database.log_security_event(
            "quota_exceeded", "warning",
            client_ip=request.client.host if request.client else "",
            token_prefix=token_prefix,
            details=f"tts_chars: current={quota['tts_chars']}, requested={len(text)}, limit={DAILY_TTS_CHAR_LIMIT}",
            endpoint="/api/synthesize",
        )
        return JSONResponse(
            {"error": f"Daily TTS quota exceeded ({DAILY_TTS_CHAR_LIMIT:,} chars/day)"},
            status_code=429,
        )

    audio_path = None
    try:
        audio_path = await synthesizer.synthesize(text, voice=voice, rate=rate)
        if not audio_path:
            return JSONResponse(
                {"error": "Nothing to synthesize (mostly code)"},
                status_code=204,
            )

        # Record usage after success
        database.increment_tts_chars(token_prefix, date_key, len(text))

        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename="speech.mp3",
            background=BackgroundTask(lambda p=audio_path: os.unlink(p)),
        )
    except Exception as e:
        if audio_path:
            try:
                os.unlink(audio_path)
            except OSError:
                pass
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# REST: Message persistence
# ---------------------------------------------------------------------------

@app.get("/api/messages")
async def get_messages(request: Request, cwd: str = "", agent_id: str = "default"):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not cwd:
        return JSONResponse({"error": "cwd parameter is required"}, status_code=400)
    if len(cwd) > MAX_CWD_LENGTH or len(agent_id) > WS_MAX_AGENT_ID_LENGTH:
        return JSONResponse({"error": "Parameter too long"}, status_code=400)
    messages = database.get_messages(cwd, agent_id=agent_id)
    return {"messages": messages}


@app.delete("/api/messages")
async def delete_messages(request: Request, cwd: str = "", agent_id: str = ""):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not cwd:
        return JSONResponse({"error": "cwd parameter is required"}, status_code=400)
    if len(cwd) > MAX_CWD_LENGTH or len(agent_id) > WS_MAX_AGENT_ID_LENGTH:
        return JSONResponse({"error": "Parameter too long"}, status_code=400)
    count = database.clear_messages(cwd, agent_id=agent_id or None)
    return {"deleted": count}


@app.get("/api/metrics")
async def get_metrics(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    metrics = database.get_metrics_data()
    return metrics


# ---------------------------------------------------------------------------
# Conversation History (JSON file-based, max 5)
# ---------------------------------------------------------------------------

HISTORY_DIR = CONFIG_DIR / "history"
HISTORY_GLOB = "*.json"
MAX_CONVERSATIONS = 5


@app.get("/api/history")
async def list_conversations(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    conversations = []
    for f in sorted(HISTORY_DIR.glob(HISTORY_GLOB), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            conversations.append({
                "id": data["id"],
                "createdAt": data["createdAt"],
                "updatedAt": data["updatedAt"],
                "label": data.get("label", ""),
                "cwd": data.get("cwd", ""),
                "messageCount": data.get("messageCount", 0),
                "preview": data.get("preview", ""),
                "totalCost": data.get("totalCost", 0),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return {"conversations": conversations}


@app.post("/api/history")
async def save_conversation(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    conv_id = body.get("id", f"conv_{int(time.time() * 1000)}")
    body["id"] = conv_id

    # Find existing file for this id, or create new filename
    target = None
    for f in HISTORY_DIR.glob(HISTORY_GLOB):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == conv_id:
                target = f
                break
        except (json.JSONDecodeError, OSError):
            continue

    if not target:
        safe_agent = str(body.get("agentId", "default")).replace("/", "_").replace("\\", "_")
        target = HISTORY_DIR / f"{int(time.time() * 1000)}_{safe_agent}.json"

    target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    # Enforce max conversations — delete oldest beyond limit
    deleted = []
    files = sorted(HISTORY_DIR.glob(HISTORY_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[MAX_CONVERSATIONS:]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            deleted.append(data.get("id", f.stem))
        except Exception:
            deleted.append(f.stem)
        f.unlink()

    return {"saved": True, "id": conv_id, "deleted": deleted}


@app.get("/api/history/{conversation_id}")
async def load_conversation(request: Request, conversation_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    for f in HISTORY_DIR.glob(HISTORY_GLOB):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == conversation_id:
                return data
        except (json.JSONDecodeError, OSError):
            continue
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.delete("/api/history/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    for f in HISTORY_DIR.glob(HISTORY_GLOB):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == conversation_id:
                f.unlink()
                return {"deleted": True}
        except (json.JSONDecodeError, OSError):
            continue
    return JSONResponse({"error": "Not found"}, status_code=404)


# ---------------------------------------------------------------------------
# REST API: Memories
# ---------------------------------------------------------------------------

@app.get("/api/memories")
async def api_get_memories(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return {"memories": load_memories()}


@app.post("/api/memories")
async def api_add_memory(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    content = body.get("content", "").strip()
    category = body.get("category", "fact")
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)
    memory = add_memory(content, category)
    return {"memory": memory}


@app.delete("/api/memories/{memory_id}")
async def api_delete_memory(request: Request, memory_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if remove_memory(memory_id):
        return {"deleted": True}
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.delete("/api/memories")
async def api_clear_memories(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    count = clear_memories()
    return {"cleared": count}


# ---------------------------------------------------------------------------
# REST API: Alter Egos
# ---------------------------------------------------------------------------

@app.get("/api/alter-egos")
async def api_get_alter_egos(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return {"egos": load_all_egos(), "active_ego_id": get_active_ego_id()}


@app.post("/api/alter-egos")
async def api_save_alter_ego(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    try:
        path = save_ego(body)
        return {"saved": True, "path": str(path)}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.delete("/api/alter-egos/{ego_id}")
async def api_delete_alter_ego(request: Request, ego_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        if delete_ego(ego_id):
            return {"deleted": True}
        return JSONResponse({"error": "Not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ---------------------------------------------------------------------------
# REST API: Skills Marketplace
# ---------------------------------------------------------------------------

from marketplace import MarketplaceRegistry

_marketplace: MarketplaceRegistry | None = None


def _get_marketplace() -> MarketplaceRegistry:
    global _marketplace
    if _marketplace is None:
        _marketplace = MarketplaceRegistry()
    return _marketplace


@app.get("/api/marketplace/skills")
async def api_marketplace_search(request: Request, q: str = "", category: str = "",
                                  tag: str = "", page: int = 1):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    return mp.search_skills(query=q, category=category, tag=tag, page=page)


@app.get("/api/marketplace/skills/{skill_name}")
async def api_marketplace_skill_info(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    info = mp.get_skill_info(skill_name)
    if not info:
        return JSONResponse({"error": "Skill not found"}, status_code=404)
    installed_version = mp.get_installed_version(skill_name)
    return {"skill": info.__dict__, "installed_version": installed_version}


@app.get("/api/marketplace/categories")
async def api_marketplace_categories(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    return {"categories": [c.__dict__ for c in mp.get_categories()]}


@app.post("/api/marketplace/install/{skill_name}")
async def api_marketplace_install(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    result = await mp.install_skill(skill_name)
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


@app.delete("/api/marketplace/install/{skill_name}")
async def api_marketplace_uninstall(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    result = await mp.uninstall_skill(skill_name)
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


@app.get("/api/marketplace/installed")
async def api_marketplace_installed(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    return {"skills": [s.__dict__ for s in mp.list_installed()]}


@app.get("/api/marketplace/updates")
async def api_marketplace_check_updates(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    return {"updates": mp.check_updates()}


@app.post("/api/marketplace/update/{skill_name}")
async def api_marketplace_update(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    result = await mp.update_skill(skill_name)
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


# ---------------------------------------------------------------------------
# WebSocket: Multi-agent Claude Code interaction
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not verify_token(token):
        # Must accept before sending close code so the browser sees 4001
        await ws.accept()
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()

    # Agent registry: agent_id → { provider, cwd, streaming_task, ... }
    agents: dict[str, dict] = {}
    api_key: str | None = config.get("default_api_key")
    current_provider_name: str = config.get("default_provider", "claude")
    current_model: str = "auto"
    current_ego_id: str = get_active_ego_id()
    last_activity: float = time.time()

    # Sub-agent manager (initialized after send() is defined below)
    subagent_manager = None  # type: ignore[assignment]

    # ── Model Failover ──
    # Stores API keys per provider for automatic failover.
    # Populated from config and updated when user sets keys via WebSocket.
    provider_keys: dict[str, str] = {}
    _cfg_keys = config.get("provider_keys", {})
    if isinstance(_cfg_keys, dict):
        provider_keys.update(_cfg_keys)
    # Ensure the default key is registered for the default provider
    if api_key and current_provider_name:
        provider_keys.setdefault(current_provider_name, api_key)

    PROVIDER_LABELS = {"claude": "Claude", "openai": "OpenAI", "gemini": "Gemini", "ollama": "Ollama"}
    FAILOVER_ORDER = ["claude", "openai", "gemini", "ollama"]

    def get_failover_chain(failed_provider: str) -> list[str]:
        """Return ordered list of fallback providers that have API keys configured."""
        return [
            p for p in FAILOVER_ORDER
            if p != failed_provider and p in provider_keys and provider_keys[p]
        ]

    # Permission request tracking
    pending_permissions: dict[str, asyncio.Event] = {}   # request_id → Event
    permission_responses: dict[str, dict] = {}            # request_id → {approved, pin}

    # ── Voice state per agent ──
    # voice_sessions: agent_id → { vad, mode, audio_buffer, audio_task }
    voice_sessions: dict[str, dict] = {}

    _send_failed = False

    async def send(msg: dict):
        nonlocal _send_failed
        try:
            await ws.send_json(msg)
        except Exception:
            if not _send_failed:
                _send_failed = True
                print(f"[WS] send failed for token={token[:8] if token else '?'}, connection likely closed")

    # Heartbeat loop: ping every 30s, close after idle timeout
    async def heartbeat_loop():
        nonlocal last_activity
        while True:
            await asyncio.sleep(WS_HEARTBEAT_INTERVAL)
            # Check idle timeout
            if time.time() - last_activity > WS_IDLE_TIMEOUT:
                try:
                    await ws.close(code=4002, reason="Idle timeout")
                except Exception:
                    pass
                return
            # Send ping
            await send({"type": "ping", "ts": time.time()})

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    # Notify frontend if API key was pre-loaded from config (setup wizard)
    if api_key:
        await send({
            "type": "api_key_loaded",
            "provider": current_provider_name,
        })

    # ── Sub-agent manager ──
    from subagents import SubAgentManager, create_subagent_handler

    def _get_subagent_provider_config() -> dict:
        """Return current provider config for sub-agent spawning."""
        return {
            "api_key": api_key or "",
            "provider_name": current_provider_name,
            "model": current_model,
            "compose_system_prompt": lambda: compose_system_prompt(current_ego_id),
            "mcp_servers": None,  # Sub-agents don't get MCP by default
            # Permission infrastructure (connection-scoped)
            "pending_permissions": pending_permissions,
            "permission_responses": permission_responses,
            "send_fn": send,
            "classify_fn": classify,
            "get_danger_reason_fn": get_danger_reason,
            "config": config,
        }

    subagent_manager = SubAgentManager(
        agents=agents,
        send_fn=send,
        get_provider_config=_get_subagent_provider_config,
    )

    def _get_active_streaming_agent() -> str | None:
        """Find the agent that currently has an active streaming task."""
        for aid, agent_data in agents.items():
            task = agent_data.get("streaming_task")
            if task and not task.done():
                return aid
        return None

    async def can_use_tool_callback(
        tool_name: str,
        tool_input: dict,
        context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Permission callback invoked by the SDK before each tool execution."""
        level = classify(tool_name, tool_input)
        active_agent_id = _get_active_streaming_agent() or "default"

        # GREEN: auto-approve silently
        if level == PermissionLevel.GREEN:
            database.log_permission_decision(
                active_agent_id, tool_name, tool_input, level.value, "approved",
            )
            return PermissionResultAllow()

        # YELLOW or RED: send permission request to frontend and wait
        request_id = f"perm_{secrets.token_hex(8)}"
        event = asyncio.Event()
        pending_permissions[request_id] = event

        await send({
            "type": "permission_request",
            "request_id": request_id,
            "agent_id": active_agent_id,
            "tool": tool_name,
            "input": tool_input,
            "level": level.value,
            "reason": get_danger_reason(tool_name, tool_input) if level == PermissionLevel.RED else "",
        })

        # Wait for frontend response (5 min timeout)
        try:
            await asyncio.wait_for(event.wait(), timeout=300)
        except asyncio.TimeoutError:
            pending_permissions.pop(request_id, None)
            permission_responses.pop(request_id, None)
            database.log_permission_decision(
                active_agent_id, tool_name, tool_input, level.value, "timeout",
            )
            return PermissionResultDeny(
                message="Permission request timed out (5 minutes). Operation denied."
            )

        response = permission_responses.pop(request_id, {})
        pending_permissions.pop(request_id, None)
        approved = response.get("approved", False)

        # For RED level, verify PIN
        if level == PermissionLevel.RED and approved:
            pin = response.get("pin", "")
            pin_hash = config.get("pin_hash", "")
            try:
                pin_valid = bool(pin) and bcrypt.checkpw(
                    pin.encode("utf-8"), pin_hash.encode("utf-8")
                )
            except Exception:
                pin_valid = False

            if not pin_valid:
                database.log_permission_decision(
                    active_agent_id, tool_name, tool_input, "red", "denied", "invalid_pin",
                )
                return PermissionResultDeny(message="Invalid PIN. Operation denied.")

        if approved:
            database.log_permission_decision(
                active_agent_id, tool_name, tool_input, level.value, "approved",
            )
            return PermissionResultAllow()
        else:
            database.log_permission_decision(
                active_agent_id, tool_name, tool_input, level.value, "denied", "user_denied",
            )
            return PermissionResultDeny(message="Operation denied by user.")

    async def stream_provider_response(provider, agent_id: str, user_text: str | None = None):
        """Stream any provider's response to the frontend. Runs as a background task.

        All providers emit NormalizedEvent objects that map directly to
        the existing WSReceiveMessage types, so the frontend needs no changes.

        If streaming fails and failover providers are available, automatically
        re-initializes with the next provider and replays the user message.
        """
        agent = agents.get(agent_id)
        if not agent:
            return
        cwd = agent.get("cwd")
        accumulated_text = ""

        def flush_text():
            nonlocal accumulated_text
            if accumulated_text and cwd:
                database.save_message(cwd, "assistant", "assistant_text",
                                      {"text": accumulated_text}, agent_id=agent_id)
                accumulated_text = ""

        try:
            async for event in provider.stream_response():
                if event.type == "assistant_text":
                    accumulated_text += event.data.get("text", "")
                    await send({"type": "assistant_text", "agent_id": agent_id, **event.data})

                elif event.type == "tool_use":
                    flush_text()
                    if cwd:
                        database.save_message(cwd, "tool", "tool_use", event.data, agent_id=agent_id)
                    await send({"type": "tool_use", "agent_id": agent_id, **event.data})

                elif event.type == "tool_result":
                    flush_text()
                    if cwd:
                        database.save_message(cwd, "tool", "tool_result", event.data, agent_id=agent_id)
                    # Truncate large content (e.g. base64 screenshots) to avoid WebSocket overflow
                    ws_data = {**event.data}
                    if len(ws_data.get("content", "")) > WS_MAX_TOOL_RESULT_WS:
                        ws_data["content"] = ws_data["content"][:WS_MAX_TOOL_RESULT_WS] + "\n... [truncated for display]"
                    await send({"type": "tool_result", "agent_id": agent_id, **ws_data})

                elif event.type == "model_info":
                    await send({"type": "model_info", "agent_id": agent_id, **event.data})

                elif event.type == "result":
                    flush_text()
                    if cwd:
                        database.save_message(cwd, "assistant", "result", event.data, agent_id=agent_id)
                    await send({"type": "result", "agent_id": agent_id, **event.data})

                    # Fetch & send rate limits (Anthropic only)
                    if provider.provider_name == "claude" and api_key:
                        rl = await fetch_rate_limits(api_key)
                        if rl:
                            await send({"type": "rate_limits", "agent_id": agent_id, "limits": rl})

                elif event.type == "status":
                    await send({"type": "status", "agent_id": agent_id, **event.data})

                elif event.type == "error":
                    flush_text()
                    await send({"type": "error", "agent_id": agent_id, **event.data})

        except asyncio.CancelledError:
            flush_text()
        except Exception as e:
            flush_text()
            # ── Streaming failover ──
            # If we have fallback providers and a user message to replay, try them.
            failed_name = agent.get("provider_name", current_provider_name)
            fallbacks = get_failover_chain(failed_name)
            if user_text and fallbacks and cwd:
                for fb_name in fallbacks:
                    fb_label = PROVIDER_LABELS.get(fb_name, fb_name)
                    try:
                        await send({
                            "type": "status", "agent_id": agent_id,
                            "text": f"Provider error. Failing over to {fb_label}...",
                        })
                        fb_provider = get_provider(fb_name)
                        await fb_provider.initialize(
                            api_key=provider_keys[fb_name],
                            model="auto",
                            cwd=cwd,
                            system_prompt=compose_system_prompt(current_ego_id),
                            can_use_tool=can_use_tool_callback if fb_name == "claude" else tool_permission_callback,
                            mcp_servers=mcp_servers if fb_name == "claude" else None,
                        )
                        # Update agent with new provider
                        agents[agent_id]["provider"] = fb_provider
                        agents[agent_id]["provider_name"] = fb_name
                        await fb_provider.send_message(user_text)
                        await send({
                            "type": "status", "agent_id": agent_id,
                            "text": f"Failover active: now using {fb_label}",
                        })
                        # Stream from failover provider (no further failover)
                        async for event in fb_provider.stream_response():
                            if event.type == "assistant_text":
                                accumulated_text += event.data.get("text", "")
                                await send({"type": "assistant_text", "agent_id": agent_id, **event.data})
                            elif event.type == "tool_use":
                                flush_text()
                                if cwd:
                                    database.save_message(cwd, "tool", "tool_use", event.data, agent_id=agent_id)
                                await send({"type": "tool_use", "agent_id": agent_id, **event.data})
                            elif event.type == "tool_result":
                                flush_text()
                                if cwd:
                                    database.save_message(cwd, "tool", "tool_result", event.data, agent_id=agent_id)
                                ws_data = {**event.data}
                                if len(ws_data.get("content", "")) > WS_MAX_TOOL_RESULT_WS:
                                    ws_data["content"] = ws_data["content"][:WS_MAX_TOOL_RESULT_WS] + "\n... [truncated for display]"
                                await send({"type": "tool_result", "agent_id": agent_id, **ws_data})
                            elif event.type == "result":
                                flush_text()
                                if cwd:
                                    database.save_message(cwd, "assistant", "result", event.data, agent_id=agent_id)
                                await send({"type": "result", "agent_id": agent_id, **event.data})
                            elif event.type == "status":
                                await send({"type": "status", "agent_id": agent_id, **event.data})
                            elif event.type == "error":
                                flush_text()
                                await send({"type": "error", "agent_id": agent_id, **event.data})
                        flush_text()
                        return  # Failover succeeded
                    except Exception:
                        continue
                # All failovers failed
                await send({"type": "error", "agent_id": agent_id, "text": f"All providers failed. Original error: {e}"})
            else:
                await send({"type": "error", "agent_id": agent_id, "text": str(e)})

    async def cancel_agent_streaming(agent_id: str):
        """Cancel the streaming task for a specific agent."""
        agent = agents.get(agent_id)
        if not agent:
            return
        task = agent.get("streaming_task")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if agent_id in agents:
            agents[agent_id]["streaming_task"] = None

    async def cancel_computer_use_task(agent_id: str):
        """Cancel a running computer use agent loop."""
        agent = agents.get(agent_id)
        if not agent:
            return
        task = agent.get("computer_task")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if agent_id in agents:
            agents[agent_id]["computer_task"] = None
        # Release held keys/mouse
        executor = agent.get("computer_executor")
        if executor:
            executor.release_all()

    async def destroy_agent(agent_id: str):
        """Fully disconnect and remove an agent (and its sub-agents)."""
        # First, clean up any sub-agents spawned by this agent
        if subagent_manager:
            await subagent_manager.cleanup_children(agent_id)

        await cancel_agent_streaming(agent_id)
        await cancel_computer_use_task(agent_id)
        agent = agents.pop(agent_id, None)
        if agent and agent.get("provider"):
            provider = agent["provider"]
            # Release browser page for this agent via the ToolExecutor
            if hasattr(provider, '_tool_executor') and provider._tool_executor:
                try:
                    await provider._tool_executor.cleanup()
                except Exception:
                    pass
            try:
                await provider.disconnect()
            except Exception:
                pass

    # ── Computer Use agent loop ─────────────────────────────────────
    async def _computer_use_loop(
        agent_id: str,
        user_text: str,
        api_key_str: str,
        executor: "ComputerUseExecutor",
        send_ws,
        agents_ref: dict,
        pending_perms: dict,
        perm_responses: dict,
    ):
        """Agent loop for Computer Use mode.

        Sends messages to Claude API with the computer tool and executes
        actions on the local PC, streaming screenshots to the frontend.
        """
        client = AsyncAnthropic(api_key=api_key_str)

        tools = [
            executor.get_tool_definition(),
            {"type": "bash_20250124", "name": "bash"},
            {"type": "text_editor_20250124", "name": "str_replace_based_edit_tool"},
        ]

        # Initial screenshot for context
        initial_screenshot = await executor.take_screenshot()
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": initial_screenshot,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ]

        # Send initial screenshot to frontend
        await send_ws({
            "type": "computer_screenshot",
            "agent_id": agent_id,
            "image": initial_screenshot,
            "action": "initial",
            "description": "Estado inicial de la pantalla",
            "iteration": 0,
        })

        iterations = 0
        total_input_tokens = 0
        total_output_tokens = 0
        start_time = time.time()

        try:
            while iterations < COMPUTER_USE_MAX_ITERATIONS:
                iterations += 1

                response = await client.beta.messages.create(
                    model=COMPUTER_USE_MODEL,
                    max_tokens=COMPUTER_USE_MAX_TOKENS,
                    system=COMPUTER_USE_SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                    betas=[COMPUTER_USE_BETA],
                )

                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

                # Build assistant content for conversation history
                assistant_content = []
                for block in response.content:
                    assistant_content.append(block)

                messages.append({"role": "assistant", "content": response.content})

                tool_results = []

                for block in response.content:
                    # Text blocks
                    if hasattr(block, "text") and block.type == "text":
                        await send_ws({
                            "type": "assistant_text",
                            "agent_id": agent_id,
                            "text": block.text,
                        })

                    # Tool use blocks
                    elif block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input if hasattr(block, "input") else {}

                        action_desc = describe_action(tool_name, tool_input)

                        # Send action preview to frontend
                        await send_ws({
                            "type": "computer_action",
                            "agent_id": agent_id,
                            "tool": tool_name,
                            "action": tool_input.get("action", tool_name),
                            "input": tool_input,
                            "description": action_desc,
                            "iteration": iterations,
                        })

                        # ── Permission check via existing system ──
                        level = classify(tool_name, tool_input)

                        # For computer tool, always request permission unless screenshot
                        if tool_name == "computer" and tool_input.get("action") != "screenshot":
                            if level == PermissionLevel.GREEN:
                                level = PermissionLevel.YELLOW

                        if level != PermissionLevel.GREEN:
                            request_id = f"perm_{secrets.token_hex(8)}"
                            event = asyncio.Event()
                            pending_perms[request_id] = event

                            await send_ws({
                                "type": "permission_request",
                                "request_id": request_id,
                                "agent_id": agent_id,
                                "tool": f"computer:{tool_input.get('action', tool_name)}" if tool_name == "computer" else tool_name,
                                "input": tool_input,
                                "level": level.value,
                                "reason": action_desc if level == PermissionLevel.RED else "",
                            })

                            try:
                                await asyncio.wait_for(event.wait(), timeout=300)
                            except asyncio.TimeoutError:
                                pending_perms.pop(request_id, None)
                                perm_responses.pop(request_id, None)
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": "Permission request timed out.",
                                    "is_error": True,
                                })
                                database.log_permission_decision(
                                    agent_id, tool_name, tool_input, level.value, "timeout",
                                )
                                continue

                            resp = perm_responses.pop(request_id, {})
                            pending_perms.pop(request_id, None)
                            approved = resp.get("approved", False)

                            # PIN check for RED level
                            if level == PermissionLevel.RED and approved:
                                pin_val = resp.get("pin", "")
                                pin_hash = config.get("pin_hash", "")
                                try:
                                    pin_valid = bool(pin_val) and bcrypt.checkpw(
                                        pin_val.encode("utf-8"), pin_hash.encode("utf-8")
                                    )
                                except Exception:
                                    pin_valid = False
                                if not pin_valid:
                                    approved = False

                            if not approved:
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": "Action denied by user.",
                                    "is_error": True,
                                })
                                database.log_permission_decision(
                                    agent_id, tool_name, tool_input, level.value, "denied",
                                )
                                continue

                            database.log_permission_decision(
                                agent_id, tool_name, tool_input, level.value, "approved",
                            )

                        # ── Execute the action ──
                        if tool_name == "computer":
                            action = tool_input.get("action", "screenshot")
                            result_content = await executor.execute_action(action, tool_input)

                            # Send screenshot to frontend
                            for item in result_content:
                                if item.get("type") == "image":
                                    await send_ws({
                                        "type": "computer_screenshot",
                                        "agent_id": agent_id,
                                        "image": item["source"]["data"],
                                        "action": action,
                                        "description": action_desc,
                                        "iteration": iterations,
                                    })

                        elif tool_name == "bash":
                            cmd = tool_input.get("command", "")
                            try:
                                proc = await asyncio.create_subprocess_shell(
                                    cmd,
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE,
                                )
                                stdout, stderr = await asyncio.wait_for(
                                    proc.communicate(), timeout=30,
                                )
                                output = (stdout or b"").decode(errors="replace") + (stderr or b"").decode(errors="replace")
                                result_content = [{"type": "text", "text": output[:10000]}]
                            except asyncio.TimeoutError:
                                result_content = [{"type": "text", "text": "Command timed out (30s)."}]
                            except Exception as e:
                                result_content = [{"type": "text", "text": f"Error: {e}"}]

                        elif tool_name == "str_replace_based_edit_tool":
                            # Text editor tool — not yet implemented in computer use mode
                            result_content = [{"type": "text", "text": "Text editor tool not yet implemented in computer use mode. Use Bash instead."}]

                        else:
                            result_content = [{"type": "text", "text": f"Unknown tool: {tool_name}"}]

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_content,
                        })

                # If no tools were used, Claude is done
                if not tool_results:
                    break

                messages.append({"role": "user", "content": tool_results})

            # ── Send final result ──
            elapsed_ms = int((time.time() - start_time) * 1000)
            input_cost = total_input_tokens * 3.0 / 1_000_000
            output_cost = total_output_tokens * 15.0 / 1_000_000
            total_cost = input_cost + output_cost

            await send_ws({
                "type": "result",
                "agent_id": agent_id,
                "text": "",
                "session_id": None,
                "cost": round(total_cost, 4),
                "duration_ms": elapsed_ms,
                "num_turns": iterations,
                "is_error": False,
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                },
            })

        except asyncio.CancelledError:
            await send_ws({
                "type": "result",
                "agent_id": agent_id,
                "text": "Computer use cancelled.",
                "session_id": None,
                "cost": None,
                "duration_ms": None,
                "num_turns": iterations,
                "is_error": False,
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            await send_ws({
                "type": "error",
                "agent_id": agent_id,
                "text": f"Computer use error: {str(e)}",
            })

    # ── End of computer use loop ─────────────────────────────────────

    try:
        await send({"type": "status", "agent_id": None, "text": "Connected. Select a project directory."})

        while True:
            raw = await ws.receive_text()
            last_activity = time.time()

            # ── 6a. Message size limit (16 KB) ──
            if len(raw) > WS_MAX_MESSAGE_BYTES:
                database.log_security_event(
                    "ws_message_too_large", "warning",
                    token_prefix=token[:8] if token else "",
                    details=f"size={len(raw)}, limit={WS_MAX_MESSAGE_BYTES}",
                )
                await send({"type": "error", "agent_id": "default", "text": "Message too large"})
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                database.log_security_event(
                    "invalid_json", "warning",
                    token_prefix=token[:8] if token else "",
                )
                await send({"type": "error", "agent_id": "default", "text": "Invalid JSON"})
                continue
            msg_type = data.get("type", "")
            agent_id = data.get("agent_id", "default")

            # ── Pong response — skip processing ──
            if msg_type == "pong":
                continue

            # ── 6b. WebSocket field validation ──
            if len(str(msg_type)) > WS_MAX_MSG_TYPE_LENGTH or len(str(agent_id)) > WS_MAX_AGENT_ID_LENGTH:
                database.log_security_event(
                    "invalid_input", "info",
                    token_prefix=token[:8] if token else "",
                    details=f"type_len={len(str(msg_type))}, agent_id_len={len(str(agent_id))}",
                )
                await send({"type": "error", "agent_id": agent_id, "text": "Invalid field length"})
                continue

            # ── 6c. WebSocket rate limiting (60/min) ──
            rl_result = rate_limiter.check(token or "", EndpointCategory.WEBSOCKET_MSG)
            if not rl_result.allowed:
                database.log_security_event(
                    "ws_rate_limited", "warning",
                    token_prefix=token[:8] if token else "",
                    details=f"limit={rl_result.limit}",
                )
                await send({
                    "type": "error", "agent_id": agent_id,
                    "text": f"Rate limit exceeded. Retry in {int(rl_result.retry_after)}s",
                })
                continue

            # ---- Set API key (global, not per-agent) ----
            if msg_type == "set_api_key":
                auth_mode = data.get("auth_mode", "api_key")

                if auth_mode == "oauth":
                    # Personal account mode — no API key needed, SDK uses ~/.claude/.credentials.json
                    api_key = ""
                    current_provider_name = "claude"
                    current_model = data.get("model", "auto")
                    await send({"type": "api_key_loaded", "provider": "claude"})
                    await send({"type": "status", "agent_id": agent_id, "text": "Using personal Claude account (Max/Pro)."})
                else:
                    key = data.get("key", "").strip()
                    if not key:
                        await send({"type": "error", "agent_id": agent_id, "text": "API key is required."})
                        continue
                    if len(key) > WS_MAX_KEY_LENGTH:
                        await send({"type": "error", "agent_id": agent_id, "text": "API key too long."})
                        continue
                    api_key = key
                    current_provider_name = data.get("provider", "claude")
                    current_model = data.get("model", "auto")
                    # Store key for failover
                    provider_keys[current_provider_name] = key
                    provider_label = PROVIDER_LABELS.get(current_provider_name, current_provider_name)
                    await send({"type": "status", "agent_id": agent_id, "text": f"API key set for {provider_label}."})

            # ---- Set transcription language ----
            elif msg_type == "set_transcription_lang":
                lang = data.get("lang", "").strip()
                if lang in ("en", "es"):
                    transcriber.language = lang
                    await send({"type": "status", "agent_id": agent_id, "text": f"Transcription language set to {lang}."})

            # ---- Set working directory for an agent ----
            elif msg_type == "set_cwd":
                new_cwd = data.get("path", "")

                # Accept model/provider overrides from frontend
                if data.get("model"):
                    current_model = data["model"]
                if data.get("provider"):
                    current_provider_name = data["provider"]

                if len(new_cwd) > WS_MAX_PATH_LENGTH:
                    await send({"type": "error", "agent_id": agent_id, "text": "Path too long."})
                    continue

                cwd_path = Path(new_cwd)

                if not cwd_path.is_dir():
                    await send({"type": "error", "agent_id": agent_id, "text": f"Not a directory: {new_cwd}"})
                    continue

                # ── 6d. Max concurrent agents (exclude sub-agents) ──
                regular_count = sum(
                    1 for a in agents.values() if not a.get("is_subagent")
                )
                if agent_id not in agents and regular_count >= WS_MAX_CONCURRENT_AGENTS:
                    await send({
                        "type": "error", "agent_id": agent_id,
                        "text": f"Max {WS_MAX_CONCURRENT_AGENTS} concurrent agents reached. Close one first.",
                    })
                    continue

                # Destroy previous agent with this id if exists
                if agent_id in agents:
                    await destroy_agent(agent_id)

                resolved_cwd = str(cwd_path.resolve())
                resume_session_id = data.get("session_id")

                # Load MCP server configuration (graceful degradation)
                mcp_servers = _load_mcp_config()

                # Permission callback for non-Claude providers
                async def tool_permission_callback(tool_name: str, _tool_name2: str, tool_input: dict) -> bool:
                    """Adapted permission callback for OpenAI/Gemini providers."""
                    # Map custom tool names to permission classifier names
                    tool_map = {
                        "read_file": "Read", "list_directory": "Read",
                        "search_files": "Glob", "grep_search": "Grep",
                        "write_file": "Write", "edit_file": "Edit",
                        "bash": "Bash",
                        "browser_navigate": "browser_navigate",
                        "browser_screenshot": "browser_screenshot",
                        "browser_click": "browser_click",
                        "browser_type": "browser_type",
                        "browser_extract_text": "browser_extract_text",
                        "browser_scroll": "browser_scroll",
                        "browser_close": "browser_close",
                    }
                    classifier_name = tool_map.get(tool_name, tool_name)
                    level = classify(classifier_name, tool_input)

                    if level == PermissionLevel.GREEN:
                        return True

                    # YELLOW/RED: send permission request to frontend and wait
                    request_id = f"perm_{secrets.token_hex(8)}"
                    active_aid = _get_active_streaming_agent() or agent_id
                    event = asyncio.Event()
                    pending_permissions[request_id] = event

                    await send({
                        "type": "permission_request",
                        "request_id": request_id,
                        "agent_id": active_aid,
                        "tool": tool_name,
                        "input": tool_input,
                        "level": level.value,
                        "reason": get_danger_reason(classifier_name, tool_input) if level == PermissionLevel.RED else "",
                    })

                    try:
                        await asyncio.wait_for(event.wait(), timeout=300)
                    except asyncio.TimeoutError:
                        pending_permissions.pop(request_id, None)
                        permission_responses.pop(request_id, None)
                        return False

                    response = permission_responses.pop(request_id, {})
                    pending_permissions.pop(request_id, None)
                    approved = response.get("approved", False)

                    if level == PermissionLevel.RED and approved:
                        pin = response.get("pin", "")
                        pin_hash = config.get("pin_hash", "")
                        try:
                            pin_valid = bool(pin) and bcrypt.checkpw(pin.encode(), pin_hash.encode())
                        except Exception:
                            pin_valid = False
                        if not pin_valid:
                            return False

                    return approved

                # Create provider via factory — with automatic failover
                async def _try_init_provider(prov_name: str, prov_key: str) -> tuple:
                    """Try to initialize a provider. Returns (provider, prov_name) or raises."""
                    prov = get_provider(prov_name)
                    await prov.initialize(
                        api_key=prov_key,
                        model=current_model if prov_name == current_provider_name else "auto",
                        cwd=resolved_cwd,
                        system_prompt=compose_system_prompt(current_ego_id),
                        can_use_tool=can_use_tool_callback if prov_name == "claude" else tool_permission_callback,
                        resume_session_id=resume_session_id if prov.supports_session_resumption() else None,
                        mcp_servers=mcp_servers if prov_name == "claude" else None,
                        agent_id=agent_id,
                    )
                    return prov, prov_name

                init_provider_name = current_provider_name
                provider = None
                try:
                    provider, init_provider_name = await _try_init_provider(
                        current_provider_name, api_key or ""
                    )
                except Exception as primary_err:
                    # Try failover providers
                    fallbacks = get_failover_chain(current_provider_name)
                    failover_succeeded = False
                    for fb_name in fallbacks:
                        fb_label = PROVIDER_LABELS.get(fb_name, fb_name)
                        try:
                            await send({
                                "type": "status", "agent_id": agent_id,
                                "text": f"Primary provider failed. Trying {fb_label}...",
                            })
                            provider, init_provider_name = await _try_init_provider(
                                fb_name, provider_keys[fb_name]
                            )
                            failover_succeeded = True
                            await send({
                                "type": "status", "agent_id": agent_id,
                                "text": f"Failover: switched to {fb_label}",
                            })
                            break
                        except Exception:
                            continue

                    if not failover_succeeded:
                        await send({
                            "type": "error", "agent_id": agent_id,
                            "text": f"Provider init failed: {primary_err} (no fallback available)",
                        })
                        continue

                agents[agent_id] = {
                    "provider": provider,
                    "provider_name": init_provider_name,
                    "cwd": resolved_cwd,
                    "streaming_task": None,
                    # Computer Use fields
                    "mode": "coding",
                    "computer_executor": None,
                    "computer_task": None,
                }

                # Inject sub-agent handler into the provider's ToolExecutor
                if hasattr(provider, '_tool_executor') and provider._tool_executor:
                    sa_handler = create_subagent_handler(subagent_manager, agent_id)
                    provider._tool_executor._handlers["manage_subagents"] = sa_handler

                provider_label = PROVIDER_LABELS.get(init_provider_name, init_provider_name)
                await send({
                    "type": "status",
                    "agent_id": agent_id,
                    "text": f"Ready ({provider_label}). Project: {cwd_path.name}",
                    "cwd": resolved_cwd,
                })

            # ---- Send message to a specific agent ----
            elif msg_type == "send_message":
                text = data.get("text", "").strip()
                if not text:
                    continue
                if len(text) > WS_MAX_TEXT_LENGTH:
                    await send({"type": "error", "agent_id": agent_id, "text": f"Message too long (max {WS_MAX_TEXT_LENGTH} chars)."})
                    continue

                agent = agents.get(agent_id)
                if not agent or not agent.get("provider"):
                    await send({"type": "error", "agent_id": agent_id, "text": "No project directory selected for this agent."})
                    continue

                # Persist user message
                if agent.get("cwd"):
                    database.save_message(agent["cwd"], "user", "text", {"text": text}, agent_id=agent_id)

                # ── Computer Use mode: separate agent loop (Claude only) ──
                if agent.get("mode") == "computer_use" and COMPUTER_USE_AVAILABLE:
                    await cancel_computer_use_task(agent_id)
                    await send({"type": "status", "agent_id": agent_id, "text": "Rain is controlling the PC..."})

                    cu_task = asyncio.create_task(
                        _computer_use_loop(
                            agent_id=agent_id,
                            user_text=text,
                            api_key_str=api_key or "",
                            executor=agent["computer_executor"],
                            send_ws=send,
                            agents_ref=agents,
                            pending_perms=pending_permissions,
                            perm_responses=permission_responses,
                        )
                    )
                    agents[agent_id]["computer_task"] = cu_task
                    continue

                # ── Coding mode (default): existing flow ──
                # Cancel any previous streaming for this agent
                await cancel_agent_streaming(agent_id)

                await send({"type": "status", "agent_id": agent_id, "text": "Rain is working..."})

                try:
                    provider = agent["provider"]
                    await provider.send_message(text)
                    task = asyncio.create_task(
                        stream_provider_response(provider, agent_id, user_text=text)
                    )
                    agents[agent_id]["streaming_task"] = task
                except Exception as e:
                    await send({"type": "error", "agent_id": agent_id, "text": str(e)})

            # ---- Interrupt a specific agent ----
            elif msg_type == "interrupt":
                agent = agents.get(agent_id)
                if agent and agent.get("provider"):
                    try:
                        await agent["provider"].interrupt()
                    except Exception:
                        pass

                await cancel_agent_streaming(agent_id)

                await send({
                    "type": "result",
                    "agent_id": agent_id,
                    "text": "Interrupted by user.",
                    "session_id": None,
                    "cost": None,
                    "duration_ms": None,
                    "num_turns": None,
                    "is_error": False,
                })

            # ---- Destroy / close a specific agent ----
            elif msg_type == "destroy_agent":
                await destroy_agent(agent_id)
                await send({"type": "agent_destroyed", "agent_id": agent_id})

            # ---- Set agent mode (coding / computer_use) ----
            elif msg_type == "set_mode":
                mode = data.get("mode", "coding")
                agent = agents.get(agent_id)
                if not agent:
                    await send({"type": "error", "agent_id": agent_id, "text": "Agent not found."})
                    continue

                if mode == "computer_use":
                    if not COMPUTER_USE_AVAILABLE:
                        await send({"type": "error", "agent_id": agent_id, "text": "Computer Use not available. Install: pip install anthropic pyautogui mss Pillow pyperclip"})
                        continue
                    if not api_key:
                        await send({"type": "error", "agent_id": agent_id, "text": "API key required for Computer Use mode."})
                        continue
                    # Computer Use only works with Claude
                    provider = agent.get("provider")
                    if provider and not provider.supports_computer_use():
                        await send({"type": "error", "agent_id": agent_id, "text": "Computer Use is only available with Claude."})
                        continue

                    executor = ComputerUseExecutor()
                    agents[agent_id]["mode"] = "computer_use"
                    agents[agent_id]["computer_executor"] = executor
                    await send({
                        "type": "mode_changed",
                        "agent_id": agent_id,
                        "mode": "computer_use",
                        "display_info": executor.get_display_info(),
                    })
                else:
                    # Switch back to coding
                    await cancel_computer_use_task(agent_id)
                    agents[agent_id]["mode"] = "coding"
                    agents[agent_id]["computer_executor"] = None
                    await send({
                        "type": "mode_changed",
                        "agent_id": agent_id,
                        "mode": "coding",
                    })

            # ---- Emergency stop for computer use ----
            elif msg_type == "emergency_stop":
                agent = agents.get(agent_id)
                if agent:
                    await cancel_computer_use_task(agent_id)
                    await cancel_agent_streaming(agent_id)
                    await send({
                        "type": "status",
                        "agent_id": agent_id,
                        "text": "EMERGENCY STOP - All actions halted.",
                    })
                    database.log_security_event(
                        "computer_use_emergency_stop", "critical",
                        client_ip="local",
                        token_prefix=token[:8] if token else "",
                        details=f"Emergency stop for agent {agent_id}",
                    )

            # ---- Switch alter ego ----
            elif msg_type == "set_alter_ego":
                new_ego_id = data.get("ego_id", "rain")
                ego = load_ego(new_ego_id)
                if not ego:
                    await send({"type": "error", "agent_id": agent_id, "text": f"Alter ego '{new_ego_id}' not found."})
                    continue

                current_ego_id = new_ego_id
                set_active_ego_id(new_ego_id)
                new_prompt = compose_system_prompt(current_ego_id)

                # Load MCP config for re-init (graceful degradation)
                _mcp_servers = _load_mcp_config()

                # Re-initialize all active agents with the new system prompt
                for aid, agent_data in list(agents.items()):
                    saved_cwd = agent_data["cwd"]
                    saved_mode = agent_data.get("mode", "coding")

                    # Cancel any running tasks
                    task = agent_data.get("streaming_task")
                    if task and not task.done():
                        task.cancel()

                    # Disconnect old provider
                    if agent_data.get("provider"):
                        try:
                            await agent_data["provider"].disconnect()
                        except Exception:
                            pass

                    # Create new provider with new prompt
                    provider = get_provider(current_provider_name)
                    try:
                        await provider.initialize(
                            api_key=api_key or "",
                            model=current_model,
                            cwd=saved_cwd,
                            system_prompt=new_prompt,
                            can_use_tool=can_use_tool_callback,
                            mcp_servers=_mcp_servers if current_provider_name == "claude" else None,
                        )
                    except Exception as e:
                        await send({"type": "error", "agent_id": aid, "text": f"Failed to re-init with new ego: {e}"})
                        continue

                    agents[aid] = {
                        "provider": provider,
                        "cwd": saved_cwd,
                        "streaming_task": None,
                        "mode": saved_mode,
                        "computer_executor": None,
                        "computer_task": None,
                    }

                await send({
                    "type": "alter_ego_changed",
                    "ego_id": new_ego_id,
                    "agent_id": agent_id,
                })
                await send({
                    "type": "status",
                    "agent_id": agent_id,
                    "text": f"{ego.get('emoji', '🤖')} Switched to {ego['name']}",
                })

            # ---- Permission response from frontend ----
            # ── Voice: set voice mode ──
            elif msg_type == "voice_mode_set":
                mode = data.get("mode", "push-to-talk")
                if mode not in ("push-to-talk", "vad", "talk-mode", "wake-word"):
                    await send({"type": "error", "agent_id": agent_id, "text": "Invalid voice mode."})
                    continue
                if mode != "push-to-talk" and not VOICE_AVAILABLE:
                    await send({
                        "type": "error", "agent_id": agent_id,
                        "text": "Voice features unavailable. Install with: pip install rain-assistant[voice]",
                    })
                    continue

                # Initialize or update voice session for this agent
                vs = voice_sessions.get(agent_id)
                if vs and vs.get("audio_task") and not vs["audio_task"].done():
                    vs["audio_task"].cancel()

                if mode == "push-to-talk":
                    voice_sessions.pop(agent_id, None)
                else:
                    vs_data: dict = {
                        "mode": mode,
                        "vad": VoiceActivityDetector(
                            threshold=data.get("vad_threshold", 0.5),
                            min_silence_ms=data.get("silence_timeout", 800),
                        ),
                        "audio_buffer": bytearray(),
                        "is_recording": False,
                        "audio_task": None,
                        "wake_active": False,
                    }
                    if mode == "wake-word":
                        vs_data["wake_word"] = WakeWordDetector()
                        vs_data["wake_active"] = False  # waiting for wake word
                    voice_sessions[agent_id] = vs_data

                await send({
                    "type": "voice_mode_changed", "agent_id": agent_id,
                    "mode": mode,
                })

            # ── Voice: process audio chunk ──
            elif msg_type == "audio_chunk":
                vs = voice_sessions.get(agent_id)
                if not vs or not VOICE_AVAILABLE:
                    continue

                import base64
                try:
                    pcm_data = base64.b64decode(data.get("data", ""))
                except Exception:
                    continue

                if len(pcm_data) == 0:
                    continue

                vad: VoiceActivityDetector = vs["vad"]
                chunk_size = VoiceActivityDetector.CHUNK_SAMPLES * 2  # 1024 bytes

                # ── Wake word gate: if in wake-word mode, check wake word first ──
                wake_detector = vs.get("wake_word")
                if wake_detector and not vs.get("wake_active"):
                    ww_chunk_size = WakeWordDetector.FRAME_SAMPLES * 2  # 2560 bytes
                    vs["ww_buffer"] = vs.get("ww_buffer", bytearray())
                    vs["ww_buffer"].extend(pcm_data)
                    while len(vs["ww_buffer"]) >= ww_chunk_size:
                        ww_chunk = bytes(vs["ww_buffer"][:ww_chunk_size])
                        vs["ww_buffer"] = vs["ww_buffer"][ww_chunk_size:]
                        detected, confidence = wake_detector.process_chunk(ww_chunk)
                        if detected:
                            vs["wake_active"] = True
                            await send({
                                "type": "wake_word_detected",
                                "agent_id": agent_id,
                                "confidence": round(confidence, 3),
                            })
                            break
                    if not vs.get("wake_active"):
                        continue  # Still waiting for wake word, skip VAD

                # Process audio in VAD-sized chunks
                vs["audio_buffer_raw"] = vs.get("audio_buffer_raw", bytearray())
                vs["audio_buffer_raw"].extend(pcm_data)

                while len(vs["audio_buffer_raw"]) >= chunk_size:
                    chunk = bytes(vs["audio_buffer_raw"][:chunk_size])
                    vs["audio_buffer_raw"] = vs["audio_buffer_raw"][chunk_size:]

                    event = vad.process_chunk(chunk)

                    if event == VADEvent.SPEECH_START:
                        vs["is_recording"] = True
                        vs["audio_buffer"] = bytearray(chunk)
                        await send({
                            "type": "vad_event", "agent_id": agent_id,
                            "event": "speech_start",
                        })

                    elif event == VADEvent.SPEECH_ONGOING and vs["is_recording"]:
                        vs["audio_buffer"].extend(chunk)

                    elif event == VADEvent.SPEECH_END and vs["is_recording"]:
                        vs["audio_buffer"].extend(chunk)
                        vs["is_recording"] = False
                        await send({
                            "type": "vad_event", "agent_id": agent_id,
                            "event": "speech_end",
                        })

                        # Transcribe the accumulated speech
                        audio_bytes = bytes(vs["audio_buffer"])
                        vs["audio_buffer"] = bytearray()

                        async def _transcribe_voice(ab: bytes, aid: str):
                            """Save PCM buffer to temp WAV and transcribe."""
                            import struct
                            import wave

                            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                            try:
                                with wave.open(tmp.name, "wb") as wf:
                                    wf.setnchannels(1)
                                    wf.setsampwidth(2)
                                    wf.setframerate(16000)
                                    wf.writeframes(ab)
                                loop = asyncio.get_event_loop()
                                text = await loop.run_in_executor(
                                    None, transcriber.transcribe, tmp.name
                                )
                                if text and text.strip():
                                    await send({
                                        "type": "voice_transcription",
                                        "agent_id": aid,
                                        "text": text.strip(),
                                        "is_final": True,
                                    })
                                else:
                                    await send({
                                        "type": "vad_event", "agent_id": aid,
                                        "event": "no_speech",
                                    })
                            except Exception as exc:
                                await send({
                                    "type": "error", "agent_id": aid,
                                    "text": f"Transcription error: {exc}",
                                })
                            finally:
                                try:
                                    os.unlink(tmp.name)
                                except OSError:
                                    pass

                        vs["audio_task"] = asyncio.create_task(
                            _transcribe_voice(audio_bytes, agent_id)
                        )

            # ── Voice: talk mode start/stop ──
            elif msg_type == "talk_mode_start":
                if not VOICE_AVAILABLE:
                    await send({
                        "type": "error", "agent_id": agent_id,
                        "text": "Voice features unavailable. Install with: pip install rain-assistant[voice]",
                    })
                    continue
                # Initialize talk session with VAD
                vs = voice_sessions.get(agent_id)
                if not vs:
                    voice_sessions[agent_id] = {
                        "mode": "talk-mode",
                        "vad": VoiceActivityDetector(),
                        "audio_buffer": bytearray(),
                        "is_recording": False,
                        "audio_task": None,
                        "talk_active": True,
                    }
                else:
                    vs["mode"] = "talk-mode"
                    vs["talk_active"] = True
                await send({
                    "type": "talk_state_changed", "agent_id": agent_id,
                    "state": "listening",
                })

            elif msg_type == "talk_mode_stop":
                vs = voice_sessions.get(agent_id)
                if vs:
                    vs["talk_active"] = False
                    vs["is_recording"] = False
                    vs["audio_buffer"] = bytearray()
                    vs["vad"].reset()
                    if vs.get("audio_task") and not vs["audio_task"].done():
                        vs["audio_task"].cancel()
                await send({
                    "type": "talk_state_changed", "agent_id": agent_id,
                    "state": "idle",
                })

            # ── Voice: interruption (user speaks during TTS) ──
            elif msg_type == "talk_interruption":
                vs = voice_sessions.get(agent_id)
                if vs and vs.get("talk_active"):
                    vs["is_recording"] = False
                    vs["audio_buffer"] = bytearray()
                    vs["vad"].reset()
                    await send({
                        "type": "talk_state_changed", "agent_id": agent_id,
                        "state": "listening",
                    })

            elif msg_type == "permission_response":
                request_id = data.get("request_id", "")
                if request_id in pending_permissions:
                    permission_responses[request_id] = {
                        "approved": data.get("approved", False),
                        "pin": data.get("pin"),
                    }
                    pending_permissions[request_id].set()
                else:
                    await send({
                        "type": "error",
                        "agent_id": agent_id,
                        "text": "Permission request expired or not found.",
                    })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        import traceback
        traceback.print_exc()
        database.log_security_event(
            "ws_unhandled_error", "error",
            token_prefix=token[:8] if token else "",
            details=str(exc)[:500],
        )
    finally:
        # Cancel heartbeat
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        # Cleanup voice sessions
        for vs in voice_sessions.values():
            task = vs.get("audio_task")
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        voice_sessions.clear()

        # Release pending permission waiters
        for evt in pending_permissions.values():
            evt.set()
        pending_permissions.clear()
        permission_responses.clear()

        # Cleanup all sub-agents first
        if subagent_manager:
            try:
                await subagent_manager.cleanup_all()
            except Exception:
                pass

        # Cleanup all agents on disconnect
        for aid in list(agents.keys()):
            agent = agents.get(aid)
            if agent:
                task = agent.get("streaming_task")
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                cu_task = agent.get("computer_task")
                if cu_task and not cu_task.done():
                    cu_task.cancel()
                    try:
                        await cu_task
                    except (asyncio.CancelledError, Exception):
                        pass
                executor = agent.get("computer_executor")
                if executor:
                    executor.release_all()
                if agent.get("provider"):
                    try:
                        await agent["provider"].disconnect()
                    except Exception:
                        pass
        agents.clear()


# ---------------------------------------------------------------------------
# Static files (CSS/JS modules)
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _get_version() -> str:
    """Get package version."""
    try:
        from importlib.metadata import version as pkg_version
        return pkg_version("rain-assistant")
    except Exception:
        return "dev"


def _check_dependencies_inline():
    """Quick dependency check during first-run wizard."""
    import shutil

    print("  Verificando dependencias...", flush=True)

    v = sys.version_info
    status = "OK" if v >= (3, 11) else "!!"
    print(f"    {status} Python {v.major}.{v.minor}", flush=True)

    if shutil.which("ffmpeg"):
        print("    OK ffmpeg", flush=True)
    else:
        print("    !! ffmpeg no encontrado (voz puede fallar)", flush=True)
        if sys.platform == "darwin":
            print("       Instalar: brew install ffmpeg", flush=True)
        elif sys.platform == "linux":
            print("       Instalar: sudo apt install ffmpeg", flush=True)
        else:
            print("       Instalar: winget install Gyan.FFmpeg", flush=True)

    try:
        import sounddevice  # noqa: F401
        print("    OK portaudio", flush=True)
    except (ImportError, OSError):
        print("    -- portaudio no encontrado (grabacion de voz deshabilitada)", flush=True)


def _is_first_run() -> bool:
    """Check if this is the first run (no setup completed yet)."""
    if not CONFIG_FILE.exists():
        return True
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return not cfg.get("_setup_complete", False)
    except Exception:
        return True


def _run_setup_wizard(force: bool = False):
    """Interactive first-run setup in the terminal."""
    if not force and not _is_first_run():
        return

    print(flush=True)
    print(f"  Rain Assistant v{_get_version()}", flush=True)
    print(flush=True)
    print("  Primera vez? Configurando...", flush=True)
    print(flush=True)

    _check_dependencies_inline()
    print(flush=True)

    print("  Proveedor de IA:", flush=True)
    print("    1 = Claude (Anthropic)", flush=True)
    print("    2 = OpenAI", flush=True)
    print("    3 = Gemini (Google)", flush=True)
    print("    4 = Ollama (Local)", flush=True)
    print("    Enter = Saltar (configura en la web despues)", flush=True)
    print(flush=True)

    try:
        choice = input("  Elige [1/2/3/4/Enter]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    provider_map = {"1": "claude", "2": "openai", "3": "gemini", "4": "ollama"}
    provider = provider_map.get(choice)

    if provider:
        key_labels = {
            "claude": "API Key de Claude (sk-ant-...)",
            "openai": "API Key de OpenAI (sk-...)",
            "gemini": "API Key de Gemini",
            "ollama": "URL de Ollama (Enter = http://localhost:11434)",
        }
        try:
            api_key_input = input(f"  {key_labels[provider]}: ").strip()
        except (EOFError, KeyboardInterrupt):
            api_key_input = ""

        # For Ollama, empty input means use default localhost URL
        if not api_key_input and provider == "ollama":
            api_key_input = "http://localhost:11434"

        if api_key_input:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cfg = {}
            if CONFIG_FILE.exists():
                try:
                    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            cfg["default_provider"] = provider
            cfg["default_api_key"] = api_key_input
            cfg["_setup_complete"] = True
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            print("  Guardado!", flush=True)
            # Reload config so server picks it up
            config.update(cfg)
        else:
            print("  Puedes configurar la API key en la web.", flush=True)
    else:
        print("  OK, configura el proveedor desde la web.", flush=True)

    # Mark setup as complete
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg["_setup_complete"] = True
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    config.update(cfg)
    print(flush=True)


def _run_doctor():
    """Check all dependencies and report status."""
    import shutil

    print(flush=True)
    print(f"  Rain Assistant v{_get_version()} - Doctor", flush=True)
    print("  " + "=" * 35, flush=True)
    print(flush=True)

    checks: list[tuple[str, bool | None, str]] = []

    # Python version
    v = sys.version_info
    checks.append(("Python >= 3.11", v >= (3, 11), f"{v.major}.{v.minor}.{v.micro}"))

    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    checks.append(("ffmpeg", bool(ffmpeg_path), ffmpeg_path or "no encontrado"))

    # portaudio (sounddevice)
    try:
        import sounddevice  # noqa: F401
        checks.append(("portaudio (voz)", True, "sounddevice OK"))
    except (ImportError, OSError):
        checks.append(("portaudio (voz)", False, "pip install sounddevice"))

    # faster-whisper
    try:
        import faster_whisper  # noqa: F401
        checks.append(("faster-whisper", True, "OK"))
    except ImportError:
        checks.append(("faster-whisper", False, "pip install faster-whisper"))

    # edge-tts
    try:
        import edge_tts  # noqa: F401
        checks.append(("edge-tts", True, "OK"))
    except ImportError:
        checks.append(("edge-tts", False, "pip install edge-tts"))

    # Telegram (optional)
    try:
        import aiogram
        checks.append(("aiogram (Telegram)", True, f"v{aiogram.__version__}"))
    except ImportError:
        checks.append(("aiogram (Telegram)", None, "pip install rain-assistant[telegram]"))

    # Computer Use (optional)
    try:
        import pyautogui  # noqa: F401
        import mss  # noqa: F401
        checks.append(("Computer Use", True, "pyautogui + mss OK"))
    except ImportError:
        checks.append(("Computer Use", None, "pip install rain-assistant[computer-use]"))

    # Config
    checks.append(("Config dir", CONFIG_DIR.exists(), str(CONFIG_DIR)))

    # Static files
    static_ok = (STATIC_DIR / "index.html").exists()
    checks.append(("Frontend (static/)", static_ok, str(STATIC_DIR)))

    for name, ok, detail in checks:
        if ok is True:
            symbol = "      OK"
        elif ok is False:
            symbol = "   FALTA"
        else:
            symbol = "OPCIONAL"
        print(f"  [{symbol}] {name}: {detail}", flush=True)

    print(flush=True)
    errors = [c for c in checks if c[1] is False]
    if errors:
        print(f"  {len(errors)} problema(s) encontrado(s).", flush=True)
    else:
        print("  Todo OK!", flush=True)
    print(flush=True)


def _find_available_port(host, preferred, max_attempts=10):
    """Find an available port, starting from preferred.
    Uses connect to check if something is already listening."""
    import socket
    for offset in range(max_attempts):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            # If connect succeeds, something is listening = port busy
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port  # Connection refused = port is free
    return None


def _start_server(cmd_args):
    """Start the FastAPI server."""
    import socket
    import webbrowser

    HOST = cmd_args.host
    preferred_port = cmd_args.port

    # Auto-find available port
    PORT = _find_available_port(HOST, preferred_port)
    if PORT is None:
        print(flush=True)
        print(f"  ERROR: No hay puertos disponibles ({preferred_port}-{preferred_port + 9})", flush=True)
        print(f"  Intenta con: rain --port {preferred_port + 100}", flush=True)
        print(flush=True)
        sys.exit(1)

    if PORT != preferred_port:
        print(flush=True)
        print(f"  Puerto {preferred_port} ocupado, usando {PORT}", flush=True)

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        local_ip = "127.0.0.1"

    print(flush=True)
    print("  Rain Assistant Server", flush=True)
    print(f"  Local:   http://localhost:{PORT}", flush=True)
    print(f"  Network: http://{local_ip}:{PORT}", flush=True)
    display_pin = config.pop("_display_pin", None)
    if display_pin:
        print(f"  PIN:     {display_pin}  (new — shown only once)", flush=True)
    else:
        print(f"  PIN:     [configured]", flush=True)
    if cmd_args.telegram:
        print(f"  Telegram: enabled", flush=True)
    print(flush=True)

    uv_config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(uv_config)

    async def _run():
        serve_task = asyncio.create_task(server.serve())
        while not server.started:
            if serve_task.done():
                # Server failed to start
                exc = serve_task.exception()
                if exc:
                    print(f"  ERROR al iniciar servidor: {exc}", flush=True)
                sys.exit(1)
            await asyncio.sleep(0.1)

        # Auto-open browser
        if not cmd_args.no_browser:
            url = f"http://localhost:{PORT}"
            print(f"  Abriendo navegador...", flush=True)
            webbrowser.open(url)

        # Start Telegram bot if requested
        if cmd_args.telegram:
            from telegram_bot import run_telegram_bot_async
            asyncio.create_task(run_telegram_bot_async())

        # Start tunnel
        from tunnel import start_tunnel
        tunnel_url = start_tunnel(port=PORT)
        if tunnel_url:
            print(f"  Public:  {tunnel_url}", flush=True)
            print(flush=True)

        await serve_task

    asyncio.run(_run())


def main():
    """Entry point for `rain` / `rain-assistant` CLI."""
    import argparse
    import multiprocessing
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(
        prog="rain",
        description="Rain Assistant — AI coding assistant with voice, plugins & web UI",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--telegram", action="store_true", help="Start Telegram bot alongside web server")
    parser.add_argument("--telegram-only", action="store_true", help="Start only the Telegram bot (no web server)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Check dependencies and system health")
    subparsers.add_parser("setup", help="Re-run first-time setup wizard")

    cmd_args = parser.parse_args()

    if cmd_args.version:
        print(f"Rain Assistant v{_get_version()}")
        sys.exit(0)

    if cmd_args.command == "doctor":
        _run_doctor()
        sys.exit(0)

    if cmd_args.command == "setup":
        _run_setup_wizard(force=True)
        sys.exit(0)

    # First-run wizard
    if _is_first_run():
        _run_setup_wizard()

    # Telegram-only mode
    if cmd_args.telegram_only:
        from telegram_bot import run_telegram_bot
        print(flush=True)
        print("  Rain Assistant — Telegram Only Mode", flush=True)
        print(flush=True)
        run_telegram_bot()
        sys.exit(0)

    _start_server(cmd_args)


if __name__ == "__main__":
    main()
