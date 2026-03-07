"""Tests for the audit log module."""

import json
import time
import sqlite3
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit.logger import AuditEvent, AuditEventType, AuditLogger
from audit.storage import AuditStorage


# ── AuditEvent tests ─────────────────────────────────────────────────────────


class TestAuditEvent:
    def test_event_creation(self):
        event = AuditEvent(
            event_id="test-1",
            event_type=AuditEventType.TOOL_EXECUTED,
            timestamp=1000.0,
            user_id="user1",
            tool_name="bash",
            action="execute",
            result="success",
        )
        assert event.event_id == "test-1"
        assert event.event_type == AuditEventType.TOOL_EXECUTED
        assert event.user_id == "user1"
        assert event.tool_name == "bash"

    def test_hash_computation_deterministic(self):
        event = AuditEvent(
            event_id="test-1",
            event_type=AuditEventType.TOOL_EXECUTED,
            timestamp=1000.0,
            prev_hash="genesis",
        )
        h1 = event.compute_hash()
        h2 = event.compute_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_hash_changes_with_different_data(self):
        base = dict(
            event_id="test-1",
            event_type=AuditEventType.TOOL_EXECUTED,
            timestamp=1000.0,
            prev_hash="genesis",
        )
        e1 = AuditEvent(**base)
        e2 = AuditEvent(**{**base, "event_id": "test-2"})
        assert e1.compute_hash() != e2.compute_hash()

    def test_to_dict(self):
        event = AuditEvent(
            event_id="test-1",
            event_type=AuditEventType.AUTH_SUCCESS,
            timestamp=1000.0,
            details={"reason": "valid token"},
        )
        d = event.to_dict()
        assert d["event_type"] == "auth_success"
        assert d["details"] == {"reason": "valid token"}
        assert "event_id" in d


# ── Hash chain tests ─────────────────────────────────────────────────────────


class TestHashChain:
    def test_chain_linkage(self):
        logger = AuditLogger()
        e1 = logger.log_auth_success(user_id="u1")
        e2 = logger.log_auth_success(user_id="u2")
        assert e1.prev_hash == "genesis"
        assert e2.prev_hash == e1.event_hash
        assert e2.event_hash != e1.event_hash

    def test_chain_three_events(self):
        logger = AuditLogger()
        events = []
        for i in range(3):
            events.append(logger.log_auth_success(user_id=f"u{i}"))
        assert events[0].prev_hash == "genesis"
        assert events[1].prev_hash == events[0].event_hash
        assert events[2].prev_hash == events[1].event_hash


# ── AuditLogger convenience method tests ─────────────────────────────────────


class TestAuditLogger:
    def test_log_tool_executed(self):
        logger = AuditLogger()
        event = logger.log_tool_executed("bash", {"command": "ls"}, "green", user_id="u1")
        assert event.event_type == AuditEventType.TOOL_EXECUTED
        assert event.tool_name == "bash"
        assert event.result == "success"
        assert event.details["permission_level"] == "green"

    def test_log_tool_denied(self):
        logger = AuditLogger()
        event = logger.log_tool_denied("rm_rf", {}, "user rejected", user_id="u1")
        assert event.event_type == AuditEventType.TOOL_DENIED
        assert event.result == "denied"
        assert event.details["reason"] == "user rejected"

    def test_log_auth_success(self):
        logger = AuditLogger()
        event = logger.log_auth_success(user_id="admin", ip="192.168.1.1")
        assert event.event_type == AuditEventType.AUTH_SUCCESS
        assert event.ip_address == "192.168.1.1"
        assert event.result == "success"

    def test_log_auth_failure(self):
        logger = AuditLogger()
        event = logger.log_auth_failure(ip="10.0.0.1", reason="bad password")
        assert event.event_type == AuditEventType.AUTH_FAILURE
        assert event.result == "denied"

    def test_log_config_changed(self):
        logger = AuditLogger()
        event = logger.log_config_changed("model", user_id="admin")
        assert event.event_type == AuditEventType.CONFIG_CHANGED
        assert event.details["key"] == "model"

    def test_log_policy_violation(self):
        logger = AuditLogger()
        event = logger.log_policy_violation("rate_limit", {"count": 100}, user_id="u1")
        assert event.event_type == AuditEventType.POLICY_VIOLATION
        assert event.details["policy"] == "rate_limit"
        assert event.details["count"] == 100

    def test_log_computer_use_action(self):
        logger = AuditLogger()
        event = logger.log_computer_use_action("click", {"x": 100, "y": 200})
        assert event.event_type == AuditEventType.COMPUTER_USE_ACTION
        assert event.tool_name == "computer"
        assert event.action == "click"

    def test_event_count(self):
        logger = AuditLogger()
        logger.log_auth_success()
        logger.log_auth_success()
        logger.log_auth_failure()
        assert logger._event_count == 3


# ── Sanitize input tests ─────────────────────────────────────────────────────


