"""Inbox system for director deliverables.

Directors save their outputs (reports, drafts, analyses, code) to the inbox.
Users review, approve, reject, or archive items.
"""

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

from .storage import _get_db, _ensure_dir


def _ensure_inbox_table(conn: sqlite3.Connection) -> None:
    """Create the director_inbox table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS director_inbox (
            id              TEXT PRIMARY KEY,
            director_id     TEXT NOT NULL,
            director_name   TEXT NOT NULL,
            title           TEXT NOT NULL,
            content         TEXT NOT NULL,
            content_type    TEXT NOT NULL DEFAULT 'report',
            status          TEXT NOT NULL DEFAULT 'unread',
            priority        INTEGER NOT NULL DEFAULT 5,
            task_id         TEXT,
            metadata        TEXT NOT NULL DEFAULT '{}',
            user_comment    TEXT,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL,
            user_id         TEXT NOT NULL DEFAULT 'default'
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_inbox_status
        ON director_inbox(status, user_id, created_at DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_inbox_director
        ON director_inbox(director_id, user_id)
    """)
    conn.commit()


def _get_inbox_db() -> sqlite3.Connection:
    """Get DB connection with inbox table ensured."""
    conn = _get_db()
    _ensure_inbox_table(conn)
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict with parsed JSON fields."""
    d = dict(row)
    try:
        d["metadata"] = json.loads(d.get("metadata", "{}"))
    except (json.JSONDecodeError, TypeError):
        d["metadata"] = {}
    return d


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def add_inbox_item(
    director_id: str,
    director_name: str,
    title: str,
    content: str,
    content_type: str = "report",
    priority: int = 5,
    task_id: str | None = None,
    metadata: dict | None = None,
    user_id: str = "default",
) -> dict:
    """Add a new item to the inbox."""
    now = time.time()
    item_id = str(uuid.uuid4())[:8]

    conn = _get_inbox_db()
    try:
        conn.execute(
            """INSERT INTO director_inbox
               (id, director_id, director_name, title, content, content_type,
                status, priority, task_id, metadata, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, 'unread', ?, ?, ?, ?, ?, ?)""",
            (item_id, director_id, director_name, title, content, content_type,
             max(1, min(10, priority)), task_id,
             json.dumps(metadata or {}, ensure_ascii=False),
             now, now, user_id),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM director_inbox WHERE id = ?", (item_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_inbox(
    user_id: str = "default",
    status: str | None = None,
    director_id: str | None = None,
    content_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List inbox items with optional filters."""
    conn = _get_inbox_db()
    try:
        conditions = ["user_id = ?"]
        params: list = [user_id]

        if status:
            conditions.append("status = ?")
            params.append(status)
        if director_id:
            conditions.append("director_id = ?")
            params.append(director_id)
        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        rows = conn.execute(
            f"SELECT * FROM director_inbox WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_inbox_item(item_id: str, user_id: str = "default") -> dict | None:
    """Get a specific inbox item."""
    conn = _get_inbox_db()
    try:
        row = conn.execute(
            "SELECT * FROM director_inbox WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_inbox_status(
    item_id: str,
    status: str,
    user_comment: str | None = None,
    user_id: str = "default",
) -> dict | None:
    """Update an inbox item's status (read, approved, rejected, archived)."""
    valid_statuses = ("unread", "read", "approved", "rejected", "archived")
    if status not in valid_statuses:
        return None

    now = time.time()
    conn = _get_inbox_db()
    try:
        if user_comment is not None:
            conn.execute(
                """UPDATE director_inbox
                   SET status = ?, user_comment = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?""",
                (status, user_comment, now, item_id, user_id),
            )
        else:
            conn.execute(
                """UPDATE director_inbox
                   SET status = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?""",
                (status, now, item_id, user_id),
            )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM director_inbox WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_unread_count(user_id: str = "default") -> int:
    """Get the number of unread inbox items."""
    conn = _get_inbox_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM director_inbox WHERE user_id = ? AND status = 'unread'",
            (user_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def archive_old_items(days: int = 30, user_id: str = "default") -> int:
    """Archive items older than N days that aren't already archived."""
    cutoff = time.time() - (days * 86400)
    conn = _get_inbox_db()
    try:
        cur = conn.execute(
            """UPDATE director_inbox
               SET status = 'archived', updated_at = ?
               WHERE user_id = ? AND status NOT IN ('archived') AND created_at < ?""",
            (time.time(), user_id, cutoff),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
