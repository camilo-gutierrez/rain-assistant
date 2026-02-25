"""Task queue for inter-director delegation.

Directors can create tasks for other directors. Tasks are stored in the same
directors.db and processed by the scheduler loop.
"""

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

from .storage import _get_db, _ensure_dir


def _ensure_tasks_table(conn: sqlite3.Connection) -> None:
    """Create the director_tasks table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS director_tasks (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            description     TEXT DEFAULT '',
            creator_id      TEXT NOT NULL,
            assignee_id     TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            priority        INTEGER NOT NULL DEFAULT 5,
            task_type       TEXT NOT NULL DEFAULT 'analysis',
            input_data      TEXT NOT NULL DEFAULT '{}',
            output_data     TEXT NOT NULL DEFAULT '{}',
            depends_on      TEXT NOT NULL DEFAULT '[]',
            claimed_by      TEXT,
            claimed_at      REAL,
            completed_at    REAL,
            error_message   TEXT,
            retry_count     INTEGER NOT NULL DEFAULT 0,
            max_retries     INTEGER NOT NULL DEFAULT 2,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL,
            user_id         TEXT NOT NULL DEFAULT 'default'
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dtasks_status
        ON director_tasks(status, priority, user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dtasks_assignee
        ON director_tasks(assignee_id, status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dtasks_creator
        ON director_tasks(creator_id)
    """)
    conn.commit()


def _get_tasks_db() -> sqlite3.Connection:
    """Get DB connection with tasks table ensured."""
    conn = _get_db()
    _ensure_tasks_table(conn)
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict with parsed JSON fields."""
    d = dict(row)
    for field in ("input_data", "output_data"):
        try:
            d[field] = json.loads(d.get(field, "{}"))
        except (json.JSONDecodeError, TypeError):
            d[field] = {}
    try:
        d["depends_on"] = json.loads(d.get("depends_on", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["depends_on"] = []
    return d


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_task(
    title: str,
    creator_id: str,
    assignee_id: str | None = None,
    description: str = "",
    priority: int = 5,
    task_type: str = "analysis",
    input_data: dict | None = None,
    depends_on: list[str] | None = None,
    user_id: str = "default",
) -> dict:
    """Create a new task in the queue."""
    now = time.time()
    task_id = str(uuid.uuid4())[:8]

    conn = _get_tasks_db()
    try:
        conn.execute(
            """INSERT INTO director_tasks
               (id, title, description, creator_id, assignee_id, status, priority,
                task_type, input_data, depends_on, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, title, description, creator_id, assignee_id,
             max(1, min(10, priority)), task_type,
             json.dumps(input_data or {}, ensure_ascii=False),
             json.dumps(depends_on or [], ensure_ascii=False),
             now, now, user_id),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM director_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_tasks(
    user_id: str = "default",
    status: str | None = None,
    assignee_id: str | None = None,
    creator_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tasks with optional filters."""
    conn = _get_tasks_db()
    try:
        conditions = ["user_id = ?"]
        params: list = [user_id]

        if status:
            conditions.append("status = ?")
            params.append(status)
        if assignee_id:
            conditions.append("assignee_id = ?")
            params.append(assignee_id)
        if creator_id:
            conditions.append("creator_id = ?")
            params.append(creator_id)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = conn.execute(
            f"SELECT * FROM director_tasks WHERE {where} ORDER BY priority ASC, created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_task(task_id: str, user_id: str = "default") -> dict | None:
    """Get a specific task."""
    conn = _get_tasks_db()
    try:
        row = conn.execute(
            "SELECT * FROM director_tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def claim_task(task_id: str, director_id: str, user_id: str = "default") -> dict | None:
    """Atomically claim a pending task for a director."""
    now = time.time()
    conn = _get_tasks_db()
    try:
        cur = conn.execute(
            """UPDATE director_tasks
               SET status = 'running', claimed_by = ?, claimed_at = ?, updated_at = ?
               WHERE id = ? AND user_id = ? AND status = 'pending'""",
            (director_id, now, now, task_id, user_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None

        row = conn.execute("SELECT * FROM director_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def complete_task(task_id: str, output_data: dict | None = None, user_id: str = "default") -> dict | None:
    """Mark a task as completed with output data."""
    now = time.time()
    conn = _get_tasks_db()
    try:
        conn.execute(
            """UPDATE director_tasks
               SET status = 'completed', output_data = ?, completed_at = ?, updated_at = ?
               WHERE id = ? AND user_id = ?""",
            (json.dumps(output_data or {}, ensure_ascii=False), now, now, task_id, user_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM director_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def fail_task(task_id: str, error_message: str, user_id: str = "default") -> dict | None:
    """Mark a task as failed. Requeues if retries remain."""
    now = time.time()
    conn = _get_tasks_db()
    try:
        row = conn.execute("SELECT * FROM director_tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
        if not row:
            return None
        task = _row_to_dict(row)

        retry_count = task.get("retry_count", 0) + 1
        max_retries = task.get("max_retries", 2)

        if retry_count <= max_retries:
            # Requeue for retry
            conn.execute(
                """UPDATE director_tasks
                   SET status = 'pending', error_message = ?, retry_count = ?,
                       claimed_by = NULL, claimed_at = NULL, updated_at = ?
                   WHERE id = ?""",
                (error_message, retry_count, now, task_id),
            )
        else:
            # Permanently failed
            conn.execute(
                """UPDATE director_tasks
                   SET status = 'failed', error_message = ?, retry_count = ?, updated_at = ?
                   WHERE id = ?""",
                (error_message, retry_count, now, task_id),
            )
        conn.commit()

        row = conn.execute("SELECT * FROM director_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def cancel_task(task_id: str, user_id: str = "default") -> bool:
    """Cancel a pending or running task."""
    conn = _get_tasks_db()
    try:
        cur = conn.execute(
            """UPDATE director_tasks
               SET status = 'cancelled', updated_at = ?
               WHERE id = ? AND user_id = ? AND status IN ('pending', 'running')""",
            (time.time(), task_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_ready_tasks(assignee_id: str | None = None, user_id: str | None = None) -> list[dict]:
    """Get pending tasks whose dependencies are all completed.

    Used by the scheduler loop (user_id=None returns all users).
    """
    conn = _get_tasks_db()
    try:
        conditions = ["status = 'pending'"]
        params: list = []

        if assignee_id:
            conditions.append("assignee_id = ?")
            params.append(assignee_id)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM director_tasks WHERE {where} ORDER BY priority ASC, created_at ASC",
            params,
        ).fetchall()

        ready = []
        for row in rows:
            task = _row_to_dict(row)
            deps = task.get("depends_on", [])
            if not deps:
                ready.append(task)
                continue

            # Check all dependencies are completed
            placeholders = ",".join("?" for _ in deps)
            count = conn.execute(
                f"SELECT COUNT(*) FROM director_tasks WHERE id IN ({placeholders}) AND status = 'completed'",
                deps,
            ).fetchone()[0]
            if count == len(deps):
                ready.append(task)

        return ready
    finally:
        conn.close()


def get_task_stats(user_id: str = "default") -> dict:
    """Get task counts by status for the dashboard."""
    conn = _get_tasks_db()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM director_tasks WHERE user_id = ? GROUP BY status",
            (user_id,),
        ).fetchall()
        stats = {r["status"]: r["count"] for r in rows}
        stats["total"] = sum(stats.values())
        return stats
    finally:
        conn.close()
