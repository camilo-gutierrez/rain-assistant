"""Authentication, session management, device management, and OAuth routes."""

import hashlib
import json
import secrets
import time
from pathlib import Path

import bcrypt
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import database
from shared_state import (
    active_tokens,
    _active_ws_by_device,
    _token_device_map,
    _auth_attempts,
    _oauth_login_process,
    config,
    CONFIG_FILE,
    TOKEN_TTL_SECONDS,
    MAX_PIN_ATTEMPTS,
    LOCKOUT_SECONDS,
    MAX_DEVICES,
    _get_real_ip,
    _secure_chmod,
    _find_claude_cli,
    verify_token,
    get_token,
)
import shared_state

auth_router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Input validation models
# ---------------------------------------------------------------------------

class AuthRequest(BaseModel):
    pin: str = Field(..., min_length=1, max_length=20)
    device_id: str = Field(default="", max_length=64)
    device_name: str = Field(default="", max_length=100)
    replace_device_id: str = Field(default="", max_length=64)


# ---------------------------------------------------------------------------
# REST: Authentication
# ---------------------------------------------------------------------------


@auth_router.post("/api/auth")
async def authenticate(request: Request):
    client_ip = _get_real_ip(request)

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
            # Lockout expired -- reset
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

    # Successful auth -- clear any attempt tracking for this IP
    _auth_attempts.pop(client_ip, None)

    device_id = auth_req.device_id.strip()
    device_name = auth_req.device_name.strip()
    user_agent = request.headers.get("user-agent", "")[:200]

    # Clean expired sessions before checking device limit
    database.cleanup_expired_sessions(TOKEN_TTL_SECONDS)

    # If this device already has a session, revoke old token and reuse slot
    if device_id:
        existing = database.get_session_by_device_id(device_id)
        if existing:
            # Revoke old token for this device
            old_hash = existing["token_hash"]
            old_tokens = [t for t, _ in active_tokens.items()
                          if hashlib.sha256(t.encode()).hexdigest() == old_hash]
            for t in old_tokens:
                active_tokens.pop(t, None)
            database.revoke_session(old_hash)
            _token_device_map.pop(old_hash, None)
            print(f"  [AUTH] Device {device_id[:8]}... re-authenticated, old token revoked", flush=True)
        else:
            # New device -- check limit
            device_count = database.count_active_devices(TOKEN_TTL_SECONDS)
            if device_count >= shared_state.MAX_DEVICES:
                # If replace_device_id provided, revoke that device to free a slot
                replace_id = auth_req.replace_device_id.strip()
                if replace_id:
                    target_session = database.get_session_by_device_id(replace_id)
                    if target_session:
                        # Close WebSocket first
                        ws = _active_ws_by_device.pop(replace_id, None)
                        if ws:
                            try:
                                await ws.close(code=4003, reason="Replaced by new device")
                            except Exception:
                                pass
                        revoked_hash = database.revoke_session_by_device_id(replace_id)
                        if revoked_hash:
                            to_remove = [t for t, _ in active_tokens.items()
                                         if hashlib.sha256(t.encode()).hexdigest() == revoked_hash]
                            for t in to_remove:
                                active_tokens.pop(t, None)
                            _token_device_map.pop(revoked_hash, None)
                        database.log_security_event(
                            "device_replaced", "warning",
                            client_ip=client_ip, endpoint="/api/auth",
                            details=f"replaced={replace_id[:8]}... by={device_id[:8]}...",
                        )
                        print(f"  [AUTH] Device {replace_id[:8]}... replaced by {device_id[:8]}...", flush=True)
                    else:
                        return JSONResponse({
                            "error": "device_limit_reached",
                            "max_devices": shared_state.MAX_DEVICES,
                        }, status_code=409)
                else:
                    database.log_security_event(
                        "device_limit_reached", "warning",
                        client_ip=client_ip, endpoint="/api/auth",
                        details=f"device_id={device_id[:8]}... count={device_count}/{shared_state.MAX_DEVICES}",
                    )
                    return JSONResponse({
                        "error": "device_limit_reached",
                        "max_devices": shared_state.MAX_DEVICES,
                    }, status_code=409)

    token = secrets.token_urlsafe(32)
    active_tokens[token] = time.time() + TOKEN_TTL_SECONDS

    # Track session in database (with encrypted token for persistence across restarts)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    encrypted_token = database.encrypt_field(token)
    database.create_session(
        token_hash, client_ip, user_agent, device_id, device_name,
        user_id="default", encrypted_token=encrypted_token,
    )
    if device_id:
        _token_device_map[token_hash] = device_id

    return {"token": token}


