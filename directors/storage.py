"""Storage layer for Rain Autonomous Directors — SQLite-based persistence.

Directors are stored in ~/.rain-assistant/directors.db using a dedicated SQLite
file (separate from conversations.db and scheduler.db).

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
DIRECTORS_DB = CONFIG_DIR / "directors.db"


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _get_db() -> sqlite3.Connection:
    """Open (and initialize) the directors database."""
    _ensure_dir()
    conn = sqlite3.connect(str(DIRECTORS_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS directors (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            emoji           TEXT DEFAULT '🤖',
            description     TEXT DEFAULT '',
            role_prompt     TEXT NOT NULL,
            schedule        TEXT,
            enabled         INTEGER NOT NULL DEFAULT 1,
            tools_allowed   TEXT NOT NULL DEFAULT '["*"]',
            plugins_allowed TEXT NOT NULL DEFAULT '["*"]',
            permission_level TEXT NOT NULL DEFAULT 'green',
            can_delegate    INTEGER NOT NULL DEFAULT 0,
            context_window  TEXT NOT NULL DEFAULT '{}',
            last_run        REAL,
            next_run        REAL,
            last_result     TEXT,
            last_error      TEXT,
            run_count       INTEGER NOT NULL DEFAULT 0,
            total_cost      REAL NOT NULL DEFAULT 0.0,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL,
            user_id         TEXT NOT NULL DEFAULT 'default'
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_directors_user
        ON directors(user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_directors_schedule
        ON directors(next_run, enabled)
    """)
    conn.commit()
    return conn


