"""Tests for the tracing module."""

import json
import time
import threading
import pytest

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracing.tracer import Span, SpanKind, Tracer
from tracing.storage import TracingStorage


# ── Span tests ──────────────────────────────────────────────────────────


class TestSpan:
    def test_span_creation(self):
        span = Span(
            trace_id="t1",
            span_id="s1",
            kind=SpanKind.TOOL_CALL,
            name="bash",
            start_time=time.time(),
        )
        assert span.trace_id == "t1"
        assert span.span_id == "s1"
        assert span.kind == SpanKind.TOOL_CALL
        assert span.name == "bash"
        assert span.status == "ok"
        assert span.end_time == 0.0
        assert span.duration_ms == 0.0

    def test_span_finish_sets_duration(self):
        start = time.time()
        span = Span(
            trace_id="t1", span_id="s1",
            kind=SpanKind.LLM_REQUEST, name="claude",
            start_time=start,
        )
        time.sleep(0.01)
        span.finish()
        assert span.end_time > start
        assert span.duration_ms > 0
        assert span.status == "ok"

    def test_span_finish_with_error(self):
        span = Span(
            trace_id="t1", span_id="s1",
            kind=SpanKind.TOOL_CALL, name="bash",
            start_time=time.time(),
        )
        span.finish(status="error", error="command failed")
        assert span.status == "error"
        assert span.error_message == "command failed"

    def test_span_to_dict(self):
        span = Span(
            trace_id="t1", span_id="s1",
            kind=SpanKind.PERMISSION_CHECK, name="check_bash",
            start_time=1000.0,
            agent_id="agent-1",
            user_id="user-1",
            permission_level="GREEN",
            metadata={"extra": "data"},
        )
        span.finish()
        d = span.to_dict()
        assert d["trace_id"] == "t1"
        assert d["kind"] == "permission_check"
        assert d["permission_level"] == "GREEN"
        assert d["metadata"] == {"extra": "data"}
        assert d["duration_ms"] >= 0
        assert isinstance(d["tool_input"], dict)

    def test_span_to_dict_truncates_tool_output(self):
        span = Span(
            trace_id="t1", span_id="s1",
            kind=SpanKind.TOOL_CALL, name="bash",
            start_time=time.time(),
        )
        span.tool_output = "x" * 1000
        span.finish()
        d = span.to_dict()
        assert len(d["tool_output"]) == 500

    def test_span_to_dict_empty_tool_output(self):
        span = Span(
            trace_id="t1", span_id="s1",
            kind=SpanKind.TOOL_CALL, name="bash",
            start_time=time.time(),
        )
        span.finish()
        d = span.to_dict()
        assert d["tool_output"] == ""


# ── Tracer tests ────────────────────────────────────────────────────────


class TestTracer:
    def test_tracer_default_trace_id(self):
        tracer = Tracer()
        assert tracer.trace_id  # auto-generated UUID
        assert tracer.agent_id == "default"
        assert tracer.user_id == "default"

    def test_tracer_custom_ids(self):
        tracer = Tracer(trace_id="my-trace", agent_id="a1", user_id="u1")
        assert tracer.trace_id == "my-trace"
        assert tracer.agent_id == "a1"
        assert tracer.user_id == "u1"

    def test_start_and_end_span(self):
        tracer = Tracer(trace_id="t1")
        span = tracer.start_span(SpanKind.TOOL_CALL, "bash")
        assert span.trace_id == "t1"
        span.tool_input = {"command": "ls"}
        span.tool_output = "file1\nfile2"
        tracer.end_span(span)
        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0]["name"] == "bash"
        assert spans[0]["tool_input"] == {"command": "ls"}

    def test_end_span_auto_finishes(self):
        tracer = Tracer()
        span = tracer.start_span(SpanKind.LLM_REQUEST, "openai")
        # Don't call span.finish() manually
        tracer.end_span(span)
        spans = tracer.get_spans()
        assert spans[0]["end_time"] > 0
        assert spans[0]["duration_ms"] >= 0

    def test_get_summary(self):
        tracer = Tracer(trace_id="t1")

        # Add tool call
        s1 = tracer.start_span(SpanKind.TOOL_CALL, "bash")
        s1.finish()
        tracer.end_span(s1)

        # Add LLM request
        s2 = tracer.start_span(SpanKind.LLM_REQUEST, "claude")
        s2.input_tokens = 100
        s2.output_tokens = 50
        s2.cost_usd = 0.003
        s2.finish()
        tracer.end_span(s2)

        # Add error span
        s3 = tracer.start_span(SpanKind.TOOL_CALL, "write_file")
        s3.finish(status="error", error="permission denied")
        tracer.end_span(s3)

        summary = tracer.get_summary()
        assert summary["trace_id"] == "t1"
        assert summary["total_spans"] == 3
        assert summary["tool_calls"] == 2
        assert summary["llm_requests"] == 1
        assert summary["total_input_tokens"] == 100
        assert summary["total_output_tokens"] == 50
        assert summary["total_cost_usd"] == 0.003
        assert summary["errors"] == 1


# ── TracingStorage tests ────────────────────────────────────────────────