# ---------------------------------------------------------------------------
# REST: List devices with PIN (pre-auth, for device replacement flow)
# ---------------------------------------------------------------------------


@auth_router.post("/api/auth/devices")
async def list_devices_with_pin(request: Request):
    """List active devices using PIN authentication (no token required).

    Used when a new device hits the device limit and needs to choose
    which existing device to replace.
    """
    client_ip = _get_real_ip(request)

    # Check lockout (same as /api/auth)
    record = _auth_attempts.get(client_ip)
    if record:
        remaining = record["locked_until"] - time.time()
        if remaining > 0:
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": int(remaining),
            }, status_code=429)
        else:
            del _auth_attempts[client_ip]

    try:
        body = await request.json()
        pin = str(body.get("pin", "")).strip()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    if not pin or len(pin) > 20:
        return JSONResponse({"error": "Invalid PIN"}, status_code=400)

    pin_hash = config.get("pin_hash", "")
    try:
        pin_valid = bool(pin) and bcrypt.checkpw(
            pin.encode("utf-8"), pin_hash.encode("utf-8")
        )
    except Exception:
        pin_valid = False

    if not pin_valid:
        # Track failed attempt (same counter as /api/auth)
        if client_ip not in _auth_attempts:
            _auth_attempts[client_ip] = {"attempts": 0, "locked_until": 0}
        _auth_attempts[client_ip]["attempts"] += 1
        attempts = _auth_attempts[client_ip]["attempts"]
        remaining_attempts = MAX_PIN_ATTEMPTS - attempts

        if attempts >= MAX_PIN_ATTEMPTS:
            _auth_attempts[client_ip]["locked_until"] = time.time() + LOCKOUT_SECONDS
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": LOCKOUT_SECONDS,
            }, status_code=429)

        return JSONResponse({
            "error": "Invalid PIN",
            "remaining_attempts": remaining_attempts,
        }, status_code=401)

    # PIN valid -- return device list (no token created)
    database.cleanup_expired_sessions(TOKEN_TTL_SECONDS)
    devices = database.get_active_devices()
    result = []
    for d in devices:
        result.append({
            "device_id": d["device_id"],
            "device_name": d["device_name"],
            "client_ip": d["client_ip"],
            "created_at": d["created_at"],
            "last_activity": d["last_activity"],
        })
    return {"devices": result, "max_devices": shared_state.MAX_DEVICES}


@auth_router.post("/api/auth/revoke-device")
async def revoke_device_with_pin(request: Request):
    """Revoke a single device session using PIN authentication (no token required).

    Used from the device replacement flow to free a slot without logging in.
    """
    client_ip = _get_real_ip(request)

    # Check lockout
    record = _auth_attempts.get(client_ip)
    if record:
        remaining = record["locked_until"] - time.time()
        if remaining > 0:
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": int(remaining),
            }, status_code=429)
        else:
            del _auth_attempts[client_ip]

    try:
        body = await request.json()
        pin = str(body.get("pin", "")).strip()
        device_id = str(body.get("device_id", "")).strip()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    if not pin or len(pin) > 20:
        return JSONResponse({"error": "Invalid PIN"}, status_code=400)
    if not device_id:
        return JSONResponse({"error": "device_id required"}, status_code=400)

    pin_hash = config.get("pin_hash", "")
    try:
        pin_valid = bool(pin) and bcrypt.checkpw(
            pin.encode("utf-8"), pin_hash.encode("utf-8")
        )
    except Exception:
        pin_valid = False

    if not pin_valid:
        if client_ip not in _auth_attempts:
            _auth_attempts[client_ip] = {"attempts": 0, "locked_until": 0}
        _auth_attempts[client_ip]["attempts"] += 1
        attempts = _auth_attempts[client_ip]["attempts"]
        remaining_attempts = MAX_PIN_ATTEMPTS - attempts

        if attempts >= MAX_PIN_ATTEMPTS:
            _auth_attempts[client_ip]["locked_until"] = time.time() + LOCKOUT_SECONDS
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": LOCKOUT_SECONDS,
            }, status_code=429)

        return JSONResponse({
            "error": "Invalid PIN",
            "remaining_attempts": remaining_attempts,
        }, status_code=401)

    # PIN valid -- revoke the target device
    session = database.get_session_by_device_id(device_id)
    if not session:
        return JSONResponse({"error": "Device not found"}, status_code=404)

    # Close WebSocket first
    ws = _active_ws_by_device.pop(device_id, None)
    if ws:
        try:
            await ws.close(code=4003, reason="Device revoked via PIN")
        except Exception:
            pass

    revoked_hash = database.revoke_session_by_device_id(device_id)
    if revoked_hash:
        to_remove = [t for t, _ in active_tokens.items()
                     if hashlib.sha256(t.encode()).hexdigest() == revoked_hash]
        for t in to_remove:
            active_tokens.pop(t, None)
        _token_device_map.pop(revoked_hash, None)

    database.log_security_event(
        "device_revoked_via_pin", "warning",
        client_ip=client_ip, endpoint="/api/auth/revoke-device",
        details=f"revoked device_id={device_id[:8]}...",
    )
    print(f"  [AUTH] Device {device_id[:8]}... revoked via PIN from {client_ip}", flush=True)
    return {"revoked": True, "device_id": device_id}


