"""
Logging configuration for Rain Assistant.

Provides rotating file logs with structured format and colored console output.
Uses only Python stdlib (logging, logging.handlers).

Usage:
    from logging_config import setup_logging, get_logger

    setup_logging()                # call once at startup
    logger = get_logger(__name__)  # per-module logger
    logger.info("Server started on port %d", port)

Environment variables:
    RAIN_LOG_LEVEL  - root log level (default: INFO)
                      accepts: DEBUG, INFO, WARNING, ERROR, CRITICAL
"""

import copy
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG_DIR = Path.home() / ".rain-assistant" / "logs"
_LOG_FILE = _LOG_DIR / "rain.log"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
_BACKUP_COUNT = 5

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class _ConsoleFormatter(logging.Formatter):
    """Colored, human-readable formatter for terminal output."""

    # ANSI color codes
    _COLORS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[1;31m", # bold red
    }
    _RESET = "\033[0m"

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        # Work on a copy so ANSI codes don't leak into other handlers
        record = copy.copy(record)
        color = self._COLORS.get(record.levelno, "")
        reset = self._RESET if color else ""
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


class _JsonFormatter(logging.Formatter):
    """Structured key=value formatter suitable for log parsing/ingestion.

    Produces lines like:
        ts=2026-02-22T14:30:00.123Z level=INFO logger=rain.server msg="Server started on port 8080"
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3] + "Z"

        # Build the log message from the record
        msg = record.getMessage()

        # Append exception traceback if present
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg = msg + " | " + record.exc_text.replace("\n", "\\n")
        if record.stack_info:
            msg = msg + " | " + record.stack_info.replace("\n", "\\n")

        # Sanitize to prevent log injection via newlines or control chars
        msg_escaped = msg.replace("\\", "\\\\").replace('"', '\\"')
        msg_escaped = msg_escaped.replace("\n", "\\n").replace("\r", "\\r")

        return (
            f'ts={ts} level={record.levelname} logger={record.name} '
            f'msg="{msg_escaped}"'
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_logging() -> None:
    """Initialize logging for the Rain Assistant process.

    Safe to call multiple times; handlers are only added once.
    """
    root = logging.getLogger()

    # Avoid adding duplicate handlers on repeated calls
    if getattr(root, "_rain_logging_configured", False):
        return

    # Resolve desired level from environment
    level_name = os.environ.get("RAIN_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    # --- Console handler (stderr, colored) --------------------------------
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(_ConsoleFormatter())
    root.addHandler(console_handler)

    # --- Rotating file handler (structured) --------------------------------
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(_LOG_FILE),
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # capture everything to file
        file_handler.setFormatter(_JsonFormatter())
        root.addHandler(file_handler)
    except OSError:
        # If we cannot write to the log directory (permissions, read-only FS),
        # fall back to console-only logging without crashing the application.
        root.warning(
            "Could not create log file at %s — file logging disabled",
            _LOG_FILE,
        )

    # Quiet down noisy third-party loggers
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    # Mark as configured so repeated calls are harmless
    root._rain_logging_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name.

    Convention: use ``get_logger(__name__)`` in each module, or
    ``get_logger("rain.<subsystem>")`` for explicit namespacing.
    """
    return logging.getLogger(name)
