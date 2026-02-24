"""Filesystem browser routes."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import database
from shared_state import (
    ALLOWED_ROOT,
    MAX_BROWSE_PATH_LENGTH,
    MAX_ENTRIES,
    _get_real_ip,
    verify_token,
    get_token,
)

files_router = APIRouter(tags=["files"])


# ---------------------------------------------------------------------------
# REST: Filesystem browser
# ---------------------------------------------------------------------------


@files_router.get("/api/browse")
async def browse_filesystem(request: Request, path: str = "~"):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if len(path) > MAX_BROWSE_PATH_LENGTH:
        database.log_security_event(
            "invalid_input", "info",
            client_ip=_get_real_ip(request),
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

    # Verify the fully resolved path (following ALL symlinks) is within ALLOWED_ROOT
    final_resolved = target.resolve(strict=True)
    try:
        final_resolved.relative_to(ALLOWED_ROOT)
    except ValueError:
        return JSONResponse(
            {"error": "Access denied: symlink target outside allowed area"},
            status_code=403,
        )

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
