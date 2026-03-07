"""Structured tracing for Rain Assistant runtime.

Records tool calls, provider requests, and permission decisions
with timestamps, durations, costs, and results.
Compatible with OpenTelemetry span concepts.
"""

import time
import uuid
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional


class SpanKind(str, Enum):
    TOOL_CALL = "tool_call"
    LLM_REQUEST = "llm_request"
    PERMISSION_CHECK = "permission_check"
    POLICY_CHECK = "policy_check"
    WEBSOCKET_MESSAGE = "websocket_message"
    DIRECTOR_TASK = "director_task"


@dataclass
class Span:
    trace_id: str           # groups spans in a conversation/session
    span_id: str            # unique ID for this span
    kind: SpanKind
    name: str               # e.g. tool name, provider name
    start_time: float       # time.time()
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"      # "ok", "error", "denied"
    agent_id: str = "default"
    user_id: str = "default"

    # Tool-specific
    tool_input: dict = field(default_factory=dict)
    tool_output: str = ""
    permission_level: str = ""

    # LLM-specific
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # Error info
    error_message: str = ""

    # Metadata
    metadata: dict = field(default_factory=dict)

    def finish(self, status: str = "ok", error: str = ""):
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        if error:
            self.error_message = error

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "kind": self.kind.value,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output[:500] if self.tool_output else "",
            "permission_level": self.permission_level,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class Tracer:
    """Thread-safe tracer that collects spans for a session.

    Usage:
        tracer = Tracer(trace_id="conv-123", agent_id="agent-1")
        span = tracer.start_span(SpanKind.TOOL_CALL, "bash")
        span.tool_input = {"command": "ls"}
        # ... execute tool ...
        span.tool_output = result
        span.finish()
        tracer.end_span(span)
    """

    def __init__(self, trace_id: str = None, agent_id: str = "default", user_id: str = "default"):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.agent_id = agent_id
        self.user_id = user_id
        self._spans: list[Span] = []
        self._lock = threading.Lock()
        self._storage: Optional['TracingStorage'] = None

    def set_storage(self, storage: 'TracingStorage'):
        self._storage = storage

    def start_span(self, kind: SpanKind, name: str, **kwargs) -> Span:
        span = Span(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            kind=kind,
            name=name,
            start_time=time.time(),
            agent_id=self.agent_id,
            user_id=self.user_id,
            **kwargs,
        )
        return span

    def end_span(self, span: Span):
        if span.end_time == 0:
            span.finish()
        with self._lock:
            self._spans.append(span)
        if self._storage:
            self._storage.save_span(span)

    def get_spans(self) -> list[dict]:
        with self._lock:
            return [s.to_dict() for s in self._spans]

    def get_summary(self) -> dict:
        with self._lock:
            tool_spans = [s for s in self._spans if s.kind == SpanKind.TOOL_CALL]
            llm_spans = [s for s in self._spans if s.kind == SpanKind.LLM_REQUEST]
            return {
                "trace_id": self.trace_id,
                "total_spans": len(self._spans),
                "tool_calls": len(tool_spans),
                "llm_requests": len(llm_spans),
                "total_duration_ms": sum(s.duration_ms for s in self._spans),
                "total_cost_usd": sum(s.cost_usd for s in self._spans),
                "total_input_tokens": sum(s.input_tokens for s in self._spans),
                "total_output_tokens": sum(s.output_tokens for s in self._spans),
                "errors": len([s for s in self._spans if s.status == "error"]),
            }
