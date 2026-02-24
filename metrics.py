"""Lightweight in-memory metrics collector for production observability.

Provides Prometheus-compatible text exposition format via get_metrics_text().
Uses only the Python standard library — no external dependencies required.

Thread-safe: all mutations are guarded by a threading.Lock so the module
is safe to use from both sync and async code (FastAPI runs sync helpers in
a thread pool).

Usage:
    from metrics import record_request, record_ws_connect, get_metrics_text

    record_request("GET", "/health", 0.012)
    text = get_metrics_text()
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Histogram bucket boundaries (seconds) — matches Prometheus defaults
# ---------------------------------------------------------------------------

_DEFAULT_BUCKETS: Tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


# ---------------------------------------------------------------------------
# Internal storage types
# ---------------------------------------------------------------------------

class _Counter:
    """A monotonically increasing counter keyed by label tuples."""

    __slots__ = ("_values",)

    def __init__(self) -> None:
        self._values: Dict[Tuple[str, ...], float] = defaultdict(float)

    def inc(self, labels: Tuple[str, ...], amount: float = 1.0) -> None:
        self._values[labels] += amount

    def items(self):
        return self._values.items()


class _Gauge:
    """A value that can go up and down."""

    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value: float = 0.0

    def inc(self) -> None:
        self._value += 1

    def dec(self) -> None:
        self._value -= 1

    @property
    def value(self) -> float:
        return self._value


class _Histogram:
    """A histogram that tracks observations in configurable buckets.

    Each label-set gets its own set of buckets, a running sum, and a count.
    """

    __slots__ = ("_buckets", "_observations")

    def __init__(self, buckets: Tuple[float, ...] = _DEFAULT_BUCKETS) -> None:
        self._buckets = buckets
        # label_tuple -> { "buckets": {le: count}, "sum": float, "count": int }
        self._observations: Dict[Tuple[str, ...], dict] = {}

    def observe(self, labels: Tuple[str, ...], value: float) -> None:
        if labels not in self._observations:
            self._observations[labels] = {
                "buckets": {le: 0 for le in self._buckets},
                "sum": 0.0,
                "count": 0,
            }
        obs = self._observations[labels]
        obs["sum"] += value
        obs["count"] += 1
        for le in self._buckets:
            if value <= le:
                obs["buckets"][le] += 1

    def items(self):
        return self._observations.items()


# ---------------------------------------------------------------------------
# MetricsCollector — the single source of truth
# ---------------------------------------------------------------------------

class MetricsCollector:
    """In-memory, thread-safe metrics collector.

    All public methods acquire ``_lock`` before mutating state so the
    collector is safe to share across threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Counters
        self.requests_total = _Counter()
        self.llm_requests_total = _Counter()
        self.llm_errors_total = _Counter()
        self.tool_executions_total = _Counter()

        # Gauges
        self.active_websocket_connections = _Gauge()

        # Histograms
        self.request_duration_seconds = _Histogram()

    # -- public helpers ------------------------------------------------

    def record_request(self, method: str, path: str, duration: float) -> None:
        """Record an HTTP request.

        Parameters
        ----------
        method:
            HTTP verb (GET, POST, ...).
        path:
            Request path (e.g. ``/health``).  It is recommended to pass
            the *route template* rather than the concrete path to avoid
            high-cardinality label values.
        duration:
            Wall-clock time in **seconds**.
        """
        with self._lock:
            self.requests_total.inc((method, path))
            self.request_duration_seconds.observe((path,), duration)

    def record_ws_connect(self) -> None:
        """Increment the active WebSocket connections gauge."""
        with self._lock:
            self.active_websocket_connections.inc()

    def record_ws_disconnect(self) -> None:
        """Decrement the active WebSocket connections gauge."""
        with self._lock:
            self.active_websocket_connections.dec()

    def record_llm_request(self, provider: str) -> None:
        """Record an LLM request by provider name.

        Parameters
        ----------
        provider:
            One of ``"claude"``, ``"openai"``, ``"gemini"``, ``"ollama"``.
        """
        with self._lock:
            self.llm_requests_total.inc((provider,))

    def record_llm_error(self, provider: str, error_type: str) -> None:
        """Record an LLM error.

        Parameters
        ----------
        provider:
            Provider name.
        error_type:
            A short classifier such as ``"timeout"``, ``"rate_limit"``,
            ``"auth"``, or ``"unknown"``.
        """
        with self._lock:
            self.llm_errors_total.inc((provider, error_type))

    def record_tool_execution(self, tool_name: str, permission_level: str) -> None:
        """Record a tool execution.

        Parameters
        ----------
        tool_name:
            Name of the tool that was executed.
        permission_level:
            One of ``"green"``, ``"yellow"``, ``"red"``, ``"computer"``.
        """
        with self._lock:
            self.tool_executions_total.inc((tool_name, permission_level))

    # -- exposition -----------------------------------------------------

    def get_metrics_text(self) -> str:
        """Return all metrics in Prometheus text exposition format.

        The output is compatible with Prometheus ``/metrics`` scraping.
        """
        with self._lock:
            return self._render()

    def _render(self) -> str:  # noqa: C901 — intentionally procedural
        lines: list[str] = []

        # -- process uptime (built-in) ---------------------------------
        uptime = time.time() - self._start_time
        lines.append("# HELP process_uptime_seconds Time since the metrics collector was created")
        lines.append("# TYPE process_uptime_seconds gauge")
        lines.append(f"process_uptime_seconds {_fmt(uptime)}")
        lines.append("")

        # -- requests_total --------------------------------------------
        lines.append("# HELP requests_total Total HTTP requests")
        lines.append("# TYPE requests_total counter")
        for (method, path), value in sorted(self.requests_total.items()):
            lines.append(
                f'requests_total{{method="{_escape(method)}",path="{_escape(path)}"}} {_fmt(value)}'
            )
        lines.append("")

        # -- request_duration_seconds (histogram) ----------------------
        lines.append("# HELP request_duration_seconds HTTP request duration in seconds")
        lines.append("# TYPE request_duration_seconds histogram")
        for (path,), obs in sorted(self.request_duration_seconds.items()):
            escaped_path = _escape(path)
            for le in sorted(obs["buckets"]):
                lines.append(
                    f'request_duration_seconds_bucket{{path="{escaped_path}",le="{_fmt(le)}"}} {obs["buckets"][le]}'
                )
            lines.append(
                f'request_duration_seconds_bucket{{path="{escaped_path}",le="+Inf"}} {obs["count"]}'
            )
            lines.append(
                f'request_duration_seconds_sum{{path="{escaped_path}"}} {_fmt(obs["sum"])}'
            )
            lines.append(
                f'request_duration_seconds_count{{path="{escaped_path}"}} {obs["count"]}'
            )
        lines.append("")

        # -- active_websocket_connections (gauge) ----------------------
        lines.append("# HELP active_websocket_connections Current number of active WebSocket connections")
        lines.append("# TYPE active_websocket_connections gauge")
        lines.append(f"active_websocket_connections {_fmt(self.active_websocket_connections.value)}")
        lines.append("")

        # -- llm_requests_total ----------------------------------------
        lines.append("# HELP llm_requests_total Total LLM requests by provider")
        lines.append("# TYPE llm_requests_total counter")
        for (provider,), value in sorted(self.llm_requests_total.items()):
            lines.append(
                f'llm_requests_total{{provider="{_escape(provider)}"}} {_fmt(value)}'
            )
        lines.append("")

        # -- llm_errors_total ------------------------------------------
        lines.append("# HELP llm_errors_total Total LLM errors by provider and error type")
        lines.append("# TYPE llm_errors_total counter")
        for (provider, error_type), value in sorted(self.llm_errors_total.items()):
            lines.append(
                f'llm_errors_total{{provider="{_escape(provider)}",error_type="{_escape(error_type)}"}} {_fmt(value)}'
            )
        lines.append("")

        # -- tool_executions_total -------------------------------------
        lines.append("# HELP tool_executions_total Total tool executions by tool name and permission level")
        lines.append("# TYPE tool_executions_total counter")
        for (tool_name, permission_level), value in sorted(self.tool_executions_total.items()):
            lines.append(
                f'tool_executions_total{{tool_name="{_escape(tool_name)}",permission_level="{_escape(permission_level)}"}} {_fmt(value)}'
            )
        lines.append("")

        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(value: float) -> str:
    """Format a numeric value for Prometheus exposition.

    Integers are rendered without a decimal point; floats keep up to 6
    significant digits.  Special IEEE 754 values are mapped to the
    Prometheus text-format tokens.
    """
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if math.isnan(value):
        return "NaN"
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.6g}"


