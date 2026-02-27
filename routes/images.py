"""Image upload endpoint — HTTP-based image sending with reference IDs."""

import logging
import secrets
import time

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse

import database
import shared_state
from shared_state import (
    MAX_IMAGE_UPLOAD_BYTES,
    IMAGE_READ_CHUNK_SIZE,
    MAX_PENDING_IMAGES_PER_TOKEN,
    _VALID_IMAGE_MEDIA_TYPES,
    _get_real_ip,
    verify_token,
    get_token,
)

_logger = logging.getLogger("rain.server")

images_router = APIRouter(tags=["images"])


@images_router.post("/api/upload-image")
async def upload_image(request: Request, image: UploadFile = File(...)):
    """Upload an image and get a temporary reference ID.

    The image is held in memory until a ``send_message`` WebSocket message
    references it via ``image_ids``, or until the TTL expires (5 min).
    """
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Validate content type
    media_type = image.content_type or ""
    if media_type not in _VALID_IMAGE_MEDIA_TYPES:
        return JSONResponse(
            {"error": f"Invalid image type: {media_type}. Accepted: PNG, JPEG, GIF, WebP"},
            status_code=400,
        )

    # Per-token pending limit to prevent memory abuse
    token_str = get_token(request) or ""
    token_prefix = token_str[:8]
    user_pending = sum(
        1 for img in shared_state.pending_images.values()
        if img["token_prefix"] == token_prefix
    )
    if user_pending >= MAX_PENDING_IMAGES_PER_TOKEN:
        return JSONResponse(
            {"error": f"Too many pending images ({MAX_PENDING_IMAGES_PER_TOKEN} max). Send a message first."},
            status_code=429,
        )

    # Read in chunks, reject oversized uploads early
    content = bytearray()
    while True:
        chunk = await image.read(IMAGE_READ_CHUNK_SIZE)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_IMAGE_UPLOAD_BYTES:
            database.log_security_event(
                "image_too_large", "warning",
                client_ip=_get_real_ip(request),
                endpoint="/api/upload-image",
                details=f"size>{MAX_IMAGE_UPLOAD_BYTES}",
            )
            return JSONResponse(
                {"error": f"Image too large (max {MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)} MB)"},
                status_code=413,
            )

    if not content:
        return JSONResponse({"error": "Empty file"}, status_code=400)

    # Store with unique ID
    image_id = secrets.token_urlsafe(16)
    shared_state.pending_images[image_id] = {
        "data": bytes(content),
        "media_type": media_type,
        "token_prefix": token_prefix,
        "uploaded_at": time.time(),
    }

    _logger.info(
        "Image uploaded: id=%s size=%d type=%s user=%s",
        image_id, len(content), media_type, token_prefix,
    )

    return {"image_id": image_id, "media_type": media_type, "size": len(content)}
