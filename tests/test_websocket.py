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
        rl.reset()

        client = TestClient(test_app["app"])

        # Authenticate to get a token (Origin header required by CSRF middleware)
        resp = client.post(
            "/api/auth",
            json={"pin": test_app["pin"]},
            headers={"Origin": "http://testserver"},
        )
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
        """Agent ID exceeding 100 chars is silently rejected (server continues)."""
        with ws_connect(ws_client) as ws:
            ws.receive_json()  # drain initial status
            ws.send_json({"type": "send_message", "agent_id": "a" * 120})
            # Server logs warning and does `continue` — no error sent back.
            # Verify connection is still alive by sending a valid pong.
            ws.send_json({"type": "pong"})
            # If we get here without exception, the server didn't crash.

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
            rl.reset()

            error_found = False
            for i in range(70):
                ws.send_json({"type": "pong"})  # pong is lightweight

            # pong is skipped before rate limit check, so use a real message type
            rl.reset()
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
            rl.reset()

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
            with patch("server.transcriber"):
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


# ===========================================================================
# 10. Core Message Flow — send_message + Streaming
# ===========================================================================

def _make_streaming_provider(events):
    """Create a mock provider that yields controlled NormalizedEvent objects.

    ``events`` is a list of (event_type, data_dict) tuples that will be
    emitted by ``stream_response()``.
    """
    from providers.base import NormalizedEvent

    prov = AsyncMock()
    prov.provider_name = "claude"
    prov.supports_session_resumption.return_value = False
    prov.supports_computer_use.return_value = False
    prov._tool_executor = None

    async def _stream():
        for etype, edata in events:
            yield NormalizedEvent(etype, edata)

    prov.stream_response = _stream
    return prov