def _calculate_next_run(cron_expr: str, base_time: float | None = None) -> float | None:
    """Calculate the next run time from a cron expression."""
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
    """Convert a sqlite3.Row to a plain dict with parsed JSON fields."""
    d = dict(row)
    d["enabled"] = bool(d.get("enabled", 0))
    d["can_delegate"] = bool(d.get("can_delegate", 0))
    for field in ("tools_allowed", "plugins_allowed", "context_window"):
        try:
            d[field] = json.loads(d.get(field, "{}"))
        except (json.JSONDecodeError, TypeError):
            d[field] = {} if field == "context_window" else ["*"]
    return d


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def add_director(
    id: str,
    name: str,
    role_prompt: str,
    schedule: str | None = None,
    description: str = "",
    emoji: str = "🤖",
    tools_allowed: list[str] | None = None,
    plugins_allowed: list[str] | None = None,
    permission_level: str = "green",
    can_delegate: bool = False,
    user_id: str = "default",
) -> dict | None:
    """Create a new director.

    Returns:
        Created director dict, or None if cron expression is invalid.
    """
    next_run = None
    if schedule:
        next_run = _calculate_next_run(schedule)
        if next_run is None:
            return None

    now = time.time()
    tools_json = json.dumps(tools_allowed or ["*"], ensure_ascii=False)
    plugins_json = json.dumps(plugins_allowed or ["*"], ensure_ascii=False)

    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO directors
               (id, name, emoji, description, role_prompt, schedule, enabled,
                tools_allowed, plugins_allowed, permission_level, can_delegate,
                next_run, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (id, name, emoji, description, role_prompt, schedule,
             tools_json, plugins_json, permission_level, 1 if can_delegate else 0,
             next_run, now, now, user_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM directors WHERE id = ? AND user_id = ?",
            (id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    except sqlite3.IntegrityError:
        logger.error("Director '%s' already exists", id)
        return None
    finally:
        conn.close()


def list_directors(user_id: str = "default", enabled_only: bool = False) -> list[dict]:
    """List directors for a specific user."""
    conn = _get_db()
    try:
        if enabled_only:
            rows = conn.execute(
                "SELECT * FROM directors WHERE user_id = ? AND enabled = 1 ORDER BY name ASC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM directors WHERE user_id = ? ORDER BY enabled DESC, name ASC",
                (user_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_director(director_id: str, user_id: str = "default") -> dict | None:
    """Get a specific director by ID, scoped to a user."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM directors WHERE id = ? AND user_id = ?",
            (director_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_director(director_id: str, user_id: str = "default", **kwargs) -> dict | None:
    """Update director fields. Recalculates next_run if schedule changes."""
    director = get_director(director_id, user_id=user_id)
    if not director:
        return None

    updates = []
    params = []

    for field in ("name", "emoji", "description", "role_prompt", "permission_level"):
        if field in kwargs:
            updates.append(f"{field} = ?")
            params.append(kwargs[field])

    if "schedule" in kwargs:
        new_schedule = kwargs["schedule"]
        if new_schedule:
            next_run = _calculate_next_run(new_schedule)
            if next_run is None:
                return None
            updates.append("schedule = ?")
            params.append(new_schedule)
            updates.append("next_run = ?")
            params.append(next_run)
        else:
            updates.append("schedule = ?")
            params.append(None)
            updates.append("next_run = ?")
            params.append(None)

    for field in ("tools_allowed", "plugins_allowed"):
        if field in kwargs:
            updates.append(f"{field} = ?")
            params.append(json.dumps(kwargs[field], ensure_ascii=False))

    if "context_window" in kwargs:
        updates.append("context_window = ?")
        params.append(json.dumps(kwargs["context_window"], ensure_ascii=False))

    if "can_delegate" in kwargs:
        updates.append("can_delegate = ?")
        params.append(1 if kwargs["can_delegate"] else 0)

    if "enabled" in kwargs:
        updates.append("enabled = ?")
        params.append(1 if kwargs["enabled"] else 0)

    if not updates:
        return director

    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(director_id)
    params.append(user_id)

    conn = _get_db()
    try:
        conn.execute(
            f"UPDATE directors SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            params,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM directors WHERE id = ? AND user_id = ?",
            (director_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def delete_director(director_id: str, user_id: str = "default") -> bool:
    """Delete a director. Returns True if found and deleted."""
    conn = _get_db()
    try:
        cur = conn.execute(
            "DELETE FROM directors WHERE id = ? AND user_id = ?",
            (director_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def enable_director(director_id: str, user_id: str = "default") -> dict | None:
    """Enable a director and recalculate its next_run from now."""
    director = get_director(director_id, user_id=user_id)
    if not director:
        return None

    next_run = None
    if director.get("schedule"):
        next_run = _calculate_next_run(director["schedule"])

    conn = _get_db()
    try:
        conn.execute(
            "UPDATE directors SET enabled = 1, next_run = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (next_run, time.time(), director_id, user_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM directors WHERE id = ? AND user_id = ?",
            (director_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def disable_director(director_id: str, user_id: str = "default") -> dict | None:
    """Disable a director (stops scheduled execution)."""
    return update_director(director_id, user_id=user_id, enabled=False)


def get_pending_directors(now: float | None = None) -> list[dict]:
    """Get all enabled directors whose next_run is <= now (for ALL users).

    Used by the scheduler loop.
    """
    if now is None:
        now = time.time()

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM directors WHERE enabled = 1 AND schedule IS NOT NULL AND next_run IS NOT NULL AND next_run <= ? ORDER BY next_run ASC",
            (now,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def mark_director_run(
    director_id: str,
    result: str | None = None,
    error: str | None = None,
    cost: float = 0.0,
) -> dict | None:
    """Mark a director as having just run: update counters and reschedule."""
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM directors WHERE id = ?", (director_id,)).fetchone()
        if not row:
            return None
        director = _row_to_dict(row)

        now = time.time()
        next_run = None
        if director.get("schedule"):
            next_run = _calculate_next_run(director["schedule"], base_time=now)

        conn.execute(
            """UPDATE directors
               SET last_run = ?, next_run = ?, updated_at = ?,
                   last_result = ?, last_error = ?,
                   run_count = run_count + 1,
                   total_cost = total_cost + ?
               WHERE id = ?""",
            (now, next_run, now, result, error, cost, director_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM directors WHERE id = ?", (director_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_context(director_id: str, user_id: str = "default", key: str = "", value: str = "") -> dict | None:
    """Update a key in a director's persistent context window."""
    director = get_director(director_id, user_id=user_id)
    if not director:
        return None

    context = director.get("context_window", {})
    if not isinstance(context, dict):
        context = {}

    if value:
        context[key] = value
    else:
        context.pop(key, None)

    return update_director(director_id, user_id=user_id, context_window=context)


def migrate_directors() -> dict:
    """Ensure directors DB is initialized. Idempotent — safe to call on every startup."""
    try:
        conn = _get_db()
        conn.close()
        return {"status": "ok", "message": "directors migration complete"}
    except Exception as e:
        logger.error("Failed to migrate directors: %s", e)
        return {"status": "error", "message": str(e)}
