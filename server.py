import asyncio
import json
import os
import secrets
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from transcriber import Transcriber
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

# ---------------------------------------------------------------------------
# PIN & token management
# ---------------------------------------------------------------------------

active_tokens: set[str] = set()


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


# ---------------------------------------------------------------------------
# REST: Authentication
# ---------------------------------------------------------------------------


@app.post("/api/auth")
async def authenticate(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    pin = str(body.get("pin", "")).strip()
    expected = str(config.get("pin", "")).strip()

    print(f"  [AUTH] pin={repr(pin)} expected={repr(expected)} match={pin == expected}", flush=True)

    if not pin or pin != expected:
        return JSONResponse({"error": "Invalid PIN"}, status_code=401)
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
# WebSocket: Claude Code interaction
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not verify_token(token):
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()

    client: ClaudeSDKClient | None = None
    current_cwd: str | None = None
    api_key: str | None = None
    streaming_task: asyncio.Task | None = None

    async def send(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

    async def stream_claude_response(stream_client: ClaudeSDKClient):
        """Stream Claude's response to the frontend. Runs as a background task."""
        try:
            async for message in stream_client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            await send({
                                "type": "assistant_text",
                                "text": block.text,
                            })
                        elif isinstance(block, ToolUseBlock):
                            await send({
                                "type": "tool_use",
                                "tool": block.name,
                                "id": block.id,
                                "input": block.input,
                            })
                        elif isinstance(block, ToolResultBlock):
                            content_str = ""
                            if isinstance(block.content, str):
                                content_str = block.content
                            elif isinstance(block.content, list):
                                content_str = json.dumps(block.content, default=str)
                            elif block.content is not None:
                                content_str = str(block.content)
                            await send({
                                "type": "tool_result",
                                "tool_use_id": block.tool_use_id,
                                "content": content_str,
                                "is_error": block.is_error or False,
                            })

                elif isinstance(message, StreamEvent):
                    event = message.event
                    if isinstance(event, dict):
                        delta = event.get("delta", {})
                        if isinstance(delta, dict) and delta.get("type") == "text_delta":
                            await send({
                                "type": "stream_text",
                                "text": delta.get("text", ""),
                            })

                elif isinstance(message, ResultMessage):
                    await send({
                        "type": "result",
                        "text": message.result or "",
                        "session_id": message.session_id,
                        "cost": message.total_cost_usd,
                        "duration_ms": message.duration_ms,
                        "num_turns": message.num_turns,
                        "is_error": message.is_error,
                    })

                elif isinstance(message, SystemMessage):
                    await send({
                        "type": "status",
                        "text": f"System: {message.subtype}",
                    })

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await send({"type": "error", "text": str(e)})

    async def cancel_streaming():
        """Cancel the current streaming task if running."""
        nonlocal streaming_task
        if streaming_task and not streaming_task.done():
            streaming_task.cancel()
            try:
                await streaming_task
            except asyncio.CancelledError:
                pass
        streaming_task = None

    try:
        await send({"type": "status", "text": "Connected. Select a project directory."})

        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            # ---- Set API key ----
            if msg_type == "set_api_key":
                key = data.get("key", "").strip()
                if not key:
                    await send({"type": "error", "text": "API key is required."})
                    continue
                api_key = key
                await send({"type": "status", "text": "API key set."})

            # ---- Set working directory ----
            elif msg_type == "set_cwd":
                new_cwd = data.get("path", "")
                cwd_path = Path(new_cwd)

                if not cwd_path.is_dir():
                    await send({"type": "error", "text": f"Not a directory: {new_cwd}"})
                    continue

                # Cancel any running streaming task first
                await cancel_streaming()

                # Disconnect previous client
                if client:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

                current_cwd = str(cwd_path.resolve())

                env = {"ANTHROPIC_API_KEY": api_key} if api_key else {}
                options = ClaudeAgentOptions(
                    cwd=current_cwd,
                    permission_mode="bypassPermissions",
                    include_partial_messages=True,
                    env=env,
                    system_prompt=RAIN_SYSTEM_PROMPT,
                )
                client = ClaudeSDKClient(options=options)
                await client.connect()

                await send({
                    "type": "status",
                    "text": f"Ready. Project: {cwd_path.name}",
                    "cwd": current_cwd,
                })

            # ---- Send message to Claude ----
            elif msg_type == "send_message":
                text = data.get("text", "").strip()
                if not text:
                    continue

                if not client:
                    await send({"type": "error", "text": "No project directory selected."})
                    continue

                # Cancel any previous streaming task
                await cancel_streaming()

                await send({"type": "status", "text": "Rain is working..."})

                try:
                    await client.query(text)
                    streaming_task = asyncio.create_task(
                        stream_claude_response(client)
                    )
                except Exception as e:
                    await send({"type": "error", "text": str(e)})

            # ---- Interrupt ----
            elif msg_type == "interrupt":
                if client:
                    try:
                        await client.interrupt()
                    except Exception:
                        pass

                await cancel_streaming()

                await send({
                    "type": "result",
                    "text": "Interrupted by user.",
                    "session_id": None,
                    "cost": None,
                    "duration_ms": None,
                    "num_turns": None,
                    "is_error": False,
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if streaming_task and not streaming_task.done():
            streaming_task.cancel()
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    import socket

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        local_ip = "127.0.0.1"

    # Start Cloudflare Tunnel for remote access
    from tunnel import start_tunnel
    tunnel_url = start_tunnel(port=8000)

    print(flush=True)
    print("  Rain Assistant Server", flush=True)
    print(f"  Local:   http://localhost:8000", flush=True)
    print(f"  Network: http://{local_ip}:8000", flush=True)
    if tunnel_url:
        print(f"  Public:  {tunnel_url}", flush=True)
    print(f"  PIN:     {config['pin']}", flush=True)
    print(flush=True)

    uvicorn.run(app, host="0.0.0.0", port=8000)
