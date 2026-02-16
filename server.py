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

RAIN_SYSTEM_PROMPT = (
    "Your name is Rain. You are a friendly, tech-savvy coding assistant. "
    "When greeting the user for the first time in a conversation, introduce yourself as Rain. "
    "Use a warm and casual tone -- like a knowledgeable friend who's an expert developer. "
    "You can be a little playful, but always stay helpful and focused. "
    "Use the name 'Rain' naturally when referring to yourself. "
    "Respond in the same language the user writes in."
)

transcriber = Transcriber(model_size="base", language="es")
synthesizer = Synthesizer()

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


@asynccontextmanager
async def lifespan(application: FastAPI):
    database._ensure_db()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, transcriber.load_model)
    cleanup_task = asyncio.create_task(_cleanup_expired_tokens())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
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

    _EXEMPT_PATHS = {"/", "/sw.js", "/api/auth"}

    async def dispatch(self, request: StarletteRequest, call_next):
        path = request.url.path

        # Skip static files and exempt paths
        if path in self._EXEMPT_PATHS or path.startswith("/static"):
            return await call_next(request)

        # Extract token
        auth_header = request.headers.get("authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
        if not token:
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

    # Agent registry: agent_id → { client, cwd, streaming_task }
    agents: dict[str, dict] = {}
    api_key: str | None = None
    last_activity: float = time.time()

    # Permission request tracking
    pending_permissions: dict[str, asyncio.Event] = {}   # request_id → Event
    permission_responses: dict[str, dict] = {}            # request_id → {approved, pin}

    async def send(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

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

    async def stream_claude_response(stream_client: ClaudeSDKClient, agent_id: str):
        """Stream Claude's response to the frontend. Runs as a background task."""
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
            async for message in stream_client.receive_response():
                if isinstance(message, AssistantMessage):
                    # Forward model name to the frontend
                    model_name = getattr(message, "model", None)
                    if model_name:
                        await send({
                            "type": "model_info",
                            "agent_id": agent_id,
                            "model": model_name,
                        })
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            accumulated_text += block.text
                            await send({
                                "type": "assistant_text",
                                "agent_id": agent_id,
                                "text": block.text,
                            })
                        elif isinstance(block, ToolUseBlock):
                            flush_text()
                            payload = {
                                "tool": block.name,
                                "id": block.id,
                                "input": block.input,
                            }
                            if cwd:
                                database.save_message(cwd, "tool", "tool_use", payload, agent_id=agent_id)
                            await send({"type": "tool_use", "agent_id": agent_id, **payload})
                        elif isinstance(block, ToolResultBlock):
                            flush_text()
                            content_str = ""
                            if isinstance(block.content, str):
                                content_str = block.content
                            elif isinstance(block.content, list):
                                content_str = json.dumps(block.content, default=str)
                            elif block.content is not None:
                                content_str = str(block.content)
                            payload = {
                                "tool_use_id": block.tool_use_id,
                                "content": content_str,
                                "is_error": block.is_error or False,
                            }
                            if cwd:
                                database.save_message(cwd, "tool", "tool_result", payload, agent_id=agent_id)
                            await send({"type": "tool_result", "agent_id": agent_id, **payload})

                elif isinstance(message, StreamEvent):
                    pass  # Text already handled via AssistantMessage TextBlocks

                elif isinstance(message, ResultMessage):
                    flush_text()
                    payload = {
                        "text": message.result or "",
                        "session_id": message.session_id,
                        "cost": message.total_cost_usd,
                        "duration_ms": message.duration_ms,
                        "num_turns": message.num_turns,
                        "is_error": message.is_error,
                        "usage": message.usage,
                    }
                    if cwd:
                        database.save_message(cwd, "assistant", "result", payload, agent_id=agent_id)
                    await send({"type": "result", "agent_id": agent_id, **payload})

                    # Fetch & send rate limits after each response
                    if api_key:
                        rl = await fetch_rate_limits(api_key)
                        if rl:
                            await send({
                                "type": "rate_limits",
                                "agent_id": agent_id,
                                "limits": rl,
                            })

                elif isinstance(message, SystemMessage):
                    await send({
                        "type": "status",
                        "agent_id": agent_id,
                        "text": f"System: {message.subtype}",
                    })

        except asyncio.CancelledError:
            flush_text()
        except Exception as e:
            flush_text()
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
        """Fully disconnect and remove an agent."""
        await cancel_agent_streaming(agent_id)
        await cancel_computer_use_task(agent_id)
        agent = agents.pop(agent_id, None)
        if agent and agent.get("client"):
            try:
                await agent["client"].disconnect()
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

            data = json.loads(raw)
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
                key = data.get("key", "").strip()
                if not key:
                    await send({"type": "error", "agent_id": agent_id, "text": "API key is required."})
                    continue
                if len(key) > WS_MAX_KEY_LENGTH:
                    await send({"type": "error", "agent_id": agent_id, "text": "API key too long."})
                    continue
                api_key = key
                await send({"type": "status", "agent_id": agent_id, "text": "API key set."})

            # ---- Set transcription language ----
            elif msg_type == "set_transcription_lang":
                lang = data.get("lang", "").strip()
                if lang in ("en", "es"):
                    transcriber.language = lang
                    await send({"type": "status", "agent_id": agent_id, "text": f"Transcription language set to {lang}."})

            # ---- Set working directory for an agent ----
            elif msg_type == "set_cwd":
                new_cwd = data.get("path", "")

                if len(new_cwd) > WS_MAX_PATH_LENGTH:
                    await send({"type": "error", "agent_id": agent_id, "text": "Path too long."})
                    continue

                cwd_path = Path(new_cwd)

                if not cwd_path.is_dir():
                    await send({"type": "error", "agent_id": agent_id, "text": f"Not a directory: {new_cwd}"})
                    continue

                # ── 6d. Max concurrent agents ──
                if agent_id not in agents and len(agents) >= WS_MAX_CONCURRENT_AGENTS:
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

                env = {"ANTHROPIC_API_KEY": api_key} if api_key else {}
                options = ClaudeAgentOptions(
                    cwd=resolved_cwd,
                    permission_mode="default",
                    can_use_tool=can_use_tool_callback,
                    include_partial_messages=True,
                    env=env,
                    system_prompt=RAIN_SYSTEM_PROMPT,
                    resume=resume_session_id or None,
                )
                client = ClaudeSDKClient(options=options)
                await client.connect()

                agents[agent_id] = {
                    "client": client,
                    "cwd": resolved_cwd,
                    "streaming_task": None,
                    # Computer Use fields
                    "mode": "coding",
                    "computer_executor": None,
                    "computer_task": None,
                }

                await send({
                    "type": "status",
                    "agent_id": agent_id,
                    "text": f"Ready. Project: {cwd_path.name}",
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
                if not agent or not agent.get("client"):
                    await send({"type": "error", "agent_id": agent_id, "text": "No project directory selected for this agent."})
                    continue

                # Persist user message
                if agent.get("cwd"):
                    database.save_message(agent["cwd"], "user", "text", {"text": text}, agent_id=agent_id)

                # ── Computer Use mode: separate agent loop ──
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
                    await agent["client"].query(text)
                    task = asyncio.create_task(
                        stream_claude_response(agent["client"], agent_id)
                    )
                    agents[agent_id]["streaming_task"] = task
                except Exception as e:
                    await send({"type": "error", "agent_id": agent_id, "text": str(e)})

            # ---- Interrupt a specific agent ----
            elif msg_type == "interrupt":
                agent = agents.get(agent_id)
                if agent and agent.get("client"):
                    try:
                        await agent["client"].interrupt()
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

            # ---- Permission response from frontend ----
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
    except Exception:
        pass
    finally:
        # Cancel heartbeat
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        # Cleanup all agents on disconnect
        for aid in list(agents.keys()):
            agent = agents.get(aid)
            if agent:
                task = agent.get("streaming_task")
                if task and not task.done():
                    task.cancel()
                cu_task = agent.get("computer_task")
                if cu_task and not cu_task.done():
                    cu_task.cancel()
                executor = agent.get("computer_executor")
                if executor:
                    executor.release_all()
                if agent.get("client"):
                    try:
                        await agent["client"].disconnect()
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

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    import socket

    PORT = 8000

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
        print(f"  PIN:     [hashed — see initial creation log]", flush=True)
    print(flush=True)

    # cloudflared quick-tunnel binds the --url port on Windows, so we must
    # start uvicorn first (to own the port) and launch the tunnel afterwards
    # via the on_startup callback.
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(uv_config)

    async def _run():
        # Start uvicorn in the background so it binds the port first
        serve_task = asyncio.create_task(server.serve())
        # Wait until uvicorn is actually listening
        while not server.started:
            await asyncio.sleep(0.1)

        # Now start the tunnel — uvicorn already owns the port
        from tunnel import start_tunnel
        tunnel_url = start_tunnel(port=PORT)
        if tunnel_url:
            print(f"  Public:  {tunnel_url}", flush=True)
            print(flush=True)

        await serve_task

    asyncio.run(_run())
