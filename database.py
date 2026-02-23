import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

from cryptography.fernet import Fernet

from key_manager import ensure_encryption_key

DB_PATH = Path.home() / ".rain-assistant" / "conversations.db"
CONFIG_DIR = Path.home() / ".rain-assistant"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _secure_chmod(path: Path, mode: int) -> None:
    """Best-effort chmod. Windows has limited support, so errors are ignored."""
    try:
        os.chmod(str(path), mode)
    except OSError:
        pass  # Windows has limited chmod support


# ---------------------------------------------------------------------------
# Encryption key management (Fernet)
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    """Load or auto-generate encryption key via the OS keyring (with config.json fallback)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _secure_chmod(CONFIG_DIR, 0o700)
    enc_key = ensure_encryption_key(CONFIG_FILE)
    return Fernet(enc_key.encode("utf-8"))


_fernet: Fernet | None = None


def _get_cipher() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _get_fernet()
    return _fernet


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field for DB storage. Returns base64 ciphertext."""
    if not plaintext:
        return plaintext
    return _get_cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")


_FERNET_PREFIX = "gAAAA"


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a field, with backward compat for pre-encryption data.

    - Legacy unencrypted data (not starting with ``gAAAA``) is returned as-is.
    - Valid Fernet tokens are decrypted normally.
    - If a Fernet token fails to decrypt, a ``ValueError`` is raised to signal
      possible data tampering or key mismatch.
    """
    if not ciphertext:
        return ciphertext

    # Check if this looks like a Fernet token
    if not ciphertext.startswith(_FERNET_PREFIX):
        # Legacy unencrypted data — return as-is
        return ciphertext

    try:
        return _get_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        # This IS a Fernet token but decryption failed — possible tampering
        import logging
        logging.getLogger(__name__).error(
            "Decryption failed for Fernet token (possible data tampering): %s",
            type(e).__name__
        )
        raise ValueError("Decryption failed — possible data tampering or key mismatch") from e


def _ensure_db():
    """Create tables and indexes if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _secure_chmod(DB_PATH.parent, 0o700)
    with _connect() as conn:
        # Enable WAL mode for better concurrent read/write performance
        conn.execute("PRAGMA journal_mode=WAL")

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
        # Permission audit log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permission_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    REAL NOT NULL,
                agent_id     TEXT NOT NULL,
                tool_name    TEXT NOT NULL,
                tool_input   TEXT NOT NULL,
                level        TEXT NOT NULL,
                decision     TEXT NOT NULL,
                reason       TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_perm_log_ts
            ON permission_log(timestamp DESC)
        """)

        # ── Phase 3 tables ──

        # HTTP access log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS access_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    REAL NOT NULL,
                method       TEXT NOT NULL,
                path         TEXT NOT NULL,
                status_code  INTEGER NOT NULL,
                response_ms  REAL NOT NULL,
                client_ip    TEXT NOT NULL,
                token_prefix TEXT DEFAULT '',
                user_agent   TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_access_log_ts
            ON access_log(timestamp DESC)
        """)

        # Security events / alerts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    REAL NOT NULL,
                event_type   TEXT NOT NULL,
                severity     TEXT NOT NULL DEFAULT 'info',
                client_ip    TEXT DEFAULT '',
                token_prefix TEXT DEFAULT '',
                details      TEXT DEFAULT '',
                endpoint     TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sec_events_ts
            ON security_events(timestamp DESC)
        """)

        # TTS / audio daily usage quotas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_quotas (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                token_prefix TEXT NOT NULL,
                date_key     TEXT NOT NULL,
                tts_chars    INTEGER NOT NULL DEFAULT 0,
                audio_seconds REAL NOT NULL DEFAULT 0.0,
                UNIQUE(token_prefix, date_key)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_quotas_lookup
            ON usage_quotas(token_prefix, date_key)
        """)

        # Active session tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                token_hash    TEXT PRIMARY KEY,
                created_at    REAL NOT NULL,
                last_activity REAL NOT NULL,
                client_ip     TEXT NOT NULL,
                user_agent    TEXT DEFAULT '',
                request_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_activity
            ON active_sessions(last_activity DESC)
        """)

        # Users table for per-user data isolation
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                created_at    REAL NOT NULL,
                last_login    REAL NOT NULL,
                metadata      TEXT DEFAULT '{}'
            )
        """)

        # Migrate: add device columns if missing (upgrade from old schema)
        _migrate_device_columns(conn)

        # Migration: add user_id to active_sessions if missing
        cursor = conn.execute("PRAGMA table_info(active_sessions)")
        columns = {row[1] for row in cursor.fetchall()}
        if "user_id" not in columns:
            conn.execute("ALTER TABLE active_sessions ADD COLUMN user_id TEXT DEFAULT 'default'")
            conn.execute("UPDATE active_sessions SET user_id = 'default' WHERE user_id IS NULL")
            conn.commit()

        conn.commit()

    # Restrict DB file permissions after creation
    if DB_PATH.exists():
        _secure_chmod(DB_PATH, 0o600)


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


