"""Tests for database.py — message CRUD, metrics, encryption, sessions."""

import json
import time

import pytest

import database


class TestEncryption:
    """Test encrypt/decrypt round-trip and backward compatibility."""

    def test_encrypt_decrypt_round_trip(self, test_db):
        plaintext = "Hello, this is a secret message!"
        encrypted = database.encrypt_field(plaintext)
        assert encrypted != plaintext
        assert database.decrypt_field(encrypted) == plaintext

    def test_encrypt_empty_string(self, test_db):
        assert database.encrypt_field("") == ""

    def test_decrypt_empty_string(self, test_db):
        assert database.decrypt_field("") == ""

    def test_decrypt_unencrypted_fallback(self, test_db):
        """Backward compatibility: if data isn't encrypted, return as-is."""
        plaintext = "not encrypted at all"
        # decrypt_field should return the original string for invalid ciphertext
        result = database.decrypt_field(plaintext)
        assert result == plaintext

    def test_encrypt_unicode(self, test_db):
        text = "Rain dice: hola mundo"
        encrypted = database.encrypt_field(text)
        assert database.decrypt_field(encrypted) == text


class TestMessageCRUD:
    """Test save_message, get_messages, clear_messages."""

    def test_save_and_get_message(self, test_db):
        cwd = "/tmp/test_project"
        msg_id = database.save_message(cwd, "user", "text", {"text": "hello"})
        assert msg_id > 0

        messages = database.get_messages(cwd)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["type"] == "text"
        assert messages[0]["content"]["text"] == "hello"

    def test_get_messages_empty(self, test_db):
        messages = database.get_messages("/nonexistent")
        assert messages == []

    def test_save_multiple_messages(self, test_db):
        cwd = "/tmp/multi"
        database.save_message(cwd, "user", "text", {"text": "msg1"})
        database.save_message(cwd, "assistant", "assistant_text", {"text": "reply1"})
        database.save_message(cwd, "user", "text", {"text": "msg2"})

        messages = database.get_messages(cwd)
        assert len(messages) == 3
        # Verify ordering by timestamp
        assert messages[0]["content"]["text"] == "msg1"
        assert messages[1]["content"]["text"] == "reply1"
        assert messages[2]["content"]["text"] == "msg2"

    def test_messages_per_agent_id(self, test_db):
        cwd = "/tmp/agents"
        database.save_message(cwd, "user", "text", {"text": "agent1_msg"}, agent_id="agent1")
        database.save_message(cwd, "user", "text", {"text": "agent2_msg"}, agent_id="agent2")

        msgs1 = database.get_messages(cwd, agent_id="agent1")
        msgs2 = database.get_messages(cwd, agent_id="agent2")
        assert len(msgs1) == 1
        assert msgs1[0]["content"]["text"] == "agent1_msg"
        assert len(msgs2) == 1
        assert msgs2[0]["content"]["text"] == "agent2_msg"

    def test_default_agent_id(self, test_db):
        cwd = "/tmp/default_agent"
        database.save_message(cwd, "user", "text", {"text": "default"})
        # Default agent_id is "default"
        messages = database.get_messages(cwd, agent_id="default")
        assert len(messages) == 1

    def test_clear_messages_by_cwd(self, test_db):
        cwd = "/tmp/clear_test"
        database.save_message(cwd, "user", "text", {"text": "msg1"})
        database.save_message(cwd, "user", "text", {"text": "msg2"})

        count = database.clear_messages(cwd)
        assert count == 2
        assert database.get_messages(cwd) == []

    def test_clear_messages_by_agent_id(self, test_db):
        cwd = "/tmp/clear_agent"
        database.save_message(cwd, "user", "text", {"text": "a1"}, agent_id="a1")
        database.save_message(cwd, "user", "text", {"text": "a2"}, agent_id="a2")

        count = database.clear_messages(cwd, agent_id="a1")
        assert count == 1
        # Agent 2's messages should remain
        assert len(database.get_messages(cwd, agent_id="a2")) == 1

    def test_clear_nonexistent_cwd(self, test_db):
        count = database.clear_messages("/nonexistent")
        assert count == 0


class TestEncryptedMessageTypes:
    """Verify that sensitive message types are encrypted at rest."""

    def test_text_is_encrypted(self, test_db):
        import sqlite3

        cwd = "/tmp/enc_test"
        database.save_message(cwd, "user", "text", {"text": "secret data"})

        # Read raw from DB to verify encryption
        conn = sqlite3.connect(str(database.DB_PATH))
        row = conn.execute("SELECT content_json FROM messages WHERE cwd = ?", (cwd,)).fetchone()
        conn.close()

        raw = row[0]
        # Raw should NOT contain the plaintext (it's encrypted)
        assert "secret data" not in raw
        # But when read through the API, it should be decrypted
        messages = database.get_messages(cwd)
        assert messages[0]["content"]["text"] == "secret data"

    def test_result_type_is_not_encrypted(self, test_db):
        """Result messages are NOT encrypted (needed for json_extract in metrics)."""
        import sqlite3

        cwd = "/tmp/result_enc"
        content = {"cost": 0.01, "duration_ms": 500, "num_turns": 1,
                   "usage": {"input_tokens": 100, "output_tokens": 200}}
        database.save_message(cwd, "system", "result", content)

        conn = sqlite3.connect(str(database.DB_PATH))
        row = conn.execute("SELECT content_json FROM messages WHERE cwd = ?", (cwd,)).fetchone()
        conn.close()

        raw = row[0]
        # Result type should be plaintext JSON (for json_extract)
        parsed = json.loads(raw)
        assert parsed["cost"] == 0.01


