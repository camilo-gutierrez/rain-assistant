"""Storage layer for Rain Scheduled Tasks — SQLite-based persistent scheduling.

Tasks are stored in ~/.rain-assistant/scheduler.db using a dedicated SQLite file
(separate from the main conversations.db to keep concerns isolated).

Cron expressions are parsed using croniter to calculate next_run times.
"""

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".rain-assistant"
SCHEDULER_DB = CONFIG_DIR / "scheduler.db"


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _get_db() -> sqlite3.Connection:
    """Open (and initialize) the scheduler database."""
    _ensure_dir()
    conn = sqlite3.connect(str(SCHEDULER_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            schedule    TEXT NOT NULL,
            enabled     INTEGER NOT NULL DEFAULT 1,
            task_type   TEXT NOT NULL DEFAULT 'reminder',
            task_data   TEXT NOT NULL DEFAULT '{}',
            last_run    REAL,
            next_run    REAL NOT NULL,
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL,
            last_result TEXT,
            last_error  TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_next_run
        ON scheduled_tasks(next_run, enabled)
    """)
    # Migration: add last_result and last_error columns if missing
    _migrate_add_result_columns(conn)
    conn.commit()
    return conn


def _migrate_add_result_columns(conn: sqlite3.Connection) -> None:
    """Add last_result and last_error columns to existing databases."""
    try:
        cursor = conn.execute("PRAGMA table_info(scheduled_tasks)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if "last_result" not in existing_columns:
            conn.execute("ALTER TABLE scheduled_tasks ADD COLUMN last_result TEXT")
            logger.info("Migration: added 'last_result' column to scheduled_tasks")

        if "last_error" not in existing_columns:
            conn.execute("ALTER TABLE scheduled_tasks ADD COLUMN last_error TEXT")
            logger.info("Migration: added 'last_error' column to scheduled_tasks")
    except sqlite3.OperationalError as e:
        logger.warning("Migration check failed (may already be up to date): %s", e)


def _calculate_next_run(cron_expr: str, base_time: float | None = None) -> float | None:
    """Calculate the next run time from a cron expression.

    Supports standard 5-field cron (minute hour day month weekday)
    and human-friendly aliases like @hourly, @daily, @weekly, @monthly.

    Returns Unix timestamp or None if croniter is not available.
    """
    try:
        from croniter import croniter
    except ImportError:
        logger.warning(
            "croniter not installed. Install with: pip install rain-assistant[scheduler]"
        )
        return None

    from datetime import datetime, timezone

    if base_time is None:
        base_time = time.time()

    base_dt = datetime.fromtimestamp(base_time, tz=timezone.utc)
    try:
        cron = croniter(cron_expr, base_dt)
        next_dt = cron.get_next(datetime)
        return next_dt.timestamp()
    except (ValueError, KeyError) as e:
        logger.error("Invalid cron expression '%s': %s", cron_expr, e)
        return None


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict with parsed task_data."""
    d = dict(row)
    try:
        d["task_data"] = json.loads(d.get("task_data", "{}"))
    except (json.JSONDecodeError, TypeError):
        d["task_data"] = {}
    d["enabled"] = bool(d.get("enabled", 0))
    return d


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def add_task(
    name: str,
    schedule: str,
    task_type: str = "reminder",
    description: str = "",
    task_data: dict | None = None,
) -> dict | None:
    """Create a new scheduled task.

    Args:
        name: Short human-readable name (e.g., "Weekly standup reminder").
        schedule: Cron expression (e.g., "0 9 * * 1" = every Monday at 9am).
        task_type: One of 'reminder', 'bash', 'ai_prompt'.
        description: Optional longer description.
        task_data: Type-specific data. For 'reminder': {"message": "..."}.
                  For 'bash': {"command": "..."}. For 'ai_prompt': {"prompt": "..."}.

    Returns:
        Created task dict, or None if cron expression is invalid.
    """
    next_run = _calculate_next_run(schedule)
    if next_run is None:
        return None

    now = time.time()
    task_id = str(uuid.uuid4())[:8]
    data_json = json.dumps(task_data or {}, ensure_ascii=False)

    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO scheduled_tasks
               (id, name, description, schedule, task_type, task_data, next_run, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, name, description, schedule, task_type, data_json, next_run, now, now),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_tasks(enabled_only: bool = False) -> list[dict]:
    """List all scheduled tasks, optionally filtering to enabled only."""
    conn = _get_db()
    try:
        if enabled_only:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE enabled = 1 ORDER BY next_run ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks ORDER BY enabled DESC, next_run ASC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_task(task_id: str) -> dict | None:
    """Get a specific task by ID."""
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_task(task_id: str, **kwargs) -> dict | None:
    """Update task fields. Recalculates next_run if schedule changes.

    Supported kwargs: name, description, schedule, task_type, task_data, enabled.
    """
    task = get_task(task_id)
    if not task:
        return None

    updates = []
    params = []

    for field in ("name", "description", "task_type"):
        if field in kwargs:
            updates.append(f"{field} = ?")
            params.append(kwargs[field])

    if "schedule" in kwargs:
        new_schedule = kwargs["schedule"]
        next_run = _calculate_next_run(new_schedule)
        if next_run is None:
            return None
        updates.append("schedule = ?")
        params.append(new_schedule)
        updates.append("next_run = ?")
        params.append(next_run)

    if "task_data" in kwargs:
        updates.append("task_data = ?")
        params.append(json.dumps(kwargs["task_data"], ensure_ascii=False))

    if "enabled" in kwargs:
        updates.append("enabled = ?")
        params.append(1 if kwargs["enabled"] else 0)

    if not updates:
        return task

    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(task_id)

    conn = _get_db()
    try:
        conn.execute(
            f"UPDATE scheduled_tasks SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def delete_task(task_id: str) -> bool:
    """Delete a task. Returns True if found and deleted."""
    conn = _get_db()
    try:
        cur = conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def enable_task(task_id: str) -> dict | None:
    """Enable a task and recalculate its next_run from now."""
    task = get_task(task_id)
    if not task:
        return None

    next_run = _calculate_next_run(task["schedule"])
    if next_run is None:
        return None

    conn = _get_db()
    try:
        conn.execute(
            "UPDATE scheduled_tasks SET enabled = 1, next_run = ?, updated_at = ? WHERE id = ?",
            (next_run, time.time(), task_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def disable_task(task_id: str) -> dict | None:
    """Disable a task (stops it from running)."""
    return update_task(task_id, enabled=False)


def get_pending_tasks(now: float | None = None) -> list[dict]:
    """Get all enabled tasks whose next_run is <= now."""
    if now is None:
        now = time.time()

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE enabled = 1 AND next_run <= ? ORDER BY next_run ASC",
            (now,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def mark_task_run(
    task_id: str,
    result: str | None = None,
    error: str | None = None,
) -> dict | None:
    """Mark a task as having just run: update last_run, calculate next_run, and optionally store result/error.

    Args:
        task_id: The task ID.
        result: Optional result text from execution (e.g., AI response, bash stdout).
        error: Optional error text if execution failed.
    """
    task = get_task(task_id)
    if not task:
        return None

    now = time.time()
    next_run = _calculate_next_run(task["schedule"], base_time=now)
    if next_run is None:
        return None

    conn = _get_db()
    try:
        conn.execute(
            """UPDATE scheduled_tasks
               SET last_run = ?, next_run = ?, updated_at = ?,
                   last_result = ?, last_error = ?
               WHERE id = ?""",
            (now, next_run, now, result, error, task_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()