def _migrate_device_columns(conn):
    """Add device_id and device_name columns to active_sessions."""
    cursor = conn.execute("PRAGMA table_info(active_sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "device_id" not in columns:
        conn.execute("ALTER TABLE active_sessions ADD COLUMN device_id TEXT DEFAULT ''")
        conn.execute("ALTER TABLE active_sessions ADD COLUMN device_name TEXT DEFAULT ''")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_device
            ON active_sessions(device_id)
        """)
    if "encrypted_token" not in columns:
        conn.execute("ALTER TABLE active_sessions ADD COLUMN encrypted_token TEXT DEFAULT ''")


@contextmanager
def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


_ENCRYPTED_MSG_TYPES = {"text", "assistant_text", "tool_use", "tool_result"}


def save_message(cwd: str, role: str, msg_type: str, content: dict, agent_id: str = "default") -> int:
    """Insert a message and return its id.

    Content is encrypted at rest for sensitive message types (text, assistant_text,
    tool_use, tool_result). The 'result' type is NOT encrypted because metrics
    queries use json_extract() on it.
    """
    content_json = json.dumps(content, default=str)
    if msg_type in _ENCRYPTED_MSG_TYPES:
        content_json = encrypt_field(content_json)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages (cwd, agent_id, role, type, content_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cwd, agent_id, role, msg_type, content_json, time.time()),
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
    results = []
    for r in rows:
        raw = r["content_json"]
        # Decrypt if this type is encrypted
        if r["type"] in _ENCRYPTED_MSG_TYPES:
            try:
                raw = decrypt_field(raw)
            except ValueError:
                raw = json.dumps({"text": "[encrypted content — decryption failed]"})
        results.append({
            "id": r["id"],
            "role": r["role"],
            "type": r["type"],
            "content": json.loads(raw),
            "timestamp": r["timestamp"],
        })
    return results


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


# ---------------------------------------------------------------------------
# Permission audit log
# ---------------------------------------------------------------------------

def log_permission_decision(
    agent_id: str,
    tool_name: str,
    tool_input: dict,
    level: str,
    decision: str,
    reason: str = "",
) -> int:
    """Log a permission decision to the audit trail.

    Args:
        agent_id: The agent that requested the tool.
        tool_name: Name of the tool (e.g. "Bash", "Write").
        tool_input: Tool input parameters (truncated to 2000 chars).
        level: Permission level ("green", "yellow", "red").
        decision: "approved", "denied", or "timeout".
        reason: Human-readable reason for the decision.

    Returns:
        Row id of the inserted log entry.
    """
    with _connect() as conn:
        tool_input_json = json.dumps(tool_input, default=str)[:2000]
        cur = conn.execute(
            "INSERT INTO permission_log "
            "(timestamp, agent_id, tool_name, tool_input, level, decision, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                time.time(),
                agent_id,
                tool_name,
                encrypt_field(tool_input_json),
                level,
                decision,
                reason,
            ),
        )
        conn.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Access logging
# ---------------------------------------------------------------------------

def log_access(
    method: str, path: str, status_code: int, response_ms: float,
    client_ip: str, token_prefix: str = "", user_agent: str = "",
) -> None:
    """Insert an HTTP access log entry."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO access_log "
                "(timestamp, method, path, status_code, response_ms, client_ip, token_prefix, user_agent) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), method, path[:500], status_code, response_ms,
                 client_ip, token_prefix[:16], user_agent[:200]),
            )
            conn.commit()
    except Exception as e:
        import sys
        print(f"[SECURITY LOG FAILURE] log_access: {e}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Security events
# ---------------------------------------------------------------------------

def log_security_event(
    event_type: str, severity: str = "info", client_ip: str = "",
    token_prefix: str = "", details: str = "", endpoint: str = "",
) -> None:
    """Insert a security event for monitoring/alerting."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, severity, client_ip, token_prefix, details, endpoint) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (time.time(), event_type, severity, client_ip,
                 token_prefix[:16], encrypt_field(details[:2000]), endpoint[:500]),
            )
            conn.commit()
    except Exception as e:
        import sys
        print(f"[SECURITY LOG FAILURE] log_security_event: {e}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Usage quotas (TTS / audio)
# ---------------------------------------------------------------------------

def get_or_create_quota(token_prefix: str, date_key: str) -> dict:
    """Get current quota usage for a token+date, creating row if needed."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT tts_chars, audio_seconds FROM usage_quotas "
            "WHERE token_prefix = ? AND date_key = ?",
            (token_prefix[:16], date_key),
        ).fetchone()
        if row:
            return {"tts_chars": row["tts_chars"], "audio_seconds": row["audio_seconds"]}
        conn.execute(
            "INSERT OR IGNORE INTO usage_quotas (token_prefix, date_key) VALUES (?, ?)",
            (token_prefix[:16], date_key),
        )
        conn.commit()
        return {"tts_chars": 0, "audio_seconds": 0.0}