class TestSanitizeInput:
    def test_redacts_sensitive_keys(self):
        result = AuditLogger._sanitize_input({
            "api_key": "sk-123456",
            "password": "hunter2",
            "command": "ls",
        })
        assert result["api_key"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"
        assert result["command"] == "ls"

    def test_redacts_partial_match(self):
        result = AuditLogger._sanitize_input({
            "my_secret_value": "shh",
            "auth_token": "tok-abc",
        })
        assert result["my_secret_value"] == "***REDACTED***"
        assert result["auth_token"] == "***REDACTED***"

    def test_truncates_long_values(self):
        long_val = "x" * 2000
        result = AuditLogger._sanitize_input({"data": long_val})
        assert result["data"].endswith("[2000 chars]")
        assert len(result["data"]) < 300


# ── AuditStorage tests ───────────────────────────────────────────────────────


class TestAuditStorage:
    def test_save_and_retrieve(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        event = logger.log_auth_success(user_id="u1", ip="127.0.0.1")

        events = storage.get_events(limit=10)
        assert len(events) == 1
        assert events[0]["event_id"] == event.event_id
        assert events[0]["user_id"] == "u1"

    def test_get_last_event(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        logger.log_auth_success(user_id="first")
        logger.log_auth_success(user_id="second")

        last = storage.get_last_event()
        assert last["user_id"] == "second"

    def test_get_last_event_empty_db(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        assert storage.get_last_event() is None

    def test_verify_chain_valid(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        for i in range(5):
            logger.log_auth_success(user_id=f"u{i}")

        result = storage.verify_chain(limit=10)
        assert result["valid"] is True
        assert result["checked"] == 5
        assert result["errors"] == []

    def test_verify_chain_detects_tamper(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        for i in range(3):
            logger.log_auth_success(user_id=f"u{i}")

        # Tamper with the second event's hash
        with sqlite3.connect(str(tmp_path / "audit.db")) as conn:
            conn.execute(
                "UPDATE audit_events SET event_hash = 'tampered' "
                "WHERE rowid = 2"
            )

        result = storage.verify_chain(limit=10)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_get_events_filter_by_type(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        logger.log_auth_success(user_id="u1")
        logger.log_auth_failure(ip="10.0.0.1")
        logger.log_auth_success(user_id="u2")

        successes = storage.get_events(event_type="auth_success")
        assert len(successes) == 2
        failures = storage.get_events(event_type="auth_failure")
        assert len(failures) == 1

    def test_get_events_filter_by_user(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        logger.log_auth_success(user_id="alice")
        logger.log_auth_success(user_id="bob")
        logger.log_config_changed("model", user_id="alice")

        alice_events = storage.get_events(user_id="alice")
        assert len(alice_events) == 2
        bob_events = storage.get_events(user_id="bob")
        assert len(bob_events) == 1

    def test_cleanup_old_events(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db", retention_days=30)

        # Insert an old event directly
        old_time = time.time() - (31 * 86400)
        with sqlite3.connect(str(tmp_path / "audit.db")) as conn:
            conn.execute(
                "INSERT INTO audit_events (event_id, event_type, timestamp) "
                "VALUES (?, ?, ?)",
                ("old-1", "auth_success", old_time),
            )

        # Insert a recent event via logger
        logger = AuditLogger(storage=storage)
        logger.log_auth_success(user_id="recent")

        deleted = storage.cleanup_old_events()
        assert deleted == 1
        remaining = storage.get_events(limit=100)
        assert len(remaining) == 1
        assert remaining[0]["user_id"] == "recent"

    def test_get_stats(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        logger.log_auth_success(user_id="u1")
        logger.log_auth_success(user_id="u1")
        logger.log_auth_failure(ip="10.0.0.1")
        logger.log_tool_executed("bash", {"cmd": "ls"}, "green", user_id="u1")

        stats = storage.get_stats(days=1)
        assert stats["total_events"] == 4
        assert stats["by_type"]["auth_success"] == 2
        assert stats["by_type"]["auth_failure"] == 1
        assert stats["by_type"]["tool_executed"] == 1

    def test_export_json(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        logger.log_auth_success(user_id="u1")

        exported = storage.export_events(format="json")
        data = json.loads(exported)
        assert len(data) == 1
        assert data[0]["user_id"] == "u1"

    def test_export_csv(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger = AuditLogger(storage=storage)
        logger.log_auth_success(user_id="u1")
        logger.log_auth_failure(ip="10.0.0.1")

        exported = storage.export_events(format="csv")
        lines = exported.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "event_id" in lines[0]

    def test_set_storage_resumes_chain(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        logger1 = AuditLogger(storage=storage)
        e1 = logger1.log_auth_success(user_id="u1")

        # New logger picks up where the old one left off
        logger2 = AuditLogger()
        logger2.set_storage(storage)
        e2 = logger2.log_auth_success(user_id="u2")

        assert e2.prev_hash == e1.event_hash

        result = storage.verify_chain(limit=10)
        assert result["valid"] is True

    def test_verify_chain_empty(self, tmp_path):
        storage = AuditStorage(db_path=tmp_path / "audit.db")
        result = storage.verify_chain()
        assert result["valid"] is True
        assert result["checked"] == 0
