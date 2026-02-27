"""
computer_use_safety.py — Enhanced Safety for Computer Use

Phase 4: Action rate limiting, directory guards, audit logging,
sandboxed bash execution, and sensitive screen region detection.
"""

import json
import logging
import os
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("rain.computer_use.safety")

# ── Defaults ──────────────────────────────────────────────────────────────
DEFAULT_MAX_ACTIONS_PER_SEC = 5
DEFAULT_AUDIT_MAX_ENTRIES = 5000


# ── Action Rate Limiter ──────────────────────────────────────────────────

class ActionRateLimiter:
    """Sliding-window rate limiter for computer use actions.

    Prevents runaway action loops by enforcing a max actions/second limit.
    """

    def __init__(self, max_per_second: int = DEFAULT_MAX_ACTIONS_PER_SEC):
        self.max_per_second = max_per_second
        self._timestamps: deque[float] = deque()

    def check(self) -> bool:
        """Check if an action is allowed. Returns True if allowed."""
        now = time.monotonic()
        # Remove timestamps older than 1 second
        while self._timestamps and now - self._timestamps[0] > 1.0:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.max_per_second:
            logger.warning(
                "Rate limit exceeded: %d actions in last second (max %d)",
                len(self._timestamps), self.max_per_second,
            )
            return False

        self._timestamps.append(now)
        return True

    def reset(self) -> None:
        self._timestamps.clear()


# ── Directory Guard ──────────────────────────────────────────────────────

# Directories that should never be written to or executed from
_DEFAULT_BLOCKED_DIRS = [
    # Windows system
    r"C:\Windows\System32",
    r"C:\Windows\SysWOW64",
    r"C:\Windows\Boot",
    r"C:\Program Files\Windows Defender",
    # Unix system
    "/etc",
    "/sbin",
    "/usr/sbin",
    "/boot",
    "/proc",
    "/sys",
    # User-sensitive
    ".ssh",
    ".gnupg",
    ".aws",
]


class DirectoryGuard:
    """Validates paths against whitelist/blacklist to prevent dangerous file operations."""

    def __init__(
        self,
        blocked_dirs: Optional[list[str]] = None,
        allowed_dirs: Optional[list[str]] = None,
    ):
        self._blocked = [
            os.path.normpath(d).lower()
            for d in (blocked_dirs or _DEFAULT_BLOCKED_DIRS)
        ]
        self._allowed = [
            os.path.normpath(d).lower()
            for d in (allowed_dirs or [])
        ]

    def is_allowed(self, path: str) -> bool:
        """Check if a path is safe to access."""
        norm = os.path.normpath(os.path.abspath(path)).lower()

        # If whitelist is set, path must be under an allowed dir
        if self._allowed:
            if not any(norm.startswith(a) for a in self._allowed):
                return False

        # Check blocked directories
        for blocked in self._blocked:
            if norm.startswith(blocked) or blocked in norm:
                return False

        return True

    def get_blocked_reason(self, path: str) -> Optional[str]:
        """Return reason why a path is blocked, or None if allowed."""
        norm = os.path.normpath(os.path.abspath(path)).lower()

        if self._allowed:
            if not any(norm.startswith(a) for a in self._allowed):
                return f"Path not in allowed directories: {path}"

        for blocked in self._blocked:
            if norm.startswith(blocked) or blocked in norm:
                return f"Access to protected directory blocked: {blocked}"

        return None


# ── Audit Logger ─────────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    """Single audit log entry for a computer use action."""
    timestamp: float
    action: str
    params: dict
    result: str = "ok"
    risk_level: str = "green"


class AuditLogger:
    """Timestamped action log per session for computer use.

    Stores up to max_entries in memory, supports JSON export.
    """

    def __init__(self, session_id: str, max_entries: int = DEFAULT_AUDIT_MAX_ENTRIES):
        self.session_id = session_id
        self.max_entries = max_entries
        self._entries: list[AuditEntry] = []
        self._start_time = time.time()

    def log(self, action: str, params: dict,
            result: str = "ok", risk_level: str = "green") -> None:
        """Record an action in the audit log."""
        if len(self._entries) >= self.max_entries:
            # Evict oldest 10%
            cutoff = self.max_entries // 10
            self._entries = self._entries[cutoff:]

        self._entries.append(AuditEntry(
            timestamp=time.time(),
            action=action,
            params=params,
            result=result,
            risk_level=risk_level,
        ))

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def export_json(self, path: Optional[str] = None) -> str:
        """Export audit log as JSON string. Optionally save to file."""
        data = {
            "session_id": self.session_id,
            "start_time": self._start_time,
            "entry_count": len(self._entries),
            "entries": [
                {
                    "timestamp": e.timestamp,
                    "action": e.action,
                    "params": e.params,
                    "result": e.result,
                    "risk_level": e.risk_level,
                }
                for e in self._entries
            ],
        }
        json_str = json.dumps(data, indent=2, default=str)

        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.info("Audit log exported to %s", path)

        return json_str

    def get_summary(self) -> dict:
        """Return a summary of the audit log."""
        risk_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        for e in self._entries:
            risk_counts[e.risk_level] = risk_counts.get(e.risk_level, 0) + 1
            action_counts[e.action] = action_counts.get(e.action, 0) + 1

        return {
            "session_id": self.session_id,
            "total_actions": len(self._entries),
            "duration_seconds": round(time.time() - self._start_time, 1),
            "risk_counts": risk_counts,
            "top_actions": dict(sorted(
                action_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]),
        }


