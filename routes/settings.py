"""Audio/TTS routes and other settings-related endpoints."""

import asyncio
import logging
import os
import tempfile
from datetime import date

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

import database
from shared_state import (
    DAILY_TTS_CHAR_LIMIT,
    DAILY_AUDIO_SECONDS_LIMIT,
    MAX_AUDIO_UPLOAD_BYTES,
    AUDIO_READ_CHUNK_SIZE,
    _get_real_ip,
    verify_token,
    get_token,
)

_logger = logging.getLogger("rain.server")

settings_router = APIRouter(tags=["settings"])


# ---------------------------------------------------------------------------
# Input validation models
# ---------------------------------------------------------------------------


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = Field(default="es-MX-DaliaNeural", max_length=100)
    rate: str = Field(default="+0%", max_length=20)


# ---------------------------------------------------------------------------
# Lazy-loaded singletons (avoid circular imports with server.py)
# These are set by server.py at startup via init_settings_deps().
# ---------------------------------------------------------------------------

_transcriber = None
_synthesizer = None


def init_settings_deps(transcriber, synthesizer):
    """Called by server.py to inject the transcriber and synthesizer instances."""
    global _transcriber, _synthesizer
    _transcriber = transcriber
    _synthesizer = synthesizer


# ---------------------------------------------------------------------------
# REST: Audio upload & transcription
# ---------------------------------------------------------------------------


@settings_router.post("/api/upload-audio")
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
        # Read in chunks so we can reject oversized uploads early
        content = bytearray()
        while True:
            chunk = await audio.read(AUDIO_READ_CHUNK_SIZE)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_AUDIO_UPLOAD_BYTES:
                tmp.close()
                os.unlink(tmp.name)
                database.log_security_event(
                    "invalid_input", "warning",
                    client_ip=_get_real_ip(request),
                    endpoint="/api/upload-audio",
                    details=f"size>{MAX_AUDIO_UPLOAD_BYTES}, limit={MAX_AUDIO_UPLOAD_BYTES}",
                )
                return JSONResponse(
                    {"error": f"File too large (max {MAX_AUDIO_UPLOAD_BYTES // (1024*1024)}MB)"},
                    status_code=413,
                )
        content = bytes(content)

        # Quota check: audio seconds per day
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
                client_ip=_get_real_ip(request),
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
        text = await loop.run_in_executor(None, _transcriber.transcribe, tmp.name)

        # Record usage after success
        database.increment_audio_seconds(token_prefix, date_key, estimated_seconds)

        return {"text": text}
    except Exception:
        _logger.exception("Transcription failed")
        return JSONResponse({"text": "", "error": "Transcription failed"}, status_code=500)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# REST: Text-to-speech synthesis
# ---------------------------------------------------------------------------


@settings_router.post("/api/synthesize")
async def synthesize_text(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
        synth_req = SynthesizeRequest(**body)
    except Exception:
        database.log_security_event(
            "invalid_input", "info",
            client_ip=_get_real_ip(request),
            endpoint="/api/synthesize",
        )
        return JSONResponse({"error": "Invalid JSON or text too long (max 5000 chars)"}, status_code=400)

    text = synth_req.text.strip()
    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)

    voice = synth_req.voice
    rate = synth_req.rate

    # Quota check: TTS chars per day
    token_str = get_token(request) or ""
    token_prefix = token_str[:8]
    date_key = date.today().isoformat()
    quota = database.get_or_create_quota(token_prefix, date_key)
    if quota["tts_chars"] + len(text) > DAILY_TTS_CHAR_LIMIT:
        database.log_security_event(
            "quota_exceeded", "warning",
            client_ip=_get_real_ip(request),
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
        audio_path = await _synthesizer.synthesize(text, voice=voice, rate=rate)
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
    except Exception:
        if audio_path:
            try:
                os.unlink(audio_path)
            except OSError:
                pass
        _logger.exception("Text-to-speech synthesis failed")
        return JSONResponse({"error": "Speech synthesis failed"}, status_code=500)
