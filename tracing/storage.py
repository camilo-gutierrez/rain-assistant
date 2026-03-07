"""Persistent storage for tracing spans.

Uses SQLite for durable storage with configurable retention.
"""

import json
import sqlite3
import time
import threading
from pathlib import Path
from typing import Optional

from .tracer import Span

CONFIG_DIR = Path.home() / ".rain-assistant"


class TracingStorage:
    """SQLite storage for tracing spans with retention policy."""

    def __init__(self, db_path: Path = None, retention_days: int = 30):
        self.db_path = db_path or (CONFIG_DIR / "traces.db")
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self._ensure_db()

    def _ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    duration_ms REAL,
                    status TEXT DEFAULT 'ok',
                    agent_id TEXT DEFAULT 'default',
                    user_id TEXT DEFAULT 'default',
                    permission_level TEXT DEFAULT '',
                    provider TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    error_message TEXT DEFAULT '',
                    data_json TEXT DEFAULT '{}'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_time ON spans(start_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_kind ON spans(kind)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_user ON spans(user_id)")

    def save_span(self, span: Span):
        d = span.to_dict()
        data_json = json.dumps({
            "tool_input": d["tool_input"],
            "tool_output": d["tool_output"],
            "metadata": d["metadata"],
        }, default=str)

        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO spans
                    (span_id, trace_id, kind, name, start_time, end_time,
                     duration_ms, status, agent_id, user_id, permission_level,
                     provider, model, input_tokens, output_tokens, cost_usd,
                     error_message, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d["span_id"], d["trace_id"], d["kind"], d["name"],
                    d["start_time"], d["end_time"], d["duration_ms"],
                    d["status"], d["agent_id"], d["user_id"],
                    d["permission_level"], d["provider"], d["model"],
                    d["input_tokens"], d["output_tokens"], d["cost_usd"],
                    d["error_message"], data_json,
                ))

    def get_spans_by_trace(self, trace_id: str) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
                (trace_id,)
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_recent_traces(self, limit: int = 50, user_id: str = None) -> list[dict]:
        """Get recent unique traces with summary."""
        query = """
            SELECT trace_id,
                   MIN(start_time) as first_span,
                   MAX(end_time) as last_span,
                   COUNT(*) as span_count,
                   SUM(cost_usd) as total_cost,
                   SUM(input_tokens) as total_input_tokens,
                   SUM(output_tokens) as total_output_tokens,
                   GROUP_CONCAT(DISTINCT kind) as kinds
            FROM spans
        """
        params = []
        if user_id:
            query += " WHERE user_id = ?"
            params.append(user_id)
        query += " GROUP BY trace_id ORDER BY first_span DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def cleanup_old_spans(self):
        cutoff = time.time() - (self.retention_days * 86400)
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                result = conn.execute(
                    "DELETE FROM spans WHERE start_time < ?", (cutoff,)
                )
                return result.rowcount

    def get_cost_summary(self, days: int = 30, user_id: str = None) -> dict:
        cutoff = time.time() - (days * 86400)
        query = "SELECT SUM(cost_usd) as total, COUNT(*) as count FROM spans WHERE start_time > ?"
        params = [cutoff]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(query, params).fetchone()
            return {"total_cost_usd": row[0] or 0.0, "span_count": row[1]}

    def export_spans(self, trace_id: str = None, format: str = "json") -> str:
        """Export spans as JSON or CSV."""
        if trace_id:
            spans = self.get_spans_by_trace(trace_id)
        else:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM spans ORDER BY start_time DESC LIMIT 1000").fetchall()
                spans = [self._row_to_dict(r) for r in rows]

        if format == "csv":
            if not spans:
                return ""
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=spans[0].keys())
            writer.writeheader()
            writer.writerows(spans)
            return output.getvalue()

        return json.dumps(spans, indent=2, default=str)

    @staticmethod
    def _row_to_dict(row) -> dict:
        d = dict(row)
        if "data_json" in d:
            try:
                extra = json.loads(d.pop("data_json"))
                d.update(extra)
            except (json.JSONDecodeError, TypeError):
                d.pop("data_json", None)
        return d