def increment_tts_chars(token_prefix: str, date_key: str, chars: int) -> int:
    """Atomically increment TTS char count. Returns new total."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO usage_quotas (token_prefix, date_key, tts_chars) VALUES (?, ?, ?) "
            "ON CONFLICT(token_prefix, date_key) DO UPDATE SET tts_chars = tts_chars + ?",
            (token_prefix[:16], date_key, chars, chars),
        )
        conn.commit()
        row = conn.execute(
            "SELECT tts_chars FROM usage_quotas WHERE token_prefix = ? AND date_key = ?",
            (token_prefix[:16], date_key),
        ).fetchone()
        return row["tts_chars"] if row else chars


def increment_audio_seconds(token_prefix: str, date_key: str, seconds: float) -> float:
    """Atomically increment audio seconds. Returns new total."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO usage_quotas (token_prefix, date_key, audio_seconds) VALUES (?, ?, ?) "
            "ON CONFLICT(token_prefix, date_key) DO UPDATE SET audio_seconds = audio_seconds + ?",
            (token_prefix[:16], date_key, seconds, seconds),
        )
        conn.commit()
        row = conn.execute(
            "SELECT audio_seconds FROM usage_quotas WHERE token_prefix = ? AND date_key = ?",
            (token_prefix[:16], date_key),
        ).fetchone()
        return row["audio_seconds"] if row else seconds


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def create_session(
    token_hash: str,
    client_ip: str,
    user_agent: str = "",
    device_id: str = "",
    device_name: str = "",
    user_id: str = "default",
    encrypted_token: str = "",
) -> None:
    """Record a new active session."""
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO active_sessions "
            "(token_hash, created_at, last_activity, client_ip, user_agent, request_count, device_id, device_name, user_id, encrypted_token) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
            (token_hash, now, now, client_ip, user_agent[:200], device_id[:64], device_name[:100], user_id, encrypted_token),
        )
        conn.commit()


