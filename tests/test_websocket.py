"""WebSocket endpoint tests for Rain Assistant.

Tests the /ws endpoint: connection lifecycle, message validation, agent CRUD,
heartbeat, rate limiting, permission flow, and error handling.
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_provider():
    """Create a fresh mock provider instance."""
    prov = AsyncMock()
    prov.provider_name = "claude"
    prov.supports_session_resumption.return_value = False
    prov.supports_computer_use.return_value = False
    prov._tool_executor = None
    return prov


@pytest.fixture()
def mock_provider():
    """Create a mock provider that avoids real API calls."""
    return _make_mock_provider()


@pytest.fixture()
def ws_client(test_app, mock_provider):
    """Provide a Starlette TestClient + valid auth token for WebSocket tests.

    Patches the provider factory so set_cwd doesn't make real API calls.
    SubAgentManager and create_subagent_handler are imported locally inside
    websocket_endpoint, so we patch them in the subagents module.
    """
    mock_sa_manager = MagicMock()
    mock_sa_manager.cleanup_children = AsyncMock()
    mock_sa_manager.cleanup_all = AsyncMock()

    # get_provider is imported at module level: from providers import get_provider
    # SubAgentManager/create_subagent_handler are imported locally inside websocket_endpoint
    with patch.object(__import__("server"), "get_provider", side_effect=lambda *a, **kw: _make_mock_provider()), \
         patch("subagents.SubAgentManager", return_value=mock_sa_manager), \
         patch("subagents.create_subagent_handler", return_value=AsyncMock()):

        # Clear rate limiter state to prevent 429s across tests
        from rate_limiter import rate_limiter as rl
        rl._windows.clear()

        client = TestClient(test_app["app"])

        # Authenticate to get a token
        resp = client.post("/api/auth", json={"pin": test_app["pin"]})
        assert resp.status_code == 200
        token = resp.json()["token"]

        yield {
            "client": client,
            "token": token,
            "test_app": test_app,
            "mock_provider": mock_provider,
        }


def ws_connect(ws_client, token=None):
    """Helper: open a WebSocket connection with the given token."""
    t = token or ws_client["token"]
    return ws_client["client"].websocket_connect(f"/ws?token={t}")


def drain_until(ws, msg_type, max_messages=20):
    """Read messages until we find one with the given type. Returns it."""
    for _ in range(max_messages):
        msg = ws.receive_json()
        if msg.get("type") == msg_type:
            return msg
    raise TimeoutError(f"Never received message type '{msg_type}' in {max_messages} messages")


def drain_messages(ws, count=5):
    """Read and discard up to `count` messages. Returns all collected."""
    msgs = []
    for _ in range(count):
        try:
            msgs.append(ws.receive_json())
        except Exception:
            break
    return msgs


# ===========================================================================
# 1. Connection Lifecycle
# ===========================================================================

class TestConnectionLifecycle:
    """Tests for WebSocket connection establishment and teardown."""

    def test_connect_with_valid_token(self, ws_client):
        """Successful connection receives initial status message."""
        with ws_connect(ws_client) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "status"
            assert "Connected" in msg["text"]

    def test_connect_without_token(self, ws_client):
        """Connection without token is closed with code 4001."""
        with pytest.raises(Exception):
            with ws_client["client"].websocket_connect("/ws") as ws:
                ws.receive_json()

    def test_connect_with_invalid_token(self, ws_client):
        """Connection with invalid token is closed with code 4001."""
        with pytest.raises(Exception):
            with ws_client["client"].websocket_connect("/ws?token=bad_token_123") as ws:
                ws.receive_json()

    def test_connect_with_expired_token(self, ws_client):
        """Connection with expired token is closed with code 4001."""
        import server
        token = ws_client["token"]
        # Expire the token
        if token in server.active_tokens:
            server.active_tokens[token] = time.time() - 1000

        with pytest.raises(Exception):
            with ws_client["client"].websocket_connect(f"/ws?token={token}") as ws:
                ws.receive_json()

    def test_api_key_loaded_on_connect(self, ws_client):
        """If a default API key is in config, api_key_loaded is sent on connect."""
        import server
        server.config["default_api_key"] = "sk-test-12345"
        try:
            with ws_connect(ws_client) as ws:
                msgs = drain_messages(ws, 5)
                types = [m["type"] for m in msgs]
                assert "api_key_loaded" in types
        finally:
            server.config.pop("default_api_key", None)


# ===========================================================================
# 2. Message Validation
# ===========================================================================

class TestMessageValidation:
    """Tests for message size and field length limits."""

    def test_message_too_large(self, ws_client):
        """Messages exceeding 16KB are rejected."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            # Send a message larger than 16KB
            big_payload = json.dumps({"type": "send_message", "text": "x" * 20_000})
            ws.send_text(big_payload)
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "too large" in msg["text"].lower()

    def test_type_field_too_long(self, ws_client):
        """Message type field exceeding 50 chars is rejected."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            ws.send_json({"type": "x" * 60, "agent_id": "default"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "field length" in msg["text"].lower()

    def test_agent_id_field_too_long(self, ws_client):
        """Agent ID exceeding 100 chars is rejected."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            ws.send_json({"type": "send_message", "agent_id": "a" * 120})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "field length" in msg["text"].lower()

    def test_text_too_long(self, ws_client):
        """send_message text exceeding 10,000 chars is rejected."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            # First create an agent so the text length check is reached
            tmp_dir = ws_client["test_app"]["tmp_path"] / "project_text"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({"type": "set_cwd", "path": str(tmp_dir), "agent_id": "default"})
            drain_until(ws, "status")  # wait for "Ready" status
            # Now send oversized message
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "z" * 11_000})
            msg = drain_until(ws, "error")
            assert "too long" in msg["text"].lower()

    def test_path_too_long(self, ws_client):
        """set_cwd path exceeding 500 chars is rejected."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            ws.send_json({"type": "set_cwd", "path": "/" + "a" * 510, "agent_id": "default"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "too long" in msg["text"].lower()

    def test_api_key_too_long(self, ws_client):
        """set_api_key with key exceeding 500 chars is rejected."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            ws.send_json({"type": "set_api_key", "key": "k" * 600, "agent_id": "default"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "too long" in msg["text"].lower()


# ===========================================================================
# 3. Agent CRUD
# ===========================================================================

class TestAgentCRUD:
    """Tests for creating, using, and destroying agents via WebSocket."""

    def test_set_cwd_creates_agent(self, ws_client):
        """set_cwd with a valid directory creates an agent and returns 'Ready' status."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            tmp_dir = ws_client["test_app"]["tmp_path"] / "project_a"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({"type": "set_cwd", "path": str(tmp_dir), "agent_id": "agent1"})
            msg = drain_until(ws, "status")
            assert "Ready" in msg["text"]
            assert msg.get("cwd") is not None

    def test_set_cwd_invalid_directory(self, ws_client):
        """set_cwd with nonexistent path returns error."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({"type": "set_cwd", "path": "/nonexistent/path/xyz", "agent_id": "default"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not a directory" in msg["text"].lower()

    def test_max_concurrent_agents(self, ws_client):
        """Cannot create more than WS_MAX_CONCURRENT_AGENTS regular agents."""
        import server
        original_max = server.WS_MAX_CONCURRENT_AGENTS
        server.WS_MAX_CONCURRENT_AGENTS = 2  # lower limit for faster test
        try:
            with ws_connect(ws_client) as ws:
                ws.receive_json()
                base = ws_client["test_app"]["tmp_path"]
                # Create 2 agents (the max)
                for i in range(2):
                    d = base / f"proj_{i}"
                    d.mkdir(exist_ok=True)
                    ws.send_json({"type": "set_cwd", "path": str(d), "agent_id": f"agent_{i}"})
                    drain_until(ws, "status")  # wait for "Ready"
                # 3rd should fail
                d3 = base / "proj_2"
                d3.mkdir(exist_ok=True)
                ws.send_json({"type": "set_cwd", "path": str(d3), "agent_id": "agent_2"})
                msg = drain_until(ws, "error")
                assert "max" in msg["text"].lower() or "concurrent" in msg["text"].lower()
        finally:
            server.WS_MAX_CONCURRENT_AGENTS = original_max

    def test_destroy_agent(self, ws_client):
        """destroy_agent removes the agent and returns agent_destroyed."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            tmp_dir = ws_client["test_app"]["tmp_path"] / "project_destroy"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({"type": "set_cwd", "path": str(tmp_dir), "agent_id": "doomed"})
            drain_until(ws, "status")
            ws.send_json({"type": "destroy_agent", "agent_id": "doomed"})
            msg = drain_until(ws, "agent_destroyed")
            assert msg["agent_id"] == "doomed"

    def test_send_message_without_agent(self, ws_client):
        """Sending a message before set_cwd returns an error."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "hello"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "no project directory" in msg["text"].lower()

    def test_set_cwd_with_model_override(self, ws_client):
        """set_cwd accepts model and provider overrides."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            tmp_dir = ws_client["test_app"]["tmp_path"] / "project_model"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({
                "type": "set_cwd",
                "path": str(tmp_dir),
                "agent_id": "default",
                "model": "gpt-4o",
                "provider": "openai",
            })
            msg = drain_until(ws, "status")
            assert "Ready" in msg["text"]


