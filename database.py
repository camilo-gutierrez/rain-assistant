import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path.home() / ".rain-assistant" / "conversations.db"


def _ensure_db():
    """Create tables and indexes if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        # Create table with original schema first (safe for existing DBs)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                cwd          TEXT NOT NULL,
                role         TEXT NOT NULL,
                type         TEXT NOT NULL,
                content_json TEXT NOT NULL,
                timestamp    REAL NOT NULL
            )
        """)
        # Migrate: add agent_id column if missing (upgrade from old schema)
        _migrate_agent_id(conn)
        # Now safe to create the compound index
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_cwd_agent
            ON messages(cwd, agent_id, timestamp)
        """)
        conn.commit()


def _migrate_agent_id(conn):
    """Add agent_id column to existing databases that don't have it."""
    cursor = conn.execute("PRAGMA table_info(messages)")
    columns = [row[1] for row in cursor.fetchall()]
    if "agent_id" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN agent_id TEXT NOT NULL DEFAULT 'default'")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_cwd_agent
            ON messages(cwd, agent_id, timestamp)
        """)


@contextmanager
def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_message(cwd: str, role: str, msg_type: str, content: dict, agent_id: str = "default") -> int:
    """Insert a message and return its id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages (cwd, agent_id, role, type, content_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cwd, agent_id, role, msg_type, json.dumps(content, default=str), time.time()),
        )
        conn.commit()
        return cur.lastrowid