@auth_router.post("/api/auth/revoke-all")
async def revoke_all_devices_with_pin(request: Request):
    """Revoke ALL active sessions using PIN authentication (no token required).

    Used when a new device hits the device limit and wants to clear all
    existing sessions before logging in.
    """
    client_ip = _get_real_ip(request)

    # Check lockout
    record = _auth_attempts.get(client_ip)
    if record:
        remaining = record["locked_until"] - time.time()
        if remaining > 0:
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": int(remaining),
            }, status_code=429)
        else:
            del _auth_attempts[client_ip]

    try:
        body = await request.json()
        pin = str(body.get("pin", "")).strip()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    if not pin or len(pin) > 20:
        return JSONResponse({"error": "Invalid PIN"}, status_code=400)

    pin_hash = config.get("pin_hash", "")
    try:
        pin_valid = bool(pin) and bcrypt.checkpw(
            pin.encode("utf-8"), pin_hash.encode("utf-8")
        )
    except Exception:
        pin_valid = False

    if not pin_valid:
        if client_ip not in _auth_attempts:
            _auth_attempts[client_ip] = {"attempts": 0, "locked_until": 0}
        _auth_attempts[client_ip]["attempts"] += 1
        attempts = _auth_attempts[client_ip]["attempts"]
        remaining_attempts = MAX_PIN_ATTEMPTS - attempts

        if attempts >= MAX_PIN_ATTEMPTS:
            _auth_attempts[client_ip]["locked_until"] = time.time() + LOCKOUT_SECONDS
            return JSONResponse({
                "error": "Too many failed attempts. Try again later.",
                "locked": True,
                "remaining_seconds": LOCKOUT_SECONDS,
            }, status_code=429)

        return JSONResponse({
            "error": "Invalid PIN",
            "remaining_attempts": remaining_attempts,
        }, status_code=401)

    # PIN valid -- close all WebSockets and revoke all sessions
    for dev_id, ws in list(_active_ws_by_device.items()):
        try:
            await ws.close(code=4003, reason="All devices revoked")
        except Exception:
            pass
    _active_ws_by_device.clear()

    active_tokens.clear()
    _token_device_map.clear()
    sessions_cleared = database.revoke_all_sessions()

    database.log_security_event(
        "all_devices_revoked", "critical",
        client_ip=client_ip, endpoint="/api/auth/revoke-all",
        details=f"sessions_cleared={sessions_cleared}",
    )
    print(f"  [AUTH] All {sessions_cleared} sessions revoked via PIN from {client_ip}", flush=True)
    return {"revoked_all": True, "count": sessions_cleared}


# ---------------------------------------------------------------------------
# REST: Logout
# ---------------------------------------------------------------------------