def update_session_activity(token_hash: str) -> None:
    """Bump last_activity and increment request_count."""
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE active_sessions SET last_activity = ?, request_count = request_count + 1 "
                "WHERE token_hash = ?",
                (time.time(), token_hash),
            )
            conn.commit()
    except Exception as e:
        import sys
        print(f"[SECURITY LOG FAILURE] update_session_activity: {e}", file=sys.stderr, flush=True)


def revoke_session(token_hash: str) -> None:
    """Delete a session record."""
    with _connect() as conn:
        conn.execute("DELETE FROM active_sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()


def revoke_all_sessions() -> int:
    """Delete all session records. Returns count deleted."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM active_sessions")
        conn.commit()
        return cur.rowcount


# ---------------------------------------------------------------------------
# Device management
# ---------------------------------------------------------------------------

def get_active_devices() -> list[dict]:
    """Return all active sessions with device info."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT token_hash, device_id, device_name, client_ip, user_agent, "
            "created_at, last_activity FROM active_sessions "
            "ORDER BY last_activity DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def count_active_devices(max_age_seconds: float = 0) -> int:
    """Count distinct active device_ids (excluding empty).

    If *max_age_seconds* > 0, only sessions whose ``last_activity`` is
    within that window are counted — stale/expired sessions are ignored.
    """
    with _connect() as conn:
        if max_age_seconds > 0:
            cutoff = time.time() - max_age_seconds
            row = conn.execute(
                "SELECT COUNT(DISTINCT device_id) FROM active_sessions "
                "WHERE device_id != '' AND last_activity >= ?",
                (cutoff,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(DISTINCT device_id) FROM active_sessions WHERE device_id != ''"
            ).fetchone()
        return row[0] if row else 0


def get_session_by_device_id(device_id: str) -> dict | None:
    """Find an existing session for a device."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT token_hash, device_id, device_name, client_ip, user_agent, "
            "created_at, last_activity FROM active_sessions WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        return dict(row) if row else None


def revoke_session_by_device_id(device_id: str) -> str | None:
    """Delete session by device_id. Returns token_hash for in-memory cleanup, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT token_hash FROM active_sessions WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            return None
        token_hash = row[0]
        conn.execute("DELETE FROM active_sessions WHERE device_id = ?", (device_id,))
        conn.commit()
        return token_hash


def rename_device(device_id: str, new_name: str) -> bool:
    """Update device_name for a device. Returns True if updated."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE active_sessions SET device_name = ? WHERE device_id = ?",
            (new_name[:100], device_id),
        )
        conn.commit()
        return cur.rowcount > 0


def cleanup_expired_sessions(max_age_seconds: float) -> int:
    """Delete sessions older than max_age_seconds. Returns count deleted."""
    cutoff = time.time() - max_age_seconds
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM active_sessions WHERE last_activity < ?", (cutoff,)
        )
        conn.commit()
        return cur.rowcount


def load_persisted_tokens(max_age_seconds: float) -> list[dict]:
    """Load non-expired sessions that have an encrypted_token.

    Returns list of {encrypted_token, token_hash, device_id, created_at, last_activity}.
    """
    cutoff = time.time() - max_age_seconds
    with _connect() as conn:
        rows = conn.execute(
            "SELECT encrypted_token, token_hash, device_id, created_at, last_activity "
            "FROM active_sessions "
            "WHERE encrypted_token != '' AND last_activity >= ?",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Per-user data isolation helpers
# ---------------------------------------------------------------------------

def get_user_id_from_token(token_hash: str) -> str:
    """Look up user_id from a token_hash. Returns 'default' if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM active_sessions WHERE token_hash = ?",
            (token_hash,)
        ).fetchone()
        return row[0] if row and row[0] else "default"


def create_user(user_id: str, metadata: dict | None = None) -> None:
    """Create a new user record (idempotent)."""
    import json as _json
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, created_at, last_login, metadata) VALUES (?, ?, ?, ?)",
            (user_id, now, now, _json.dumps(metadata or {}))
        )
        conn.commit()


def update_user_login(user_id: str) -> None:
    """Update user's last_login timestamp."""
    with _connect() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (time.time(), user_id))
        conn.commit()