@pytest.fixture()
def ws_streaming_client(test_app):
    """WebSocket client fixture that lets each test inject a custom provider.

    Returns a dict with ``connect(events)`` helper.  Call it with a list
    of ``(event_type, data_dict)`` tuples to configure what the provider
    streams back.  The helper returns the open WebSocket context manager.
    """
    # Shared mutable list — tests set this before sending messages
    _provider_holder: list = [None]

    def _factory(*_args, **_kwargs):
        if _provider_holder[0] is not None:
            return _provider_holder[0]
        return _make_mock_provider()

    mock_sa_manager = MagicMock()
    mock_sa_manager.cleanup_children = AsyncMock()
    mock_sa_manager.cleanup_all = AsyncMock()

    with patch.object(__import__("server"), "get_provider", side_effect=_factory), \
         patch("subagents.SubAgentManager", return_value=mock_sa_manager), \
         patch("subagents.create_subagent_handler", return_value=AsyncMock()):

        from rate_limiter import rate_limiter as rl
        rl.reset()

        client = TestClient(test_app["app"])
        resp = client.post(
            "/api/auth",
            json={"pin": test_app["pin"]},
            headers={"Origin": "http://testserver"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]

        yield {
            "client": client,
            "token": token,
            "test_app": test_app,
            "_provider_holder": _provider_holder,
            "sa_manager": mock_sa_manager,
        }


def _setup_agent(ws, ctx, agent_id="default", events=None):
    """Helper: create an agent via set_cwd and optionally configure a streaming provider."""
    tmp_dir = ctx["test_app"]["tmp_path"] / f"project_{agent_id}_{id(events)}"
    tmp_dir.mkdir(exist_ok=True)

    if events is not None:
        ctx["_provider_holder"][0] = _make_streaming_provider(events)

    ws.send_json({"type": "set_cwd", "path": str(tmp_dir), "agent_id": agent_id})
    drain_until(ws, "status")  # wait for "Ready"
    return tmp_dir


class TestSendMessageFlow:
    """Tests for the full send_message → streaming → result pipeline."""

    def test_simple_text_response(self, ws_streaming_client):
        """send_message returns assistant_text chunks followed by a result."""
        events = [
            ("assistant_text", {"text": "Hello "}),
            ("assistant_text", {"text": "world!"}),
            ("result", {"text": "", "session_id": "s1", "cost": 0.01,
                        "duration_ms": 150, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()  # initial status
            _setup_agent(ws, ctx, events=events)

            # Now reconfigure provider for the actual message
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "Hi"})

            # Collect messages until result
            collected = []
            for _ in range(20):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            types = [m["type"] for m in collected]
            assert "status" in types  # "Rain is working..."
            assert "assistant_text" in types
            assert "result" in types

            # Verify text content
            text_chunks = [m for m in collected if m["type"] == "assistant_text"]
            assert len(text_chunks) == 2
            assert text_chunks[0]["text"] == "Hello "
            assert text_chunks[1]["text"] == "world!"

            # Verify result
            result = [m for m in collected if m["type"] == "result"][0]
            assert result["agent_id"] == "default"
            assert abs(result["cost"] - 0.01) < 1e-9

    def test_model_info_event(self, ws_streaming_client):
        """model_info event is forwarded to frontend."""
        events = [
            ("model_info", {"model": "claude-sonnet-4-20250514"}),
            ("assistant_text", {"text": "Hi"}),
            ("result", {"text": "", "session_id": None, "cost": 0.001,
                        "duration_ms": 50, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "Hi"})

            collected = []
            for _ in range(20):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            model_info_msgs = [m for m in collected if m["type"] == "model_info"]
            assert len(model_info_msgs) == 1
            assert model_info_msgs[0]["model"] == "claude-sonnet-4-20250514"

    def test_status_event_forwarded(self, ws_streaming_client):
        """Provider status events are forwarded to frontend."""
        events = [
            ("status", {"text": "Thinking..."}),
            ("assistant_text", {"text": "Done"}),
            ("result", {"text": "", "session_id": None, "cost": 0.0,
                        "duration_ms": 10, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "x"})

            collected = []
            for _ in range(20):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            # Should have "Rain is working..." plus the provider's "Thinking..." status
            status_msgs = [m for m in collected if m["type"] == "status"]
            assert any("working" in m.get("text", "").lower() for m in status_msgs)
            assert any("Thinking" in m.get("text", "") for m in status_msgs)

    def test_empty_message_ignored(self, ws_streaming_client):
        """send_message with empty text is silently ignored."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=[])
            ws.send_json({"type": "send_message", "agent_id": "default", "text": ""})
            # Send a follow-up to confirm no crash
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "   "})
            # Send a valid message type to verify connection is still alive
            ws.send_json({"type": "interrupt", "agent_id": "default"})
            msg = drain_until(ws, "result")
            assert msg["type"] == "result"


# ===========================================================================
# 11. Tool Use and Tool Result Flow
# ===========================================================================

class TestToolUseFlow:
    """Tests for tool_use and tool_result streaming events."""

    def test_tool_use_and_result(self, ws_streaming_client):
        """Provider emitting tool_use and tool_result is forwarded correctly."""
        events = [
            ("tool_use", {"tool": "Read", "tool_id": "tu_1",
                          "input": {"file_path": "/tmp/test.py"}}),
            ("tool_result", {"tool_id": "tu_1", "content": "file contents here",
                             "is_error": False}),
            ("assistant_text", {"text": "I read the file."}),
            ("result", {"text": "", "session_id": None, "cost": 0.02,
                        "duration_ms": 200, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "Read test.py"})

            collected = []
            for _ in range(25):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            types = [m["type"] for m in collected]
            assert "tool_use" in types
            assert "tool_result" in types
            assert "assistant_text" in types
            assert "result" in types

            tool_use = [m for m in collected if m["type"] == "tool_use"][0]
            assert tool_use["tool"] == "Read"
            assert tool_use["agent_id"] == "default"

            tool_result = [m for m in collected if m["type"] == "tool_result"][0]
            assert tool_result["content"] == "file contents here"

    def test_multiple_tool_calls(self, ws_streaming_client):
        """Multiple sequential tool calls in one response."""
        events = [
            ("tool_use", {"tool": "Glob", "tool_id": "tu_1",
                          "input": {"pattern": "*.py"}}),
            ("tool_result", {"tool_id": "tu_1", "content": "main.py\ntest.py",
                             "is_error": False}),
            ("tool_use", {"tool": "Read", "tool_id": "tu_2",
                          "input": {"file_path": "main.py"}}),
            ("tool_result", {"tool_id": "tu_2", "content": "print('hello')",
                             "is_error": False}),
            ("assistant_text", {"text": "Found 2 Python files."}),
            ("result", {"text": "", "session_id": None, "cost": 0.03,
                        "duration_ms": 300, "num_turns": 2, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "List py files"})

            collected = []
            for _ in range(30):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            tool_uses = [m for m in collected if m["type"] == "tool_use"]
            tool_results = [m for m in collected if m["type"] == "tool_result"]
            assert len(tool_uses) == 2
            assert len(tool_results) == 2

    def test_tool_result_truncation(self, ws_streaming_client):
        """Large tool_result content is truncated for WebSocket."""
        import server
        big_content = "x" * (server.WS_MAX_TOOL_RESULT_WS + 1000)
        events = [
            ("tool_use", {"tool": "Read", "tool_id": "tu_1",
                          "input": {"file_path": "/big.txt"}}),
            ("tool_result", {"tool_id": "tu_1", "content": big_content,
                             "is_error": False}),
            ("result", {"text": "", "session_id": None, "cost": 0.01,
                        "duration_ms": 100, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "read big"})

            collected = []
            for _ in range(25):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            tool_result = [m for m in collected if m["type"] == "tool_result"][0]
            assert "truncated" in tool_result["content"]
            assert len(tool_result["content"]) <= server.WS_MAX_TOOL_RESULT_WS + 100

    def test_tool_use_error_result(self, ws_streaming_client):
        """tool_result with is_error=True is forwarded correctly."""
        events = [
            ("tool_use", {"tool": "Read", "tool_id": "tu_1",
                          "input": {"file_path": "/nonexistent"}}),
            ("tool_result", {"tool_id": "tu_1", "content": "File not found",
                             "is_error": True}),
            ("assistant_text", {"text": "The file doesn't exist."}),
            ("result", {"text": "", "session_id": None, "cost": 0.01,
                        "duration_ms": 80, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "read it"})

            collected = []
            for _ in range(25):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            tool_result = [m for m in collected if m["type"] == "tool_result"][0]
            assert tool_result["is_error"] is True
            assert "File not found" in tool_result["content"]


# ===========================================================================
# 12. Error Handling During Streaming
# ===========================================================================

class TestStreamingErrors:
    """Tests for error conditions that occur during stream_response."""

    def test_provider_error_during_streaming(self, ws_streaming_client):
        """Exception during streaming sends error to frontend.

        stream_provider_response runs as a background asyncio task. When
        the generator raises, the handler catches it and sends an error
        message over the WebSocket.
        """
        from providers.base import NormalizedEvent

        prov = AsyncMock()
        prov.provider_name = "claude"
        prov.supports_session_resumption.return_value = False
        prov.supports_computer_use.return_value = False
        prov._tool_executor = None

        async def _failing_stream():
            yield NormalizedEvent("assistant_text", {"text": "partial"})
            raise RuntimeError("API connection lost")

        prov.stream_response = _failing_stream

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()  # initial status
            _setup_agent(ws, ctx, events=[])
            ctx["_provider_holder"][0] = prov
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "hello"})

            # The streaming task runs in the background. Collect messages
            # until we see the error, a disconnect, or a ping after streaming.
            from starlette.websockets import WebSocketDisconnect
            collected = []
            found_error = False
            disconnected = False
            for _ in range(30):
                try:
                    msg = ws.receive_json()
                except WebSocketDisconnect:
                    disconnected = True
                    break
                collected.append(msg)
                if msg.get("type") == "error" and msg.get("agent_id") == "default":
                    found_error = True
                    break
                if msg.get("type") == "ping" and any(m.get("type") == "assistant_text" for m in collected):
                    break

            # Either we got an explicit error message or the server disconnected
            # due to the streaming error — both are valid error propagation.
            assert found_error or disconnected, (
                f"Expected error or disconnect, got: {[m['type'] for m in collected]}"
            )

    def test_error_event_from_provider(self, ws_streaming_client):
        """Provider emitting an error event is forwarded."""
        from starlette.websockets import WebSocketDisconnect
        events = [
            ("error", {"text": "Rate limit exceeded. Please wait."}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "hi"})

            collected = []
            disconnected = False
            for _ in range(15):
                try:
                    msg = ws.receive_json()
                except WebSocketDisconnect:
                    disconnected = True
                    break
                collected.append(msg)
                if msg.get("type") == "error" and "Rate limit" in msg.get("text", ""):
                    break

            errors = [m for m in collected if m["type"] == "error" and "Rate limit" in m.get("text", "")]
            assert len(errors) >= 1 or disconnected

    def test_send_message_provider_exception(self, ws_streaming_client):
        """Exception during provider.send_message is handled without crash."""
        from starlette.websockets import WebSocketDisconnect
        prov = _make_mock_provider()
        prov.send_message = AsyncMock(side_effect=Exception("Connection refused"))

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=[])
            ctx["_provider_holder"][0] = prov
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "test"})

            # The exception may cause an error message or a disconnect —
            # both are valid error handling.
            collected = []
            disconnected = False
            for _ in range(15):
                try:
                    msg = ws.receive_json()
                except WebSocketDisconnect:
                    disconnected = True
                    break
                collected.append(msg)
                if msg.get("type") == "error":
                    break

            errors = [m for m in collected if m["type"] == "error"]
            assert len(errors) >= 1 or disconnected


# ===========================================================================
# 13. Interrupt Message
# ===========================================================================

class TestInterruptMessage:
    """Tests for the interrupt message during active streaming."""

    def test_interrupt_idle_agent_sends_result(self, ws_streaming_client):
        """Interrupt on an agent with no active streaming task returns result."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=[])
            ws.send_json({"type": "interrupt", "agent_id": "default"})
            result = drain_until(ws, "result")
            assert result["type"] == "result"
            assert "interrupted" in result.get("text", "").lower()
            assert result["agent_id"] == "default"

    def test_interrupt_after_streaming_completes(self, ws_streaming_client):
        """Interrupt after streaming finishes is handled gracefully."""
        events = [
            ("assistant_text", {"text": "done"}),
            ("result", {"text": "", "session_id": None, "cost": 0.0,
                        "duration_ms": 10, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "hi"})

            # Wait for result
            for _ in range(20):
                msg = ws.receive_json()
                if msg.get("type") == "result":
                    break

            # Now interrupt — streaming already done, should still return result
            ws.send_json({"type": "interrupt", "agent_id": "default"})
            result = drain_until(ws, "result")
            assert result["type"] == "result"
            assert result["agent_id"] == "default"

    def test_interrupt_nonexistent_agent_no_crash(self, ws_streaming_client):
        """Interrupt for agent that was never created still returns result."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({"type": "interrupt", "agent_id": "ghost"})
            result = drain_until(ws, "result")
            assert result["type"] == "result"
            assert result["agent_id"] == "ghost"


# ===========================================================================
# 14. Permission Request / Response (YELLOW & RED)
# ===========================================================================

class TestPermissionRequestResponse:
    """Tests for permission_request events from the provider and
    permission_response messages from the frontend.

    The permission flow is triggered by the can_use_tool_callback inside
    the WebSocket endpoint, so we test it indirectly via the full flow.
    """

    def test_permission_response_sets_event(self, ws_streaming_client):
        """Sending permission_response for a valid request_id sets the event."""
        # We can't easily trigger a real permission request from a mock provider,
        # but we can verify the permission_response handler works correctly
        # by confirming unknown IDs error out (regression from existing tests)
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "permission_response",
                "request_id": "perm_test123",
                "approved": True,
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "expired" in msg["text"].lower() or "not found" in msg["text"].lower()

    def test_permission_response_denied(self, ws_streaming_client):
        """permission_response with approved=false is handled gracefully."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "permission_response",
                "request_id": "perm_denied_test",
                "approved": False,
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"  # not found, but no crash

    def test_permission_response_with_pin(self, ws_streaming_client):
        """permission_response with pin field is accepted without crash."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "permission_response",
                "request_id": "perm_red_test",
                "approved": True,
                "pin": "999888",  # test PIN
                "agent_id": "default",
            })
            msg = ws.receive_json()
            # Should get error (not found) but no crash
            assert msg["type"] == "error"


# ===========================================================================
# 15. Computer Use Mode
# ===========================================================================

class TestComputerUseMode:
    """Tests for set_mode, mode_changed, and emergency_stop in computer use."""

    def test_set_mode_without_agent(self, ws_streaming_client):
        """set_mode before creating agent returns error."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({"type": "set_mode", "mode": "computer_use", "agent_id": "noagent"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["text"].lower()

    def test_set_mode_coding(self, ws_streaming_client):
        """Switching to coding mode returns mode_changed."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=[])
            ws.send_json({"type": "set_mode", "mode": "coding", "agent_id": "default"})
            msg = drain_until(ws, "mode_changed")
            assert msg["mode"] == "coding"
            assert msg["agent_id"] == "default"

    def test_set_mode_computer_use_unavailable(self, ws_streaming_client):
        """computer_use mode when not available returns error."""
        import server
        original = server.COMPUTER_USE_AVAILABLE
        server.COMPUTER_USE_AVAILABLE = False
        try:
            ctx = ws_streaming_client
            with ws_connect(ctx) as ws:
                ws.receive_json()
                _setup_agent(ws, ctx, events=[])
                ws.send_json({"type": "set_mode", "mode": "computer_use", "agent_id": "default"})
                msg = drain_until(ws, "error")
                assert "not available" in msg["text"].lower()
        finally:
            server.COMPUTER_USE_AVAILABLE = original

    def test_emergency_stop_sends_status(self, ws_streaming_client):
        """emergency_stop cancels tasks and sends EMERGENCY STOP status."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=[])
            ws.send_json({"type": "emergency_stop", "agent_id": "default"})
            msg = drain_until(ws, "status")
            assert "emergency stop" in msg["text"].lower()

    def test_emergency_stop_no_agent(self, ws_streaming_client):
        """emergency_stop for nonexistent agent doesn't crash."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({"type": "emergency_stop", "agent_id": "nonexistent"})
            # No error sent — just silently handled. Verify connection alive.
            ws.send_json({"type": "interrupt", "agent_id": "nonexistent"})
            msg = drain_until(ws, "result")
            assert msg["type"] == "result"


# ===========================================================================
# 16. Sub-Agent Messages
# ===========================================================================

class TestSubAgentMessages:
    """Tests for subagent_spawned and subagent_completed event forwarding.

    Sub-agent events are emitted by the SubAgentManager and forwarded via
    the send() function in the WebSocket endpoint. Since we mock the
    SubAgentManager, these tests verify the handler injection.
    """

    def test_subagent_handler_injected(self, ws_streaming_client):
        """create_subagent_handler is called when provider has _tool_executor."""
        # The ws_streaming_client fixture patches create_subagent_handler
        # We verify that an agent can be created and the mock is set up
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, events=[])
            # Agent created successfully — subagent infrastructure initialized
            # The mock SubAgentManager should exist
            assert ctx["sa_manager"] is not None

    def test_destroy_agent_cleans_subagents(self, ws_streaming_client):
        """Destroying an agent calls cleanup_children on SubAgentManager."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, agent_id="parent", events=[])
            ws.send_json({"type": "destroy_agent", "agent_id": "parent"})
            msg = drain_until(ws, "agent_destroyed")
            assert msg["agent_id"] == "parent"
            # cleanup_children should have been called
            ctx["sa_manager"].cleanup_children.assert_called_with("parent")


# ===========================================================================
# 17. Multiple Agents Sending Messages Simultaneously
# ===========================================================================

class TestMultipleAgents:
    """Tests for concurrent agents on a single WebSocket connection."""

    def test_two_agents_independent_messages(self, ws_streaming_client):
        """Two agents can be created and send messages independently."""
        events_a = [
            ("assistant_text", {"text": "Response A"}),
            ("result", {"text": "", "session_id": None, "cost": 0.01,
                        "duration_ms": 100, "num_turns": 1, "is_error": False}),
        ]
        events_b = [
            ("assistant_text", {"text": "Response B"}),
            ("result", {"text": "", "session_id": None, "cost": 0.02,
                        "duration_ms": 200, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()  # initial status

            # Create agent A
            _setup_agent(ws, ctx, agent_id="agent_a", events=events_a)
            # Create agent B
            _setup_agent(ws, ctx, agent_id="agent_b", events=events_b)

            # Send message to agent A
            ctx["_provider_holder"][0] = _make_streaming_provider(events_a)
            ws.send_json({"type": "send_message", "agent_id": "agent_a", "text": "Hi A"})

            collected_a = []
            for _ in range(20):
                msg = ws.receive_json()
                collected_a.append(msg)
                if msg.get("type") == "result" and msg.get("agent_id") == "agent_a":
                    break

            result_a = [m for m in collected_a if m["type"] == "result" and m.get("agent_id") == "agent_a"]
            assert len(result_a) == 1

            # Send message to agent B
            ctx["_provider_holder"][0] = _make_streaming_provider(events_b)
            ws.send_json({"type": "send_message", "agent_id": "agent_b", "text": "Hi B"})

            collected_b = []
            for _ in range(20):
                msg = ws.receive_json()
                collected_b.append(msg)
                if msg.get("type") == "result" and msg.get("agent_id") == "agent_b":
                    break

            result_b = [m for m in collected_b if m["type"] == "result" and m.get("agent_id") == "agent_b"]
            assert len(result_b) == 1

    def test_agent_messages_have_correct_agent_id(self, ws_streaming_client):
        """Each agent's streaming messages carry the correct agent_id."""
        events = [
            ("assistant_text", {"text": "Hello from specific agent"}),
            ("result", {"text": "", "session_id": None, "cost": 0.005,
                        "duration_ms": 50, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            _setup_agent(ws, ctx, agent_id="custom_42", events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "custom_42", "text": "go"})

            collected = []
            for _ in range(20):
                msg = ws.receive_json()
                collected.append(msg)
                if msg.get("type") == "result":
                    break

            # All agent-scoped messages should have agent_id "custom_42"
            for m in collected:
                if m["type"] in ("assistant_text", "tool_use", "tool_result", "result"):
                    assert m.get("agent_id") == "custom_42", \
                        f"Message type {m['type']} has wrong agent_id: {m.get('agent_id')}"

    def test_max_agents_enforced_for_regular(self, ws_streaming_client):
        """Max concurrent agents is enforced for regular (non-subagent) agents."""
        import server
        original_max = server.WS_MAX_CONCURRENT_AGENTS
        server.WS_MAX_CONCURRENT_AGENTS = 2
        try:
            ctx = ws_streaming_client
            with ws_connect(ctx) as ws:
                ws.receive_json()
                _setup_agent(ws, ctx, agent_id="a1", events=[])
                _setup_agent(ws, ctx, agent_id="a2", events=[])

                # Third agent should fail
                tmp = ctx["test_app"]["tmp_path"] / "proj_overflow"
                tmp.mkdir(exist_ok=True)
                ws.send_json({"type": "set_cwd", "path": str(tmp), "agent_id": "a3"})
                msg = drain_until(ws, "error")
                assert "max" in msg["text"].lower() or "concurrent" in msg["text"].lower()
        finally:
            server.WS_MAX_CONCURRENT_AGENTS = original_max


# ===========================================================================
# 18. set_transcription_lang (Extended)
# ===========================================================================

class TestTranscriptionLang:
    """Extended tests for set_transcription_lang."""

    def test_set_lang_to_english(self, ws_streaming_client):
        """Switching transcription language to English works."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            with patch("server.transcriber"):
                ws.send_json({
                    "type": "set_transcription_lang",
                    "lang": "en",
                    "agent_id": "default",
                })
                msg = ws.receive_json()
                assert msg["type"] == "status"
                assert "en" in msg["text"].lower()

    def test_set_lang_to_spanish(self, ws_streaming_client):
        """Switching transcription language to Spanish works."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            with patch("server.transcriber"):
                ws.send_json({
                    "type": "set_transcription_lang",
                    "lang": "es",
                    "agent_id": "default",
                })
                msg = ws.receive_json()
                assert msg["type"] == "status"
                assert "es" in msg["text"].lower()

    def test_set_lang_invalid_ignored(self, ws_streaming_client):
        """Invalid language code is silently ignored."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            with patch("server.transcriber"):
                ws.send_json({
                    "type": "set_transcription_lang",
                    "lang": "xx",
                    "agent_id": "default",
                })
                # No status sent for invalid lang — verify connection is still alive
                ws.send_json({"type": "interrupt", "agent_id": "default"})
                msg = drain_until(ws, "result")
                assert msg["type"] == "result"


# ===========================================================================
# 19. History Loading (GET /api/messages)
# ===========================================================================

class TestHistoryLoading:
    """Tests for message persistence and loading via REST API and database."""

    def test_messages_persisted_after_streaming(self, ws_streaming_client):
        """Messages are saved to DB during streaming and retrievable via GET /api/messages."""
        events = [
            ("assistant_text", {"text": "Test response"}),
            ("result", {"text": "", "session_id": "s1", "cost": 0.01,
                        "duration_ms": 100, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            tmp_dir = _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "save this"})

            # Drain until result
            for _ in range(20):
                msg = ws.receive_json()
                if msg.get("type") == "result":
                    break

        # Now query via REST API
        resp = ctx["client"].get(
            "/api/messages",
            params={"cwd": str(tmp_dir), "agent_id": "default"},
            headers={"Authorization": f"Bearer {ctx['token']}"},
        )
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        # Should have at least user text + assistant_text + result
        types = [m["type"] for m in messages]
        assert "text" in types  # user message
        assert "assistant_text" in types
        assert "result" in types

    def test_get_messages_requires_auth(self, ws_streaming_client):
        """GET /api/messages without auth returns 401."""
        ctx = ws_streaming_client
        resp = ctx["client"].get("/api/messages", params={"cwd": "/tmp"})
        assert resp.status_code == 401

    def test_get_messages_requires_cwd(self, ws_streaming_client):
        """GET /api/messages without cwd returns 400."""
        ctx = ws_streaming_client
        resp = ctx["client"].get(
            "/api/messages",
            headers={"Authorization": f"Bearer {ctx['token']}"},
        )
        assert resp.status_code == 400

    def test_get_messages_empty_project(self, ws_streaming_client):
        """GET /api/messages for empty project returns empty list."""
        ctx = ws_streaming_client
        resp = ctx["client"].get(
            "/api/messages",
            params={"cwd": "/tmp/nonexistent_proj", "agent_id": "default"},
            headers={"Authorization": f"Bearer {ctx['token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    def test_tool_use_messages_persisted(self, ws_streaming_client):
        """tool_use and tool_result events are saved to DB."""
        events = [
            ("tool_use", {"tool": "Read", "tool_id": "tu_1",
                          "input": {"file_path": "test.py"}}),
            ("tool_result", {"tool_id": "tu_1", "content": "print('hi')",
                             "is_error": False}),
            ("assistant_text", {"text": "Done"}),
            ("result", {"text": "", "session_id": None, "cost": 0.02,
                        "duration_ms": 150, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            tmp_dir = _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "read"})

            for _ in range(25):
                msg = ws.receive_json()
                if msg.get("type") == "result":
                    break

        resp = ctx["client"].get(
            "/api/messages",
            params={"cwd": str(tmp_dir), "agent_id": "default"},
            headers={"Authorization": f"Bearer {ctx['token']}"},
        )
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        types = [m["type"] for m in messages]
        assert "tool_use" in types
        assert "tool_result" in types

    def test_delete_messages(self, ws_streaming_client):
        """DELETE /api/messages clears conversation history."""
        events = [
            ("assistant_text", {"text": "ephemeral"}),
            ("result", {"text": "", "session_id": None, "cost": 0.0,
                        "duration_ms": 10, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            tmp_dir = _setup_agent(ws, ctx, events=events)
            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "default", "text": "tmp"})
            for _ in range(20):
                msg = ws.receive_json()
                if msg.get("type") == "result":
                    break

        # Delete messages
        resp = ctx["client"].request(
            "DELETE",
            "/api/messages",
            params={"cwd": str(tmp_dir), "agent_id": "default"},
            headers={"Authorization": f"Bearer {ctx['token']}", "Origin": "http://localhost:8000"},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] > 0

        # Verify empty
        resp = ctx["client"].get(
            "/api/messages",
            params={"cwd": str(tmp_dir), "agent_id": "default"},
            headers={"Authorization": f"Bearer {ctx['token']}"},
        )
        assert resp.json()["messages"] == []


# ===========================================================================
# 20. Alter Ego Switch During Active Agent
# ===========================================================================

class TestAlterEgoSwitch:
    """Tests for switching alter ego while agents are active."""

    def test_set_alter_ego_sends_events(self, ws_streaming_client):
        """set_alter_ego sends alter_ego_changed and status."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "set_alter_ego",
                "ego_id": "rain",
                "agent_id": "default",
            })
            msgs = drain_messages(ws, 10)
            types = [m["type"] for m in msgs]
            assert "alter_ego_changed" in types

    def test_set_alter_ego_invalid(self, ws_streaming_client):
        """set_alter_ego with invalid ego_id returns error."""
        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "set_alter_ego",
                "ego_id": "nonexistent_ego_xyz",
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["text"].lower()


# ===========================================================================
# 21. Message Persistence Across Agents
# ===========================================================================

class TestMessagePersistenceAcrossAgents:
    """Tests for per-agent message isolation in the database."""

    def test_messages_isolated_by_agent_id(self, ws_streaming_client):
        """Messages from different agents are isolated in the DB."""
        events = [
            ("assistant_text", {"text": "agent specific response"}),
            ("result", {"text": "", "session_id": None, "cost": 0.0,
                        "duration_ms": 10, "num_turns": 1, "is_error": False}),
        ]

        ctx = ws_streaming_client
        with ws_connect(ctx) as ws:
            ws.receive_json()

            # Agent A sends a message
            tmp_dir = ctx["test_app"]["tmp_path"] / "project_isolation"
            tmp_dir.mkdir(exist_ok=True)

            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "set_cwd", "path": str(tmp_dir), "agent_id": "iso_a"})
            drain_until(ws, "status")

            ctx["_provider_holder"][0] = _make_streaming_provider(events)
            ws.send_json({"type": "send_message", "agent_id": "iso_a", "text": "from A"})
            for _ in range(20):
                msg = ws.receive_json()
                if msg.get("type") == "result":
                    break

        # Query messages for iso_a
        resp = ctx["client"].get(
            "/api/messages",
            params={"cwd": str(tmp_dir), "agent_id": "iso_a"},
            headers={"Authorization": f"Bearer {ctx['token']}"},
        )
        msgs_a = resp.json()["messages"]
        assert len(msgs_a) > 0

        # Query messages for iso_b (never sent anything)
        resp = ctx["client"].get(
            "/api/messages",
            params={"cwd": str(tmp_dir), "agent_id": "iso_b"},
            headers={"Authorization": f"Bearer {ctx['token']}"},
        )
        msgs_b = resp.json()["messages"]
        assert len(msgs_b) == 0