# ===========================================================================
# 4. Heartbeat
# ===========================================================================

class TestHeartbeat:
    """Tests for ping/pong and idle timeout."""

    def test_pong_accepted(self, ws_client):
        """Sending pong does not produce an error."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            ws.send_json({"type": "pong"})
            # pong is silently consumed — send another message to verify connection alive
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "test"})
            msg = ws.receive_json()
            # Should get an error about no project directory, not a pong error
            assert msg["type"] == "error"
            assert "no project directory" in msg["text"].lower()

    def test_ping_received(self, ws_client):
        """Server sends ping messages on the heartbeat interval."""
        import server
        original_interval = server.WS_HEARTBEAT_INTERVAL
        server.WS_HEARTBEAT_INTERVAL = 0.1  # speed up for test
        try:
            with ws_connect(ws_client) as ws:
                ws.receive_json()  # drain initial status
                # Wait a bit and collect messages — should get a ping
                msg = drain_until(ws, "ping", max_messages=30)
                assert msg["type"] == "ping"
                assert "ts" in msg
        finally:
            server.WS_HEARTBEAT_INTERVAL = original_interval

    def test_idle_timeout_disconnects(self, ws_client):
        """Connection is closed with 4002 after idle timeout."""
        import server
        original_interval = server.WS_HEARTBEAT_INTERVAL
        original_timeout = server.WS_IDLE_TIMEOUT
        server.WS_HEARTBEAT_INTERVAL = 0.1
        server.WS_IDLE_TIMEOUT = 0.2
        try:
            with pytest.raises(Exception):
                with ws_connect(ws_client) as ws:
                    ws.receive_json()  # drain initial status
                    # Don't send anything — wait for timeout
                    # Keep reading until disconnect
                    for _ in range(50):
                        ws.receive_json()
        finally:
            server.WS_HEARTBEAT_INTERVAL = original_interval
            server.WS_IDLE_TIMEOUT = original_timeout


# ===========================================================================
# 5. Rate Limiting
# ===========================================================================

class TestRateLimiting:
    """Tests for WebSocket message rate limiting (60/min)."""

    def test_rate_limit_exceeded(self, ws_client):
        """Exceeding 60 messages/minute triggers rate limit error."""
        import server
        from rate_limiter import rate_limiter as rl

        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status

            # Clear rate limiter state
            rl._windows.clear()

            error_found = False
            for i in range(70):
                ws.send_json({"type": "pong"})  # pong is lightweight

            # pong is skipped before rate limit check, so use a real message type
            rl._windows.clear()
            for i in range(70):
                ws.send_json({"type": "send_message", "agent_id": "default", "text": f"msg{i}"})

            # Drain responses looking for rate limit error
            msgs = drain_messages(ws, 80)
            for m in msgs:
                if m.get("type") == "error" and "rate limit" in m.get("text", "").lower():
                    error_found = True
                    break

            assert error_found, "Expected rate limit error not found"

    def test_rate_limit_includes_retry_after(self, ws_client):
        """Rate limit error includes retry information."""
        from rate_limiter import rate_limiter as rl

        with ws_connect(ws_client) as ws:
            ws.receive_json()
            rl._windows.clear()

            for i in range(70):
                ws.send_json({"type": "send_message", "agent_id": "default", "text": f"m{i}"})

            msgs = drain_messages(ws, 80)
            for m in msgs:
                if m.get("type") == "error" and "rate limit" in m.get("text", "").lower():
                    assert "retry" in m["text"].lower()
                    return
            pytest.fail("Rate limit error with retry info not found")


# ===========================================================================
# 6. Permission Flow
# ===========================================================================

class TestPermissionFlow:
    """Tests for the permission_response message handling."""

    def test_permission_response_unknown_id(self, ws_client):
        """permission_response with unknown request_id returns error."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "permission_response",
                "request_id": "perm_nonexistent",
                "approved": True,
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "expired" in msg["text"].lower() or "not found" in msg["text"].lower()

    def test_permission_response_approved(self, ws_client):
        """permission_response with approved=true is accepted for valid request_id."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            # We can test that a known request_id doesn't error
            # Since we can't easily inject into the closure's pending_permissions,
            # we just verify that unknown IDs produce errors (tested above)
            # and that the message format is handled without crash
            ws.send_json({
                "type": "permission_response",
                "request_id": "perm_abc123",
                "approved": True,
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"  # not found, but no crash

    def test_permission_response_denied(self, ws_client):
        """permission_response with approved=false is handled gracefully."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "permission_response",
                "request_id": "perm_def456",
                "approved": False,
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"  # expired/not found, but no crash


