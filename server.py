import asyncio
import json
import os
import secrets
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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
)
from claude_agent_sdk.types import StreamEvent

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

active_tokens: set[str] = set()

# Rate limiting: track failed PIN attempts per IP
# { ip: { "attempts": int, "locked_until": float } }
MAX_PIN_ATTEMPTS = 3
LOCKOUT_SECONDS = 5 * 60  # 5 minutes
_auth_attempts: dict[str, dict] = {}


def load_or_create_config() -> dict:
    """Load config from ~/.rain-assistant/config.json or create with new PIN."""
    # Migrate from old config directory
    if OLD_CONFIG_DIR.exists() and not CONFIG_DIR.exists():
        import shutil
        shutil.copytree(str(OLD_CONFIG_DIR), str(CONFIG_DIR))
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # Ensure PIN is always a string
            if "pin" in cfg:
                cfg["pin"] = str(cfg["pin"])
            return cfg
        except (json.JSONDecodeError, OSError):
            pass
    pin = f"{secrets.randbelow(900000) + 100000}"
    config = {"pin": pin}
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


config = load_or_create_config()


def verify_token(token: str | None) -> bool:
    return token is not None and token in active_tokens


@asynccontextmanager
async def lifespan(application: FastAPI):
    database._ensure_db()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, transcriber.load_model)
    yield


app = FastAPI(title="Rain Assistant", lifespan=lifespan)


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
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    pin = str(body.get("pin", "")).strip()
    expected = str(config.get("pin", "")).strip()

    print(f"  [AUTH] pin={repr(pin)} expected={repr(expected)} match={pin == expected} ip={client_ip}", flush=True)

    if not pin or pin != expected:
        # Track failed attempt
        if client_ip not in _auth_attempts:
            _auth_attempts[client_ip] = {"attempts": 0, "locked_until": 0}
        _auth_attempts[client_ip]["attempts"] += 1
        attempts = _auth_attempts[client_ip]["attempts"]
        remaining_attempts = MAX_PIN_ATTEMPTS - attempts

        if attempts >= MAX_PIN_ATTEMPTS:
            _auth_attempts[client_ip]["locked_until"] = time.time() + LOCKOUT_SECONDS
            print(f"  [AUTH] IP {client_ip} LOCKED OUT after {attempts} failed attempts", flush=True)
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
    active_tokens.add(token)
    return {"token": token}


def get_token(request: Request) -> str | None:
    """Extract token from Authorization header."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


# ---------------------------------------------------------------------------
# REST: Filesystem browser
# ---------------------------------------------------------------------------

MAX_ENTRIES = 200


@app.get("/api/browse")
async def browse_filesystem(request: Request, path: str = "~"):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

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
        tmp.write(content)
        tmp.close()

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, transcriber.transcribe, tmp.name)

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
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)

    voice = body.get("voice", "es-MX-DaliaNeural")
    rate = body.get("rate", "+0%")

    audio_path = None
    try:
        audio_path = await synthesizer.synthesize(text, voice=voice, rate=rate)
        if not audio_path:
            return JSONResponse(
                {"error": "Nothing to synthesize (mostly code)"},
                status_code=204,
            )

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
    messages = database.get_messages(cwd, agent_id=agent_id)
    return {"messages": messages}


@app.delete("/api/messages")
async def delete_messages(request: Request, cwd: str = "", agent_id: str = ""):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not cwd:
        return JSONResponse({"error": "cwd parameter is required"}, status_code=400)
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

    async def send(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

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

    async def destroy_agent(agent_id: str):
        """Fully disconnect and remove an agent."""
        await cancel_agent_streaming(agent_id)
        agent = agents.pop(agent_id, None)
        if agent and agent.get("client"):
            try:
                await agent["client"].disconnect()
            except Exception:
                pass

    try:
        await send({"type": "status", "agent_id": None, "text": "Connected. Select a project directory."})

        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            agent_id = data.get("agent_id", "default")

            # ---- Set API key (global, not per-agent) ----
            if msg_type == "set_api_key":
                key = data.get("key", "").strip()
                if not key:
                    await send({"type": "error", "agent_id": agent_id, "text": "API key is required."})
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
                cwd_path = Path(new_cwd)

                if not cwd_path.is_dir():
                    await send({"type": "error", "agent_id": agent_id, "text": f"Not a directory: {new_cwd}"})
                    continue

                # Destroy previous agent with this id if exists
                if agent_id in agents:
                    await destroy_agent(agent_id)

                resolved_cwd = str(cwd_path.resolve())
                resume_session_id = data.get("session_id")

                env = {"ANTHROPIC_API_KEY": api_key} if api_key else {}
                options = ClaudeAgentOptions(
                    cwd=resolved_cwd,
                    permission_mode="bypassPermissions",
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

                agent = agents.get(agent_id)
                if not agent or not agent.get("client"):
                    await send({"type": "error", "agent_id": agent_id, "text": "No project directory selected for this agent."})
                    continue

                # Persist user message
                if agent.get("cwd"):
                    database.save_message(agent["cwd"], "user", "text", {"text": text}, agent_id=agent_id)

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

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Cleanup all agents on disconnect
        for aid in list(agents.keys()):
            agent = agents.get(aid)
            if agent:
                task = agent.get("streaming_task")
                if task and not task.done():
                    task.cancel()
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
    print(f"  PIN:     {config['pin']}", flush=True)
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