class TestTracingStorage:
    def _make_span(self, trace_id="t1", span_id="s1", kind=SpanKind.TOOL_CALL,
                   name="bash", start_time=None, cost=0.0, tokens_in=0,
                   tokens_out=0, user_id="default"):
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            kind=kind,
            name=name,
            start_time=start_time or time.time(),
            user_id=user_id,
        )
        span.cost_usd = cost
        span.input_tokens = tokens_in
        span.output_tokens = tokens_out
        span.finish()
        return span

    def test_save_and_retrieve_span(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        span = self._make_span()
        storage.save_span(span)
        result = storage.get_spans_by_trace("t1")
        assert len(result) == 1
        assert result[0]["span_id"] == "s1"
        assert result[0]["name"] == "bash"

    def test_get_spans_by_trace_ordering(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        now = time.time()
        storage.save_span(self._make_span(span_id="s2", start_time=now + 1))
        storage.save_span(self._make_span(span_id="s1", start_time=now))
        result = storage.get_spans_by_trace("t1")
        assert result[0]["span_id"] == "s1"
        assert result[1]["span_id"] == "s2"

    def test_get_recent_traces(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        storage.save_span(self._make_span(trace_id="t1", span_id="s1", cost=0.01))
        storage.save_span(self._make_span(trace_id="t1", span_id="s2", cost=0.02))
        storage.save_span(self._make_span(trace_id="t2", span_id="s3", cost=0.05))
        result = storage.get_recent_traces()
        assert len(result) == 2
        # Each trace should have aggregated info
        trace_ids = {r["trace_id"] for r in result}
        assert trace_ids == {"t1", "t2"}

    def test_get_recent_traces_with_user_filter(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        storage.save_span(self._make_span(trace_id="t1", span_id="s1", user_id="alice"))
        storage.save_span(self._make_span(trace_id="t2", span_id="s2", user_id="bob"))
        result = storage.get_recent_traces(user_id="alice")
        assert len(result) == 1
        assert result[0]["trace_id"] == "t1"

    def test_cleanup_old_spans(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db", retention_days=7)
        old_time = time.time() - (8 * 86400)  # 8 days ago
        storage.save_span(self._make_span(span_id="old", start_time=old_time))
        storage.save_span(self._make_span(span_id="new", start_time=time.time()))
        deleted = storage.cleanup_old_spans()
        assert deleted == 1
        remaining = storage.get_spans_by_trace("t1")
        assert len(remaining) == 1
        assert remaining[0]["span_id"] == "new"

    def test_get_cost_summary(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        storage.save_span(self._make_span(span_id="s1", cost=0.01))
        storage.save_span(self._make_span(span_id="s2", cost=0.02))
        summary = storage.get_cost_summary(days=1)
        assert summary["total_cost_usd"] == pytest.approx(0.03)
        assert summary["span_count"] == 2

    def test_get_cost_summary_user_filter(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        storage.save_span(self._make_span(span_id="s1", cost=0.01, user_id="alice"))
        storage.save_span(self._make_span(span_id="s2", cost=0.05, user_id="bob"))
        summary = storage.get_cost_summary(days=1, user_id="alice")
        assert summary["total_cost_usd"] == pytest.approx(0.01)
        assert summary["span_count"] == 1

    def test_export_json(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        storage.save_span(self._make_span(span_id="s1"))
        storage.save_span(self._make_span(span_id="s2"))
        output = storage.export_spans(trace_id="t1", format="json")
        data = json.loads(output)
        assert len(data) == 2

    def test_export_csv(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        storage.save_span(self._make_span(span_id="s1"))
        output = storage.export_spans(trace_id="t1", format="csv")
        lines = output.strip().split("\n")
        assert len(lines) == 2  # header + 1 row
        assert "span_id" in lines[0]

    def test_export_csv_empty(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        output = storage.export_spans(trace_id="nonexistent", format="csv")
        assert output == ""

    def test_data_json_round_trip(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        span = self._make_span()
        span.tool_input = {"command": "echo hello"}
        span.tool_output = "hello"
        span.metadata = {"cwd": "/tmp"}
        storage.save_span(span)
        result = storage.get_spans_by_trace("t1")
        assert result[0]["tool_input"] == {"command": "echo hello"}
        assert result[0]["tool_output"] == "hello"
        assert result[0]["metadata"] == {"cwd": "/tmp"}


# ── Thread safety test ──────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_span_additions(self):
        tracer = Tracer(trace_id="concurrent")
        errors = []

        def add_spans(start_idx):
            try:
                for i in range(50):
                    span = tracer.start_span(SpanKind.TOOL_CALL, f"tool-{start_idx}-{i}")
                    span.finish()
                    tracer.end_span(span)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_spans, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        spans = tracer.get_spans()
        assert len(spans) == 200  # 4 threads * 50 spans

    def test_concurrent_storage_writes(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        errors = []

        def write_spans(thread_id):
            try:
                for i in range(20):
                    span = Span(
                        trace_id=f"t-{thread_id}",
                        span_id=f"s-{thread_id}-{i}",
                        kind=SpanKind.TOOL_CALL,
                        name=f"tool-{i}",
                        start_time=time.time(),
                    )
                    span.finish()
                    storage.save_span(span)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_spans, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # Verify all spans were saved
        total = 0
        for t in range(4):
            spans = storage.get_spans_by_trace(f"t-{t}")
            total += len(spans)
        assert total == 80  # 4 threads * 20 spans


# ── Integration: Tracer + Storage ───────────────────────────────────────


class TestTracerWithStorage:
    def test_tracer_auto_saves_to_storage(self, tmp_path):
        storage = TracingStorage(db_path=tmp_path / "traces.db")
        tracer = Tracer(trace_id="integrated")
        tracer.set_storage(storage)

        span = tracer.start_span(SpanKind.LLM_REQUEST, "claude")
        span.provider = "anthropic"
        span.model = "claude-3-opus"
        span.input_tokens = 500
        span.output_tokens = 200
        span.cost_usd = 0.015
        span.finish()
        tracer.end_span(span)

        # Verify in-memory
        assert len(tracer.get_spans()) == 1

        # Verify persisted
        db_spans = storage.get_spans_by_trace("integrated")
        assert len(db_spans) == 1
        assert db_spans[0]["provider"] == "anthropic"
        assert db_spans[0]["model"] == "claude-3-opus"
        assert db_spans[0]["input_tokens"] == 500