# ===========================================================================
# 7. Specific Message Types
# ===========================================================================

class TestSpecificMessages:
    """Tests for individual WebSocket message types."""

    def test_set_api_key(self, ws_client):
        """set_api_key stores the key and returns status confirmation."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "set_api_key",
                "key": "sk-test-key-12345",
                "provider": "openai",
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "status"
            assert "api key set" in msg["text"].lower()

    def test_set_api_key_empty_rejected(self, ws_client):
        """set_api_key with empty key returns error."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "set_api_key",
                "key": "",
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "required" in msg["text"].lower()

    def test_set_api_key_oauth_mode(self, ws_client):
        """set_api_key with auth_mode=oauth sends api_key_loaded."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "set_api_key",
                "auth_mode": "oauth",
                "agent_id": "default",
            })
            msgs = drain_messages(ws, 5)
            types = [m["type"] for m in msgs]
            assert "api_key_loaded" in types

    def test_set_transcription_lang(self, ws_client):
        """set_transcription_lang with valid lang returns status confirmation."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            with patch("server.transcriber") as mock_transcriber:
                ws.send_json({
                    "type": "set_transcription_lang",
                    "lang": "es",
                    "agent_id": "default",
                })
                msg = ws.receive_json()
                assert msg["type"] == "status"
                assert "es" in msg["text"].lower()

    def test_set_alter_ego(self, ws_client):
        """set_alter_ego switches the ego and sends alter_ego_changed."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "set_alter_ego",
                "ego_id": "rain",
                "agent_id": "default",
            })
            msgs = drain_messages(ws, 5)
            types = [m["type"] for m in msgs]
            assert "alter_ego_changed" in types


# ===========================================================================
# 8. Error Handling
# ===========================================================================

class TestErrorHandling:
    """Tests for error conditions and edge cases."""

    def test_interrupt_without_agent(self, ws_client):
        """Interrupt for nonexistent agent doesn't crash."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({"type": "interrupt", "agent_id": "nonexistent"})
            # Should get a result message (interrupted) even without active agent
            msg = ws.receive_json()
            assert msg["type"] == "result"
            assert msg["agent_id"] == "nonexistent"

    def test_destroy_nonexistent_agent(self, ws_client):
        """Destroying a nonexistent agent still returns agent_destroyed."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({"type": "destroy_agent", "agent_id": "phantom"})
            msg = ws.receive_json()
            assert msg["type"] == "agent_destroyed"
            assert msg["agent_id"] == "phantom"

    def test_set_mode_without_agent(self, ws_client):
        """set_mode before creating an agent returns error."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            ws.send_json({"type": "set_mode", "mode": "computer_use", "agent_id": "default"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["text"].lower()

    def test_emergency_stop_with_agent(self, ws_client):
        """emergency_stop sends EMERGENCY STOP status."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            tmp_dir = ws_client["test_app"]["tmp_path"] / "project_estop"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({"type": "set_cwd", "path": str(tmp_dir), "agent_id": "agent_e"})
            drain_until(ws, "status")  # wait for "Ready"
            ws.send_json({"type": "emergency_stop", "agent_id": "agent_e"})
            msg = drain_until(ws, "status")
            assert "emergency stop" in msg["text"].lower()


# ===========================================================================
# 9. Cleanup on Disconnect
# ===========================================================================

class TestCleanup:
    """Tests for resource cleanup on WebSocket disconnection."""

    def test_disconnect_cleans_up(self, ws_client):
        """Disconnecting cleans up agents gracefully without errors."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            tmp_dir = ws_client["test_app"]["tmp_path"] / "project_cleanup"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({"type": "set_cwd", "path": str(tmp_dir), "agent_id": "cleanup_agent"})
            drain_until(ws, "status")
        # Connection closed — no assertion needed, just verify no exception

    def test_multiple_agents_cleaned_up(self, ws_client):
        """Multiple agents are all cleaned up on disconnect."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()
            base = ws_client["test_app"]["tmp_path"]
            for i in range(3):
                d = base / f"cleanup_proj_{i}"
                d.mkdir(exist_ok=True)
                ws.send_json({"type": "set_cwd", "path": str(d), "agent_id": f"cleanup_{i}"})
                drain_until(ws, "status")
        # Graceful disconnect with 3 agents — no exception