def _escape(text: str) -> str:
    """Escape a label value for Prometheus text format.

    Prometheus requires backslash, double-quote, and newline to be escaped
    inside label values.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# ---------------------------------------------------------------------------
# Module-level singleton & convenience functions
# ---------------------------------------------------------------------------

collector = MetricsCollector()
"""Module-level singleton — import and use directly or via the helper functions."""


def record_request(method: str, path: str, duration: float) -> None:
    """Record an HTTP request (method, path, duration in seconds)."""
    collector.record_request(method, path, duration)


def record_ws_connect() -> None:
    """Increment the active WebSocket connections gauge."""
    collector.record_ws_connect()


def record_ws_disconnect() -> None:
    """Decrement the active WebSocket connections gauge."""
    collector.record_ws_disconnect()


def record_llm_request(provider: str) -> None:
    """Record an LLM request for the given provider."""
    collector.record_llm_request(provider)


def record_llm_error(provider: str, error_type: str) -> None:
    """Record an LLM error for the given provider and error type."""
    collector.record_llm_error(provider, error_type)


def record_tool_execution(tool_name: str, permission_level: str) -> None:
    """Record a tool execution with its permission level."""
    collector.record_tool_execution(tool_name, permission_level)


def get_metrics_text() -> str:
    """Return all metrics as a Prometheus-compatible text exposition string."""
    return collector.get_metrics_text()