@auth_router.post("/api/logout")
async def logout(request: Request):
    """Revoke the current token."""
    token = get_token(request)
    if not token or not verify_token(token):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    client_ip = _get_real_ip(request)
    active_tokens.pop(token, None)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    database.revoke_session(token_hash)
    database.log_security_event(
        "token_revoked", "info", client_ip=client_ip,
        token_prefix=token[:8], endpoint="/api/logout",
    )
    return {"logged_out": True}


@auth_router.post("/api/logout-all")
async def logout_all(request: Request):
    """Revoke ALL tokens. Requires PIN confirmation."""
    token = get_token(request)
    if not token or not verify_token(token):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    client_ip = _get_real_ip(request)

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
# REST: Device management
# ---------------------------------------------------------------------------


@auth_router.get("/api/devices")
async def list_devices(request: Request):
    """List all active devices."""
    token = get_token(request)
    if not token or not verify_token(token):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Clean expired before listing
    database.cleanup_expired_sessions(TOKEN_TTL_SECONDS)

    current_hash = hashlib.sha256(token.encode()).hexdigest()
    devices = database.get_active_devices()
    result = []
    for d in devices:
        result.append({
            "device_id": d["device_id"],
            "device_name": d["device_name"],
            "client_ip": d["client_ip"],
            "created_at": d["created_at"],
            "last_activity": d["last_activity"],
            "is_current": d["token_hash"] == current_hash,
        })
    return {"devices": result, "max_devices": shared_state.MAX_DEVICES}


@auth_router.delete("/api/devices/{device_id}")
async def revoke_device(request: Request, device_id: str):
    """Revoke a specific device by its device_id."""
    token = get_token(request)
    if not token or not verify_token(token):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if not device_id or len(device_id) > 64 or not device_id.isalnum() and not all(c.isalnum() or c in "-_" for c in device_id):
        return JSONResponse({"error": "Invalid device ID"}, status_code=400)

    client_ip = _get_real_ip(request)

    # Prevent revoking self
    current_hash = hashlib.sha256(token.encode()).hexdigest()
    session = database.get_session_by_device_id(device_id)
    if not session:
        return JSONResponse({"error": "Device not found"}, status_code=404)
    if session["token_hash"] == current_hash:
        return JSONResponse({"error": "Cannot revoke current device"}, status_code=400)

    # Close WebSocket FIRST to prevent race condition
    ws = _active_ws_by_device.pop(device_id, None)
    if ws:
        try:
            await ws.close(code=4003, reason="Device revoked")
        except Exception:
            pass

    # Then remove from in-memory tokens
    revoked_hash = database.revoke_session_by_device_id(device_id)
    if revoked_hash:
        to_remove = [t for t, _ in active_tokens.items()
                     if hashlib.sha256(t.encode()).hexdigest() == revoked_hash]
        for t in to_remove:
            active_tokens.pop(t, None)
        _token_device_map.pop(revoked_hash, None)

    database.log_security_event(
        "device_revoked", "warning", client_ip=client_ip,
        endpoint="/api/devices", details=f"revoked device_id={device_id[:8]}...",
    )
    return {"revoked": True, "device_id": device_id}


