"""Input sanitization and security utilities for Rain Assistant."""

import os
import re
import sys
from pathlib import Path

_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def sanitize_user_id(user_id: str) -> str:
    """Validate and return a safe user_id for filesystem paths.

    Raises ValueError if user_id contains unsafe characters.
    """
    if not user_id:
        return "default"
    if not _SAFE_ID_PATTERN.match(user_id):
        raise ValueError("Invalid user_id: contains unsafe characters")
    if len(user_id) > 128:
        raise ValueError("user_id too long (max 128)")
    return user_id


def secure_chmod(path: Path, mode: int) -> None:
    """Set file permissions (no-op on Windows)."""
    if sys.platform != "win32":
        try:
            os.chmod(path, mode)
        except OSError:
            pass
