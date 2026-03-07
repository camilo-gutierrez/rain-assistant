"""SQLite storage for audit events with hash chain integrity."""

import json
import sqlite3
import time
import threading
from pathlib import Path
from typing import Optional

from .logger import AuditEvent, AuditEventType

CONFIG_DIR = Path.home() / ".rain-assistant"


class AuditStorage:
    """Append-only SQLite storage for audit events."""

    def __init__(self, db_path: Path = None, retention_days: int = 90):
        self.db_path = db_path or (CONFIG_DIR / "audit.db")
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self._ensure_db()

    def _ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    user_id TEXT DEFAULT 'system',
                    agent_id TEXT DEFAULT 'default',
                    tool_name TEXT DEFAULT '',
                    action TEXT DEFAULT '',
                    details_json TEXT DEFAULT '{}',
                    result TEXT DEFAULT '',
                    ip_address TEXT DEFAULT '',
                    prev_hash TEXT DEFAULT '',
                    event_hash TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_events(tool_name)")

    def save_event(self, event: AuditEvent):
        d = event.to_dict()
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    INSERT INTO audit_events
                    (event_id, event_type, timestamp, user_id, agent_id,
                     tool_name, action, details_json, result, ip_address,
                     prev_hash, event_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d["event_id"], d["event_type"], d["timestamp"],
                    d["user_id"], d["agent_id"], d["tool_name"],
                    d["action"], json.dumps(d["details"], default=str),
                    d["result"], d["ip_address"],
                    d["prev_hash"], d["event_hash"],
                ))

    def get_events(self, limit: int = 100, event_type: str = None,
                   user_id: str = None, since: float = None) -> list[dict]:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_last_event(self) -> Optional[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def verify_chain(self, limit: int = 100) -> dict:
        """Verify hash chain integrity of recent events."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY timestamp ASC LIMIT ?",
                (limit,)
            ).fetchall()

        if not rows:
            return {"valid": True, "checked": 0, "errors": []}

        errors = []
        for i, row in enumerate(rows):
            d = self._row_to_dict(row)
            # Recompute hash
            event = AuditEvent(
                event_id=d["event_id"],
                event_type=d["event_type"],
                timestamp=d["timestamp"],
                user_id=d.get("user_id", "system"),
                agent_id=d.get("agent_id", "default"),
                tool_name=d.get("tool_name", ""),
                action=d.get("action", ""),
                result=d.get("result", ""),
                prev_hash=d.get("prev_hash", ""),
            )
            computed = event.compute_hash()
            if computed != d.get("event_hash", ""):
                errors.append({
                    "event_id": d["event_id"],
                    "index": i,
                    "expected": d.get("event_hash"),
                    "computed": computed,
                })

            # Check chain linkage
            if i > 0:
                prev_d = self._row_to_dict(rows[i - 1])
                if d.get("prev_hash") != prev_d.get("event_hash"):
                    errors.append({
                        "event_id": d["event_id"],
                        "index": i,
                        "chain_break": True,
                        "expected_prev": prev_d.get("event_hash"),
                        "actual_prev": d.get("prev_hash"),
                    })

        return {
            "valid": len(errors) == 0,
            "checked": len(rows),
            "errors": errors,
        }

    def cleanup_old_events(self) -> int:
        cutoff = time.time() - (self.retention_days * 86400)
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                result = conn.execute(
                    "DELETE FROM audit_events WHERE timestamp < ?", (cutoff,)
                )
                return result.rowcount

    def get_stats(self, days: int = 30, user_id: str = None) -> dict:
        cutoff = time.time() - (days * 86400)
        base_query = "SELECT event_type, COUNT(*) as count FROM audit_events WHERE timestamp > ?"
        params = [cutoff]
        if user_id:
            base_query += " AND user_id = ?"
            params.append(user_id)
        base_query += " GROUP BY event_type"

        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(base_query, params).fetchall()
            by_type = {row[0]: row[1] for row in rows}
            total = sum(by_type.values())
            return {
                "total_events": total,
                "by_type": by_type,
                "days": days,
            }

    def export_events(self, format: str = "json", limit: int = 1000) -> str:
        events = self.get_events(limit=limit)
        if format == "csv":
            if not events:
                return ""
            import csv, io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)
            return output.getvalue()
        return json.dumps(events, indent=2, default=str)

    @staticmethod
    def _row_to_dict(row) -> dict:
        d = dict(row)
        if "details_json" in d:
            try:
                d["details"] = json.loads(d.pop("details_json"))
            except (json.JSONDecodeError, TypeError):
                d["details"] = {}
                d.pop("details_json", None)
        return d
