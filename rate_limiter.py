"""
Token-based sliding window rate limiter for Rain Assistant.

In-memory implementation — no external dependencies (Redis, etc.).
Thread-safe for asyncio (single-threaded event loop).
"""

import hashlib
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum


class EndpointCategory(str, Enum):
    AUTH = "auth"                       # 10/min — strict to prevent brute-force
    AUDIO_UPLOAD = "audio_upload"       # 30/min
    TTS_SYNTHESIS = "tts_synthesis"     # 50/min
    FILE_BROWSING = "file_browsing"     # 200/min
    GENERIC_API = "generic_api"         # 100/min
    WEBSOCKET_MSG = "websocket_msg"     # 60/min


# Requests allowed per 60-second sliding window
RATE_LIMITS: dict[EndpointCategory, int] = {
    EndpointCategory.AUTH: 10,
    EndpointCategory.AUDIO_UPLOAD: 30,
    EndpointCategory.TTS_SYNTHESIS: 50,
    EndpointCategory.FILE_BROWSING: 200,
    EndpointCategory.GENERIC_API: 100,
    EndpointCategory.WEBSOCKET_MSG: 60,
}

WINDOW_SECONDS = 60


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: float  # seconds until next slot opens (0 if allowed)


MAX_WINDOWS = 10_000  # Hard cap to prevent unbounded memory growth


class RateLimiter:
    """Sliding-window rate limiter keyed by (token_hash, category)."""

    def __init__(self):
        self._windows: dict[tuple[str, str], deque[float]] = {}
        self._last_cleanup: float = 0.0
        self._cleanup_interval = 300  # every 5 minutes

    @staticmethod
    def _token_key(token: str) -> str:
        """Hash the full token to avoid prefix-collision issues."""
        if not token:
            return "anon"
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def check(self, token: str, category: EndpointCategory) -> RateLimitResult:
        """Check if a request is allowed. If allowed, records it.

        This is atomic: it both checks and records in one call,
        preventing TOCTOU issues.
        """
        now = time.time()
        limit = RATE_LIMITS[category]
        key = (self._token_key(token), category.value)

        # Lazy cleanup of stale windows
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now)

        window = self._windows.get(key)
        if window is None:
            # Enforce max windows to prevent memory exhaustion
            if len(self._windows) >= MAX_WINDOWS:
                self._cleanup(now)
            window = deque()
            self._windows[key] = window

        # Evict expired timestamps
        cutoff = now - WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= limit:
            # Denied: calculate retry_after from oldest entry in window
            retry_after = window[0] + WINDOW_SECONDS - now
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=max(0.1, retry_after),
            )

        # Allowed: record this request
        window.append(now)
        remaining = limit - len(window)
        return RateLimitResult(
            allowed=True, limit=limit, remaining=remaining, retry_after=0
        )

    def reset(self, token: str | None = None) -> None:
        """Clear rate-limit state. If token is given, clear only that token's
        windows; otherwise clear everything. Safe for use in tests."""
        if token is None:
            self._windows.clear()
            return
        token_hash = self._token_key(token)
        keys_to_delete = [k for k in self._windows if k[0] == token_hash]
        for k in keys_to_delete:
            del self._windows[k]

    def _cleanup(self, now: float):
        """Remove windows that have been idle for over 2x the window period."""
        self._last_cleanup = now
        cutoff = now - (WINDOW_SECONDS * 2)
        stale_keys = [
            k for k, dq in self._windows.items()
            if not dq or dq[-1] < cutoff
        ]
        for k in stale_keys:
            del self._windows[k]


# Singleton instance
rate_limiter = RateLimiter()


def categorize_endpoint(path: str) -> EndpointCategory:
    """Map a request path to its rate limit category."""
    if path == "/api/auth" or path.startswith("/api/auth/"):
        return EndpointCategory.AUTH
    if path in ("/api/logout", "/api/logout-all"):
        return EndpointCategory.AUTH
    if path.startswith("/api/upload-audio"):
        return EndpointCategory.AUDIO_UPLOAD
    if path.startswith("/api/synthesize"):
        return EndpointCategory.TTS_SYNTHESIS
    if path.startswith("/api/browse"):
        return EndpointCategory.FILE_BROWSING
    return EndpointCategory.GENERIC_API