def get_messages(cwd: str, agent_id: str = "default") -> list[dict]:
    """Return all messages for a cwd + agent_id, ordered by timestamp."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, type, content_json, timestamp "
            "FROM messages WHERE cwd = ? AND agent_id = ? ORDER BY timestamp ASC",
            (cwd, agent_id),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "role": r["role"],
            "type": r["type"],
            "content": json.loads(r["content_json"]),
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def clear_messages(cwd: str, agent_id: str | None = None) -> int:
    """Delete messages for a cwd. If agent_id given, only that agent. Returns count deleted."""
    with _connect() as conn:
        if agent_id:
            cur = conn.execute("DELETE FROM messages WHERE cwd = ? AND agent_id = ?", (cwd, agent_id))
        else:
            cur = conn.execute("DELETE FROM messages WHERE cwd = ?", (cwd,))
        conn.commit()
        return cur.rowcount


def get_metrics_data() -> dict:
    """Aggregate usage metrics from all result-type messages."""
    now = datetime.now()
    start_of_today = datetime(now.year, now.month, now.day).timestamp()
    start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    start_of_month = datetime(now.year, now.month, 1).timestamp()
    thirty_days_ago = (now - timedelta(days=30)).timestamp()

    _base_where = (
        "type = 'result' "
        "AND json_extract(content_json, '$.cost') IS NOT NULL "
        "AND json_extract(content_json, '$.cost') > 0"
    )

    with _connect() as conn:
        # 1. All-time totals
        row = conn.execute(f"""
            SELECT
                COUNT(*) as total_sessions,
                COALESCE(SUM(json_extract(content_json, '$.cost')), 0) as total_cost,
                COALESCE(AVG(json_extract(content_json, '$.cost')), 0) as avg_cost,
                COALESCE(AVG(json_extract(content_json, '$.duration_ms')), 0) as avg_duration_ms,
                COALESCE(SUM(json_extract(content_json, '$.num_turns')), 0) as total_turns,
                COALESCE(SUM(json_extract(content_json, '$.usage.input_tokens')), 0) as total_input_tokens,
                COALESCE(SUM(json_extract(content_json, '$.usage.output_tokens')), 0) as total_output_tokens
            FROM messages WHERE {_base_where}
        """).fetchone()
        all_time = {
            "cost": row["total_cost"],
            "sessions": row["total_sessions"],
            "avg_cost": row["avg_cost"],
            "avg_duration_ms": row["avg_duration_ms"],
            "total_turns": row["total_turns"],
            "total_input_tokens": row["total_input_tokens"],
            "total_output_tokens": row["total_output_tokens"],
        }

        # 2. Period totals (today, this week, this month)
        def _period_totals(since: float) -> dict:
            r = conn.execute(f"""
                SELECT COUNT(*) as s, COALESCE(SUM(json_extract(content_json, '$.cost')), 0) as c
                FROM messages WHERE {_base_where} AND timestamp >= ?
            """, (since,)).fetchone()
            return {"cost": r["c"], "sessions": r["s"]}

        today = _period_totals(start_of_today)
        this_week = _period_totals(start_of_week)
        this_month = _period_totals(start_of_month)

        # 3. Hourly distribution (24 buckets)
        hour_rows = conn.execute(f"""
            SELECT
                CAST(strftime('%H', timestamp, 'unixepoch', 'localtime') AS INTEGER) as hour,
                COUNT(*) as sessions,
                COALESCE(SUM(json_extract(content_json, '$.cost')), 0) as cost
            FROM messages WHERE {_base_where}
            GROUP BY hour ORDER BY hour
        """).fetchall()
        hour_map = {r["hour"]: {"sessions": r["sessions"], "cost": r["cost"]} for r in hour_rows}
        by_hour = [
            {"hour": h, "sessions": hour_map.get(h, {}).get("sessions", 0),
             "cost": hour_map.get(h, {}).get("cost", 0.0)}
            for h in range(24)
        ]

        # 4. Day-of-week distribution (7 buckets)
        dow_names = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
        dow_rows = conn.execute(f"""
            SELECT
                CAST(strftime('%w', timestamp, 'unixepoch', 'localtime') AS INTEGER) as dow,
                COUNT(*) as sessions,
                COALESCE(SUM(json_extract(content_json, '$.cost')), 0) as cost
            FROM messages WHERE {_base_where}
            GROUP BY dow ORDER BY dow
        """).fetchall()
        dow_map = {r["dow"]: {"sessions": r["sessions"], "cost": r["cost"]} for r in dow_rows}
        by_dow = [
            {"dow": d, "name": dow_names[d],
             "sessions": dow_map.get(d, {}).get("sessions", 0),
             "cost": dow_map.get(d, {}).get("cost", 0.0)}
            for d in range(7)
        ]

        # 5. Daily breakdown (last 30 days)
        day_rows = conn.execute(f"""
            SELECT
                strftime('%Y-%m-%d', timestamp, 'unixepoch', 'localtime') as day,
                COUNT(*) as sessions,
                COALESCE(SUM(json_extract(content_json, '$.cost')), 0) as cost,
                COALESCE(SUM(json_extract(content_json, '$.duration_ms')), 0) as duration_ms
            FROM messages WHERE {_base_where} AND timestamp >= ?
            GROUP BY day ORDER BY day
        """, (thirty_days_ago,)).fetchall()
        by_day = [
            {"day": r["day"], "sessions": r["sessions"], "cost": r["cost"], "duration_ms": r["duration_ms"]}
            for r in day_rows
        ]

        # 6. Monthly breakdown (all time)
        month_rows = conn.execute(f"""
            SELECT
                strftime('%Y-%m', timestamp, 'unixepoch', 'localtime') as month,
                COUNT(*) as sessions,
                COALESCE(SUM(json_extract(content_json, '$.cost')), 0) as cost,
                COALESCE(SUM(json_extract(content_json, '$.duration_ms')), 0) as duration_ms
            FROM messages WHERE {_base_where}
            GROUP BY month ORDER BY month
        """).fetchall()
        by_month = [
            {"month": r["month"], "sessions": r["sessions"], "cost": r["cost"], "duration_ms": r["duration_ms"]}
            for r in month_rows
        ]

    return {
        "totals": {
            "all_time": all_time,
            "today": today,
            "this_week": this_week,
            "this_month": this_month,
        },
        "by_hour": by_hour,
        "by_dow": by_dow,
        "by_day": by_day,
        "by_month": by_month,
    }
