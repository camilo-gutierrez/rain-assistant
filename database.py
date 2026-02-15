import json
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path.home() / ".rain-assistant" / "conversations.db"


def _ensure_db():
    """Create tables and indexes if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_cwd
            ON messages(cwd, timestamp)
        """)
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_message(cwd: str, role: str, msg_type: str, content: dict) -> int:
    """Insert a message and return its id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages (cwd, role, type, content_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (cwd, role, msg_type, json.dumps(content, default=str), time.time()),
        )
        conn.commit()
        return cur.lastrowid


def get_messages(cwd: str) -> list[dict]:
    """Return all messages for a cwd, ordered by timestamp."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, type, content_json, timestamp "
            "FROM messages WHERE cwd = ? ORDER BY timestamp ASC",
            (cwd,),
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


def clear_messages(cwd: str) -> int:
    """Delete all messages for a cwd. Returns count deleted."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM messages WHERE cwd = ?", (cwd,))
        conn.commit()
        return cur.rowcount