@auth_router.patch("/api/devices/{device_id}")
async def rename_device_endpoint(request: Request, device_id: str):
    """Rename a device."""
    token = get_token(request)
    if not token or not verify_token(token):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if not device_id or len(device_id) > 64 or not all(c.isalnum() or c in "-_" for c in device_id):
        return JSONResponse({"error": "Invalid device ID"}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    new_name = str(body.get("name", "")).strip()
    if not new_name or len(new_name) > 100:
        return JSONResponse({"error": "Invalid device name"}, status_code=400)

    if database.rename_device(device_id, new_name):
        return {"renamed": True, "device_id": device_id, "name": new_name}
    return JSONResponse({"error": "Device not found"}, status_code=404)


# ---------------------------------------------------------------------------
# REST: Check Claude OAuth credentials
# ---------------------------------------------------------------------------


@auth_router.get("/api/check-oauth")
async def check_oauth(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Method 1: Check credentials file (Windows, some Linux)
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
            oauth = creds.get("claudeAiOauth", {})
            if oauth.get("accessToken"):
                expires_at = oauth.get("expiresAt", 0)
                is_expired = expires_at < (time.time() * 1000)
                return JSONResponse({
                    "available": True,
                    "subscriptionType": oauth.get("subscriptionType", "unknown"),
                    "rateLimitTier": oauth.get("rateLimitTier", ""),
                    "expired": is_expired,
                })
        except Exception:
            pass

    # Method 2: Check via 'claude auth status' (macOS Keychain, etc.)
    cli = _find_claude_cli()
    if cli:
        try:
            import subprocess
            import os
            env = {**os.environ}
            env.pop("CLAUDE_CODE_ENTRYPOINT", None)
            env.pop("CLAUDECODE", None)
            result = subprocess.run(
                [cli, "auth", "status"],
                env=env, capture_output=True, text=True, timeout=10,
            )
            status_out = (result.stdout + result.stderr).lower()
            if result.returncode == 0 and "logged in" in status_out:
                return JSONResponse({
                    "available": True,
                    "subscriptionType": "unknown",
                    "rateLimitTier": "",
                    "expired": False,
                })
        except Exception:
            pass

    # Method 3: Check if config says oauth mode (trust the setup)
    if config.get("auth_mode") == "oauth":
        return JSONResponse({
            "available": True,
            "subscriptionType": "configured",
            "rateLimitTier": "",
            "expired": False,
        })

    return JSONResponse({"available": False})


@auth_router.post("/api/trigger-oauth-login")
async def trigger_oauth_login(request: Request):
    """Trigger Claude OAuth login flow (opens browser on the server machine)."""
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Check if already logged in
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
            oauth = creds.get("claudeAiOauth", {})
            if oauth.get("accessToken"):
                expires_at = oauth.get("expiresAt", 0)
                if expires_at > (time.time() * 1000):
                    return JSONResponse({
                        "status": "already_logged_in",
                        "subscriptionType": oauth.get("subscriptionType", "unknown"),
                    })
        except Exception:
            pass

    cli = _find_claude_cli()
    if not cli:
        return JSONResponse(
            {"error": "Claude CLI not found. Install claude-agent-sdk."},
            status_code=500,
        )

    # Check if a login is already in progress
    current_process = shared_state._oauth_login_process
    if current_process and current_process.get("process"):
        proc = current_process["process"]
        if proc.poll() is None:  # still running
            return JSONResponse({"status": "login_in_progress"})

    import subprocess
    import os

    env = {**os.environ}
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env.pop("CLAUDECODE", None)

    try:
        proc = subprocess.Popen(
            [cli, "auth", "login"],
            env=env,
        )
        shared_state._oauth_login_process = {"process": proc, "started": time.time()}
        return JSONResponse({"status": "login_started"})
    except Exception:
        return JSONResponse({"error": "Failed to start OAuth login"}, status_code=500)


@auth_router.get("/api/oauth-login-status")
async def oauth_login_status(request: Request):
    """Check if the OAuth login process completed and credentials exist."""
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Check if credentials now exist
    creds_path = Path.home() / ".claude" / ".credentials.json"
    logged_in = False
    sub_type = "unknown"

    if creds_path.exists():
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
            oauth = creds.get("claudeAiOauth", {})
            if oauth.get("accessToken"):
                logged_in = True
                sub_type = oauth.get("subscriptionType", "unknown")
        except Exception:
            pass

    # Check process status
    proc_running = False
    current_process = shared_state._oauth_login_process
    if current_process and current_process.get("process"):
        proc = current_process["process"]
        if proc.poll() is None:
            proc_running = True
            # Timeout after 5 minutes
            if time.time() - current_process.get("started", 0) > 300:
                proc.kill()
                shared_state._oauth_login_process = None
                proc_running = False

    if logged_in:
        # Auto-save oauth mode to config
        try:
            cfg = {}
            if CONFIG_FILE.exists():
                cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg["default_provider"] = "claude"
            cfg["auth_mode"] = "oauth"
            cfg.pop("default_api_key", None)
            cfg["_setup_complete"] = True
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            _secure_chmod(CONFIG_FILE, 0o600)
            config.update(cfg)
        except Exception:
            pass

        shared_state._oauth_login_process = None
        return JSONResponse({
            "status": "logged_in",
            "subscriptionType": sub_type,
        })

    if proc_running:
        return JSONResponse({"status": "waiting"})

    return JSONResponse({"status": "not_started"})