# ── Sandboxed Bash Execution ────────────────────────────────────────────

# Patterns for extracting file paths from commands
_PATH_PATTERNS = [
    re.compile(r'(?:^|\s)([A-Z]:\\[^\s"\'|&;]+)', re.IGNORECASE),  # Windows paths
    re.compile(r'(?:^|\s)(/[^\s"\'|&;]+)'),                        # Unix paths
    re.compile(r'"([^"]+[/\\][^"]+)"'),                              # Quoted paths
    re.compile(r"'([^']+[/\\][^']+)'"),                              # Single-quoted paths
]


def extract_paths_from_command(command: str) -> list[str]:
    """Extract file/directory paths from a shell command."""
    paths: list[str] = []
    for pattern in _PATH_PATTERNS:
        for match in pattern.finditer(command):
            p = match.group(1) if pattern.groups else match.group(0)
            p = p.strip()
            if len(p) > 2 and ("/" in p or "\\" in p):
                paths.append(p)
    return paths


async def run_sandboxed_bash(
    command: str,
    cwd: str,
    timeout: float = 30.0,
    directory_guard: Optional[DirectoryGuard] = None,
) -> tuple[str, int]:
    """Run a bash command with safety checks.

    Returns (output, return_code). Validates paths against directory guard
    and enforces timeout.
    """
    import asyncio

    # Check paths in command against directory guard
    if directory_guard:
        for path in extract_paths_from_command(command):
            reason = directory_guard.get_blocked_reason(path)
            if reason:
                return f"BLOCKED: {reason}", -1

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=timeout,
        )
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        return output[:50_000], proc.returncode or 0

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return f"Command timed out after {timeout}s", -2
    except Exception as e:
        return f"Error executing command: {e}", -1


# ── Sensitive Screen Region Detection ────────────────────────────────────

@dataclass
class ScreenRegion:
    """A named screen region with bounds."""
    name: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int


def _get_sensitive_regions(screen_width: int, screen_height: int) -> list[ScreenRegion]:
    """Define sensitive screen regions for the current resolution."""
    return [
        # Windows taskbar (bottom 48px)
        ScreenRegion("taskbar", 0, screen_height - 48, screen_width, screen_height),
        # System tray (bottom-right 300x48)
        ScreenRegion("system_tray", screen_width - 300, screen_height - 48,
                      screen_width, screen_height),
        # Start button area (bottom-left 60x48)
        ScreenRegion("start_menu", 0, screen_height - 48, 60, screen_height),
    ]


def detect_sensitive_screen_region(
    x: int, y: int,
    screen_width: int, screen_height: int,
) -> Optional[str]:
    """Check if coordinates fall in a sensitive screen region.

    Returns the region name if sensitive, None otherwise.
    """
    for region in _get_sensitive_regions(screen_width, screen_height):
        if (region.x_min <= x <= region.x_max and
                region.y_min <= y <= region.y_max):
            return region.name
    return None


# ── Computer Action Classifier ───────────────────────────────────────────

# Keyboard shortcuts that are dangerous
_DANGEROUS_KEYS = {
    "alt+f4",           # Close window
    "ctrl+alt+delete",  # System menu
    "ctrl+alt+del",     # System menu
    "win+l",            # Lock screen
    "win+r",            # Run dialog
}

# Text patterns that suggest dangerous commands being typed
_DANGEROUS_TYPE_PATTERNS = [
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[sq]\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
]


def classify_computer_action(action: str, params: dict) -> str:
    """Classify a computer use action into a risk level.

    Returns: "green", "yellow", or "red".
    """
    # Screenshots are always safe
    if action == "screenshot":
        return "green"

    # Wait is safe
    if action == "wait":
        return "green"

    # Check dangerous keyboard shortcuts
    if action == "key":
        keys = str(params.get("text", "")).lower().replace(" ", "")
        if keys in _DANGEROUS_KEYS:
            return "red"

    # Check if typed text contains dangerous commands
    if action == "type":
        text = str(params.get("text", ""))
        for pattern in _DANGEROUS_TYPE_PATTERNS:
            if pattern.search(text):
                return "red"

    # All other actions are yellow (require confirmation)
    return "yellow"