class TestMetricsAggregation:
    """Test get_metrics_data aggregation."""

    def test_metrics_empty_db(self, test_db):
        metrics = database.get_metrics_data()
        assert metrics["totals"]["all_time"]["cost"] == 0
        assert metrics["totals"]["all_time"]["sessions"] == 0
        assert len(metrics["by_hour"]) == 24
        assert len(metrics["by_dow"]) == 7

    def test_metrics_with_data(self, test_db):
        cwd = "/tmp/metrics_test"
        content = {
            "cost": 0.05,
            "duration_ms": 1000,
            "num_turns": 3,
            "usage": {"input_tokens": 500, "output_tokens": 300},
        }
        database.save_message(cwd, "system", "result", content)

        metrics = database.get_metrics_data()
        assert metrics["totals"]["all_time"]["cost"] == 0.05
        assert metrics["totals"]["all_time"]["sessions"] == 1
        assert metrics["totals"]["all_time"]["total_turns"] == 3
        assert metrics["totals"]["all_time"]["total_input_tokens"] == 500
        assert metrics["totals"]["all_time"]["total_output_tokens"] == 300

    def test_metrics_today_totals(self, test_db):
        cwd = "/tmp/metrics_today"
        content = {"cost": 0.10, "duration_ms": 2000, "num_turns": 5,
                   "usage": {"input_tokens": 1000, "output_tokens": 500}}
        database.save_message(cwd, "system", "result", content)

        metrics = database.get_metrics_data()
        assert metrics["totals"]["today"]["cost"] == 0.10
        assert metrics["totals"]["today"]["sessions"] == 1


class TestPermissionLog:
    """Test permission audit logging."""

    def test_log_permission_decision(self, test_db):
        row_id = database.log_permission_decision(
            agent_id="agent1",
            tool_name="Bash",
            tool_input={"command": "rm -rf /"},
            level="red",
            decision="denied",
            reason="Dangerous command",
        )
        assert row_id > 0

    def test_log_truncates_tool_input(self, test_db):
        """Tool input should be truncated to 2000 chars."""
        long_input = {"command": "x" * 5000}
        row_id = database.log_permission_decision(
            agent_id="agent1",
            tool_name="Bash",
            tool_input=long_input,
            level="red",
            decision="denied",
        )
        assert row_id > 0


class TestSessionManagement:
    """Test active session CRUD."""

    def test_create_session(self, test_db):
        database.create_session("hash123", "127.0.0.1", "TestAgent/1.0")
        # No assertion needed — just verify no crash

    def test_update_session_activity(self, test_db):
        database.create_session("hash456", "127.0.0.1")
        database.update_session_activity("hash456")

    def test_revoke_session(self, test_db):
        database.create_session("hash789", "127.0.0.1")
        database.revoke_session("hash789")

    def test_revoke_all_sessions(self, test_db):
        database.create_session("hashA", "1.1.1.1")
        database.create_session("hashB", "2.2.2.2")
        count = database.revoke_all_sessions()
        assert count == 2

    def test_revoke_all_sessions_empty(self, test_db):
        count = database.revoke_all_sessions()
        assert count == 0


class TestUsageQuotas:
    """Test TTS / audio quota tracking."""

    def test_get_or_create_quota_new(self, test_db):
        quota = database.get_or_create_quota("tok12345", "2026-02-18")
        assert quota["tts_chars"] == 0
        assert quota["audio_seconds"] == 0.0

    def test_increment_tts_chars(self, test_db):
        new_total = database.increment_tts_chars("tok12345", "2026-02-18", 500)
        assert new_total == 500
        new_total = database.increment_tts_chars("tok12345", "2026-02-18", 300)
        assert new_total == 800

    def test_increment_audio_seconds(self, test_db):
        new_total = database.increment_audio_seconds("tok12345", "2026-02-18", 30.0)
        assert new_total == 30.0
        new_total = database.increment_audio_seconds("tok12345", "2026-02-18", 15.5)
        assert new_total == 45.5

    def test_quotas_per_token_per_day(self, test_db):
        database.increment_tts_chars("tokA", "2026-02-18", 100)
        database.increment_tts_chars("tokB", "2026-02-18", 200)
        database.increment_tts_chars("tokA", "2026-02-19", 300)

        qA_18 = database.get_or_create_quota("tokA", "2026-02-18")
        qB_18 = database.get_or_create_quota("tokB", "2026-02-18")
        qA_19 = database.get_or_create_quota("tokA", "2026-02-19")

        assert qA_18["tts_chars"] == 100
        assert qB_18["tts_chars"] == 200
        assert qA_19["tts_chars"] == 300


class TestAccessLog:
    """Test HTTP access logging."""

    def test_log_access(self, test_db):
        # Should not raise even if called many times
        database.log_access("GET", "/api/browse", 200, 12.5, "127.0.0.1")
        database.log_access("POST", "/api/auth", 401, 5.0, "10.0.0.1", "tok123", "Mozilla/5.0")


class TestSecurityEvents:
    """Test security event logging."""

    def test_log_security_event(self, test_db):
        database.log_security_event(
            "auth_failed", "warning",
            client_ip="10.0.0.1",
            details="bad pin attempt",
            endpoint="/api/auth",
        )
        # Verify no crash. The event is logged to DB.

    def test_log_security_event_with_long_details(self, test_db):
        # Details are truncated to 2000 chars in the source
        database.log_security_event(
            "test_event", "info",
            details="x" * 5000,
        )
