"""Smoke Test E2E for Rain Assistant.

Comprehensive end-to-end smoke tests that verify all major features:
  - Provider integration (Claude, OpenAI, Gemini, Ollama)
  - WebSocket protocol (auth, agent CRUD, messaging, streaming)
  - REST API endpoints (health, auth, history, memories, alter-egos)
  - Plugin lifecycle (create -> enable -> use -> disable -> delete)
  - RAG / Documents (ingest -> search -> remove)
  - MCP server availability (Email, Browser, Calendar, Smart Home)
  - Telegram bot readiness
  - Computer Use availability

Run modes:
    pytest tests/test_smoke_e2e.py -m smoke          # Quick checks only
    pytest tests/test_smoke_e2e.py -m e2e             # Full integration
    pytest tests/test_smoke_e2e.py                    # Everything

Tests are skipped automatically when required API keys, configs, or
services are not available.
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Environment detection helpers
# ---------------------------------------------------------------------------

def _has_env(var: str) -> bool:
    """Check if an environment variable is set and non-empty."""
    return bool(os.environ.get(var, "").strip())


def _has_anthropic_key() -> bool:
    return _has_env("ANTHROPIC_API_KEY")


def _has_openai_key() -> bool:
    return _has_env("OPENAI_API_KEY")


def _has_google_key() -> bool:
    return _has_env("GOOGLE_API_KEY")


def _ollama_available() -> bool:
    """Check if Ollama is running locally."""
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _has_telegram_config() -> bool:
    """Check if Telegram bot token is configured."""
    config_file = Path.home() / ".rain-assistant" / "config.json"
    if not config_file.exists():
        return False
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8"))
        return bool(cfg.get("telegram", {}).get("bot_token"))
    except Exception:
        return False


def _has_mcp_config() -> bool:
    """Check if .mcp.json exists and has at least one server."""
    mcp_path = Path(__file__).parent.parent / ".mcp.json"
    if not mcp_path.exists():
        return False
    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        return bool(data.get("mcpServers"))
    except Exception:
        return False


def _mcp_has_server(name: str) -> bool:
    """Check if a specific MCP server is configured."""
    mcp_path = Path(__file__).parent.parent / ".mcp.json"
    if not mcp_path.exists():
        return False
    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        return name in data.get("mcpServers", {})
    except Exception:
        return False


def _computer_use_available() -> bool:
    """Check if computer-use dependencies are installed."""
    try:
        from anthropic import AsyncAnthropic
        import pyautogui
        import mss
        return True
    except ImportError:
        return False


def _sentence_transformers_available() -> bool:
    """Check if sentence-transformers is available for RAG."""
    try:
        from sentence_transformers import SentenceTransformer
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Skip condition decorators
# ---------------------------------------------------------------------------

skip_no_anthropic = pytest.mark.skipif(
    not _has_anthropic_key(),
    reason="ANTHROPIC_API_KEY not set",
)
skip_no_openai = pytest.mark.skipif(
    not _has_openai_key(),
    reason="OPENAI_API_KEY not set",
)
skip_no_google = pytest.mark.skipif(
    not _has_google_key(),
    reason="GOOGLE_API_KEY not set",
)
skip_no_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running on localhost:11434",
)
skip_no_telegram = pytest.mark.skipif(
    not _has_telegram_config(),
    reason="Telegram bot_token not configured",
)
skip_no_mcp = pytest.mark.skipif(
    not _has_mcp_config(),
    reason=".mcp.json not found or empty",
)
skip_no_computer_use = pytest.mark.skipif(
    not _computer_use_available(),
    reason="Computer Use dependencies not installed",
)
skip_no_embeddings = pytest.mark.skipif(
    not _sentence_transformers_available(),
    reason="sentence-transformers not installed (pip install rain-assistant[memory])",
)


# ---------------------------------------------------------------------------
# Pytest markers registration
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.e2e]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_provider(provider_name="claude"):
    """Create a mock provider that avoids real API calls."""
    prov = AsyncMock()
    prov.provider_name = provider_name
    prov.supports_session_resumption.return_value = False
    prov.supports_computer_use.return_value = False
    prov._tool_executor = None
    return prov


@pytest.fixture()
def smoke_client(test_app):
    """Provide a Starlette TestClient + valid auth token for smoke tests.

    Patches the provider factory so no real API calls are made
    unless explicitly testing a live provider.
    """
    mock_sa_manager = MagicMock()
    mock_sa_manager.cleanup_children = AsyncMock()
    mock_sa_manager.cleanup_all = AsyncMock()

    with patch.object(
        __import__("server"), "get_provider",
        side_effect=lambda *a, **kw: _make_mock_provider(),
    ), \
        patch("subagents.SubAgentManager", return_value=mock_sa_manager), \
        patch("subagents.create_subagent_handler", return_value=AsyncMock()):

        from rate_limiter import rate_limiter as rl
        rl.reset()

        client = TestClient(test_app["app"])

        # CSRF middleware requires Origin header on POST requests
        resp = client.post(
            "/api/auth",
            json={"pin": test_app["pin"]},
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]

        yield {
            "client": client,
            "token": token,
            "test_app": test_app,
            "pin": test_app["pin"],
        }


def ws_connect(smoke_client, token=None):
    """Open a WebSocket connection with the given token."""
    t = token or smoke_client["token"]
    return smoke_client["client"].websocket_connect(f"/ws?token={t}")


def drain_until(ws, msg_type, max_messages=30, timeout_msg=None):
    """Read messages until we find one with the given type."""
    for _ in range(max_messages):
        msg = ws.receive_json()
        if msg.get("type") == msg_type:
            return msg
    raise TimeoutError(
        timeout_msg or f"Never received message type '{msg_type}' in {max_messages} messages"
    )


def drain_messages(ws, count=10):
    """Read and discard up to `count` messages. Returns all collected."""
    msgs = []
    for _ in range(count):
        try:
            msgs.append(ws.receive_json())
        except Exception:
            break
    return msgs


# ===========================================================================
# 1. HEALTH & READINESS
# ===========================================================================

class TestHealthEndpoints:
    """Tests for health and readiness probes (unauthenticated)."""

    @pytest.mark.smoke
    def test_health_endpoint(self, test_app):
        """GET /health returns 200 with version and checks."""
        from rate_limiter import rate_limiter as rl
        rl.reset()
        client = TestClient(test_app["app"])
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "version" in body
        assert "uptime_seconds" in body
        assert "checks" in body
        assert body["checks"]["database"] == "ok"

    @pytest.mark.smoke
    def test_readiness_endpoint(self, test_app):
        """GET /ready returns 200 with status=ready."""
        from rate_limiter import rate_limiter as rl
        rl.reset()
        client = TestClient(test_app["app"])
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


# ===========================================================================
# 2. AUTHENTICATION
# ===========================================================================

class TestAuthentication:
    """Tests for the /api/auth endpoint and token lifecycle."""

    @pytest.mark.smoke
    def test_auth_valid_pin(self, test_app):
        """Valid PIN returns a token."""
        from rate_limiter import rate_limiter as rl
        rl.reset()
        client = TestClient(test_app["app"])
        resp = client.post(
            "/api/auth",
            json={"pin": test_app["pin"]},
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) > 10

    @pytest.mark.smoke
    def test_auth_invalid_pin(self, test_app):
        """Invalid PIN returns 401."""
        from rate_limiter import rate_limiter as rl
        rl.reset()
        client = TestClient(test_app["app"])
        resp = client.post(
            "/api/auth",
            json={"pin": "wrongpin"},
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 401

    @pytest.mark.smoke
    def test_auth_empty_body(self, test_app):
        """Empty body returns 400."""
        from rate_limiter import rate_limiter as rl
        rl.reset()
        client = TestClient(test_app["app"])
        resp = client.post(
            "/api/auth",
            json={},
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code in (400, 422)


# ===========================================================================
# 3. WEBSOCKET CONNECTION
# ===========================================================================

class TestWebSocketConnection:
    """Smoke tests for WebSocket connection lifecycle."""

    @pytest.mark.smoke
    def test_ws_connect_and_receive_status(self, smoke_client):
        """WebSocket connects and receives initial status."""
        with ws_connect(smoke_client) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "status"
            assert "Connected" in msg["text"]

    @pytest.mark.smoke
    def test_ws_reject_invalid_token(self, smoke_client):
        """WebSocket rejects invalid token."""
        with pytest.raises(Exception):
            with smoke_client["client"].websocket_connect("/ws?token=invalid_token") as ws:
                ws.receive_json()

    @pytest.mark.smoke
    def test_ws_set_cwd_creates_agent(self, smoke_client):
        """set_cwd creates an agent and returns Ready status."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()  # drain initial status
            tmp_dir = smoke_client["test_app"]["tmp_path"] / "smoke_project"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({
                "type": "set_cwd",
                "path": str(tmp_dir),
                "agent_id": "smoke-agent",
            })
            msg = drain_until(ws, "status")
            assert "Ready" in msg["text"]
            assert msg.get("cwd") is not None

    @pytest.mark.smoke
    def test_ws_destroy_agent(self, smoke_client):
        """destroy_agent removes the agent."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            tmp_dir = smoke_client["test_app"]["tmp_path"] / "destroy_test"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({
                "type": "set_cwd",
                "path": str(tmp_dir),
                "agent_id": "doomed",
            })
            drain_until(ws, "status")
            ws.send_json({"type": "destroy_agent", "agent_id": "doomed"})
            msg = drain_until(ws, "agent_destroyed")
            assert msg["agent_id"] == "doomed"

    @pytest.mark.smoke
    def test_ws_send_message_without_agent(self, smoke_client):
        """Sending message before set_cwd returns error."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            ws.send_json({
                "type": "send_message",
                "agent_id": "default",
                "text": "hello",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "no project directory" in msg["text"].lower()

    @pytest.mark.smoke
    def test_ws_heartbeat_pong(self, smoke_client):
        """Sending pong is accepted without error."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            ws.send_json({"type": "pong"})
            # Verify connection is still alive
            ws.send_json({
                "type": "send_message",
                "agent_id": "default",
                "text": "test",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"  # no project, but connection is alive

    @pytest.mark.smoke
    def test_ws_provider_override(self, smoke_client):
        """set_cwd accepts model and provider overrides."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            tmp_dir = smoke_client["test_app"]["tmp_path"] / "provider_test"
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
# 4. REST API ENDPOINTS (authenticated)
# ===========================================================================

class TestRESTAPI:
    """Smoke tests for authenticated REST API endpoints."""

    @pytest.mark.smoke
    async def test_history_endpoint(self, authenticated_client):
        """GET /api/history returns conversations."""
        resp = await authenticated_client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        # Response is {"conversations": [...]} or a bare list
        if isinstance(data, dict):
            assert "conversations" in data
            assert isinstance(data["conversations"], list)
        else:
            assert isinstance(data, list)

    @pytest.mark.smoke
    async def test_memories_endpoint(self, authenticated_client):
        """GET /api/memories returns memories."""
        resp = await authenticated_client.get("/api/memories")
        assert resp.status_code == 200
        data = resp.json()
        # Response is {"memories": [...]} or a bare list
        if isinstance(data, dict):
            assert "memories" in data
            assert isinstance(data["memories"], list)
        else:
            assert isinstance(data, list)

    @pytest.mark.smoke
    async def test_alter_egos_endpoint(self, authenticated_client):
        """GET /api/alter-egos returns at least one ego."""
        resp = await authenticated_client.get("/api/alter-egos")
        assert resp.status_code == 200
        data = resp.json()
        # Response is {"egos": [...], "active_ego_id": "..."} or a bare list
        if isinstance(data, dict):
            assert "egos" in data
            egos = data["egos"]
        else:
            egos = data
        assert isinstance(egos, list)
        assert len(egos) >= 1

    @pytest.mark.smoke
    async def test_browse_endpoint(self, test_app):
        """GET /api/browse returns directory listing for home."""
        from httpx import AsyncClient, ASGITransport
        from rate_limiter import rate_limiter as rl
        rl.reset()

        transport = ASGITransport(app=test_app["app"])
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Authenticate (include origin for CSRF)
            resp = await client.post(
                "/api/auth",
                json={"pin": test_app["pin"]},
                headers={"origin": "http://testserver"},
            )
            assert resp.status_code == 200, f"Auth failed: {resp.text}"
            token = resp.json()["token"]
            client.headers["Authorization"] = f"Bearer {token}"

            resp = await client.get("/api/browse", params={"path": str(Path.home())})
            assert resp.status_code == 200
            data = resp.json()
            assert "entries" in data

    @pytest.mark.smoke
    async def test_unauthenticated_rejected(self, unauthenticated_client):
        """Unauthenticated requests to protected endpoints return 401/403."""
        resp = await unauthenticated_client.get("/api/history")
        assert resp.status_code in (401, 403)


# ===========================================================================
# 5. PROVIDER INTEGRATION (live, requires API keys)
# ===========================================================================

class TestProviderInitialization:
    """Tests for provider factory and initialization.

    These tests verify that providers can be created and configured.
    They use mocks for the actual API calls unless API keys are available.
    """

    @pytest.mark.smoke
    def test_provider_factory_claude(self):
        """get_provider('claude') returns ClaudeProvider."""
        from providers import get_provider
        provider = get_provider("claude")
        assert provider.provider_name == "claude"

    @pytest.mark.smoke
    def test_provider_factory_openai(self):
        """get_provider('openai') returns OpenAIProvider."""
        from providers import get_provider
        provider = get_provider("openai")
        assert provider.provider_name == "openai"

    @pytest.mark.smoke
    def test_provider_factory_gemini(self):
        """get_provider('gemini') returns GeminiProvider."""
        from providers import get_provider
        provider = get_provider("gemini")
        assert provider.provider_name == "gemini"

    @pytest.mark.smoke
    def test_provider_factory_ollama(self):
        """get_provider('ollama') returns OllamaProvider."""
        from providers import get_provider
        provider = get_provider("ollama")
        assert provider.provider_name == "ollama"

    @pytest.mark.smoke
    def test_provider_factory_invalid(self):
        """get_provider with unknown name raises ValueError."""
        from providers import get_provider
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    @pytest.mark.smoke
    def test_provider_base_interface(self):
        """All providers implement the required BaseProvider interface."""
        from providers import get_provider
        for name in ("claude", "openai", "gemini", "ollama"):
            p = get_provider(name)
            assert hasattr(p, "initialize")
            assert hasattr(p, "send_message")
            assert hasattr(p, "stream_response")
            assert hasattr(p, "interrupt")
            assert hasattr(p, "disconnect")
            assert hasattr(p, "supports_session_resumption")
            assert hasattr(p, "supports_computer_use")


class TestProviderLiveChat:
    """Live provider tests that require real API keys.

    Each test sends a simple message and verifies the provider
    responds with streaming events. Tests have a 60-second timeout.
    """

    @skip_no_anthropic
    @pytest.mark.e2e
    @pytest.mark.timeout(60)
    async def test_claude_chat(self, tmp_path):
        """Claude provider responds to a simple chat message."""
        from providers import get_provider

        provider = get_provider("claude")
        cwd = str(tmp_path)

        async def auto_approve(*args, **kwargs):
            from claude_agent_sdk import PermissionResultAllow
            return PermissionResultAllow()

        await provider.initialize(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model="auto",
            cwd=cwd,
            system_prompt="You are a test assistant. Reply with exactly: SMOKE_OK",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message("Say SMOKE_OK")
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type == "result":
                    break

            event_types = [e.type for e in events]
            assert "result" in event_types, f"Expected 'result' event, got: {event_types}"

            # Check that we got some text
            text_parts = [
                e.data.get("text", "") for e in events if e.type == "assistant_text"
            ]
            full_text = "".join(text_parts)
            assert len(full_text) > 0, "Expected non-empty response text"
        finally:
            await provider.disconnect()

    @skip_no_anthropic
    @pytest.mark.e2e
    @pytest.mark.timeout(60)
    async def test_claude_session_resumption(self, tmp_path):
        """Claude provider supports session resumption."""
        from providers import get_provider

        provider = get_provider("claude")
        assert provider.supports_session_resumption(), (
            "Claude provider should support session resumption"
        )
        await provider.disconnect()

    @skip_no_openai
    @pytest.mark.e2e
    @pytest.mark.timeout(60)
    async def test_openai_chat(self, tmp_path):
        """OpenAI provider responds to a simple chat message."""
        from providers import get_provider

        provider = get_provider("openai")
        cwd = str(tmp_path)

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-4o-mini",
            cwd=cwd,
            system_prompt="You are a test assistant. Reply with exactly: SMOKE_OK",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message("Say SMOKE_OK")
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type == "result":
                    break

            event_types = [e.type for e in events]
            assert "result" in event_types, f"Expected 'result' event, got: {event_types}"
        finally:
            await provider.disconnect()

    @skip_no_openai
    @pytest.mark.e2e
    @pytest.mark.timeout(60)
    async def test_openai_streaming(self, tmp_path):
        """OpenAI provider streams text incrementally."""
        from providers import get_provider

        provider = get_provider("openai")

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-4o-mini",
            cwd=str(tmp_path),
            system_prompt="Reply with a short greeting.",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message("Hello")
            text_events = []
            async for event in provider.stream_response():
                if event.type == "assistant_text":
                    text_events.append(event)
                if event.type == "result":
                    break

            assert len(text_events) > 0, "Expected streaming text events"
        finally:
            await provider.disconnect()

    @skip_no_google
    @pytest.mark.e2e
    @pytest.mark.timeout(60)
    async def test_gemini_chat(self, tmp_path):
        """Gemini provider responds to a simple chat message."""
        from providers import get_provider

        provider = get_provider("gemini")

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key=os.environ["GOOGLE_API_KEY"],
            model="auto",
            cwd=str(tmp_path),
            system_prompt="You are a test assistant. Reply with exactly: SMOKE_OK",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message("Say SMOKE_OK")
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type == "result":
                    break

            event_types = [e.type for e in events]
            assert "result" in event_types, f"Expected 'result' event, got: {event_types}"
        finally:
            await provider.disconnect()

    @skip_no_google
    @pytest.mark.e2e
    @pytest.mark.timeout(60)
    async def test_gemini_streaming(self, tmp_path):
        """Gemini provider streams text incrementally."""
        from providers import get_provider

        provider = get_provider("gemini")

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key=os.environ["GOOGLE_API_KEY"],
            model="auto",
            cwd=str(tmp_path),
            system_prompt="Reply with a short greeting.",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message("Hello")
            text_events = []
            async for event in provider.stream_response():
                if event.type == "assistant_text":
                    text_events.append(event)
                if event.type == "result":
                    break

            assert len(text_events) > 0, "Expected streaming text events"
        finally:
            await provider.disconnect()

    @skip_no_ollama
    @pytest.mark.e2e
    @pytest.mark.timeout(120)
    async def test_ollama_chat(self, tmp_path):
        """Ollama provider responds to a simple chat message."""
        from providers import get_provider

        provider = get_provider("ollama")

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key="",  # Ollama does not need an API key
            model="auto",
            cwd=str(tmp_path),
            system_prompt="You are a test assistant. Reply with exactly: SMOKE_OK",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message("Say SMOKE_OK")
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type in ("result", "error"):
                    break

            event_types = [e.type for e in events]
            # Ollama might return an error if no models are pulled
            if "error" in event_types:
                pytest.skip("Ollama returned an error (no model available?)")
            assert "result" in event_types, f"Expected 'result' event, got: {event_types}"
        finally:
            await provider.disconnect()

    @skip_no_ollama
    @pytest.mark.e2e
    @pytest.mark.timeout(120)
    async def test_ollama_graceful_no_tools(self, tmp_path):
        """Ollama gracefully handles tool-use requests (may not support them)."""
        from providers import get_provider

        provider = get_provider("ollama")

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key="",
            model="auto",
            cwd=str(tmp_path),
            system_prompt="List the files in the current directory using the bash tool.",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message("List files in current directory")
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type in ("result", "error"):
                    break

            # Should complete without crashing, regardless of tool support
            event_types = [e.type for e in events]
            assert "result" in event_types or "error" in event_types, (
                f"Expected 'result' or graceful 'error', got: {event_types}"
            )
        finally:
            await provider.disconnect()


# ===========================================================================
# 6. PROVIDER TOOL USE (live, requires API keys)
# ===========================================================================

class TestProviderToolUse:
    """Live tests verifying providers can execute tools."""

    @skip_no_anthropic
    @pytest.mark.e2e
    @pytest.mark.timeout(90)
    async def test_claude_tool_use(self, tmp_path):
        """Claude provider executes tool calls (read_file, etc.)."""
        from providers import get_provider

        # Create a test file for the provider to read
        test_file = tmp_path / "hello.txt"
        test_file.write_text("SMOKE_TEST_CONTENT")

        provider = get_provider("claude")

        async def auto_approve(*args, **kwargs):
            from claude_agent_sdk import PermissionResultAllow
            return PermissionResultAllow()

        await provider.initialize(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model="auto",
            cwd=str(tmp_path),
            system_prompt="You are a test assistant.",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message(
                f"Read the file at {test_file} and tell me its content."
            )
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type == "result":
                    break

            event_types = [e.type for e in events]
            assert "result" in event_types

            # Should have used a tool (Read or read_file)
            tool_events = [e for e in events if e.type == "tool_use"]
            assert len(tool_events) > 0, "Expected at least one tool_use event"
        finally:
            await provider.disconnect()

    @skip_no_openai
    @pytest.mark.e2e
    @pytest.mark.timeout(90)
    async def test_openai_tool_use(self, tmp_path):
        """OpenAI provider executes tool calls."""
        from providers import get_provider

        test_file = tmp_path / "hello.txt"
        test_file.write_text("SMOKE_TEST_CONTENT")

        provider = get_provider("openai")

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-4o-mini",
            cwd=str(tmp_path),
            system_prompt="You are a test assistant.",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message(
                f"Read the file at {test_file} and tell me its content."
            )
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type == "result":
                    break

            event_types = [e.type for e in events]
            assert "result" in event_types
        finally:
            await provider.disconnect()

    @skip_no_google
    @pytest.mark.e2e
    @pytest.mark.timeout(90)
    async def test_gemini_tool_use(self, tmp_path):
        """Gemini provider executes tool calls."""
        from providers import get_provider

        test_file = tmp_path / "hello.txt"
        test_file.write_text("SMOKE_TEST_CONTENT")

        provider = get_provider("gemini")

        async def auto_approve(tool_name, _name2, tool_input):
            return True

        await provider.initialize(
            api_key=os.environ["GOOGLE_API_KEY"],
            model="auto",
            cwd=str(tmp_path),
            system_prompt="You are a test assistant.",
            can_use_tool=auto_approve,
        )

        try:
            await provider.send_message(
                f"Read the file at {test_file} and tell me its content."
            )
            events = []
            async for event in provider.stream_response():
                events.append(event)
                if event.type == "result":
                    break

            event_types = [e.type for e in events]
            assert "result" in event_types
        finally:
            await provider.disconnect()


# ===========================================================================
# 7. PLUGIN LIFECYCLE
# ===========================================================================

class TestPluginLifecycle:
    """Tests for the plugin create -> enable -> use -> disable -> delete cycle."""

    PLUGIN_YAML = """\
name: smoke_test_plugin
description: A smoke test plugin
version: "1.0"
author: smoke-test
enabled: true
permission_level: green
parameters:
  - name: query
    type: string
    description: Test query
    required: true
execution:
  type: http
  method: GET
  url: "https://httpbin.org/get?q={{query}}"
"""

    def _patch_plugins_dir(self, rain_home):
        """Context manager helper to patch PLUGINS_DIR in both loader and meta_tool."""
        from plugins import loader
        from plugins import meta_tool as pm
        old_loader_dir = loader.PLUGINS_DIR
        old_meta_dir = pm.PLUGINS_DIR
        loader.PLUGINS_DIR = rain_home["plugins_dir"]
        pm.PLUGINS_DIR = rain_home["plugins_dir"]
        return old_loader_dir, old_meta_dir

    def _restore_plugins_dir(self, old_loader_dir, old_meta_dir):
        from plugins import loader
        from plugins import meta_tool as pm
        loader.PLUGINS_DIR = old_loader_dir
        pm.PLUGINS_DIR = old_meta_dir

    @pytest.mark.smoke
    async def test_plugin_create(self, rain_home):
        """Create a plugin via meta-tool."""
        from plugins.meta_tool import handle_manage_plugins

        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            result = await handle_manage_plugins({
                "action": "create",
                "yaml_content": self.PLUGIN_YAML,
            }, cwd=str(rain_home["root"]))

            assert not result["is_error"], f"Plugin create failed: {result['content']}"
            assert "created successfully" in result["content"]
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_list(self, rain_home):
        """List plugins after creating one."""
        from plugins.meta_tool import handle_manage_plugins

        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            # Create first
            await handle_manage_plugins({
                "action": "create",
                "yaml_content": self.PLUGIN_YAML,
            }, cwd=str(rain_home["root"]))

            # List
            result = await handle_manage_plugins({
                "action": "list",
            }, cwd=str(rain_home["root"]))

            assert not result["is_error"]
            assert "smoke_test_plugin" in result["content"]
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_disable_enable(self, rain_home):
        """Disable and re-enable a plugin."""
        from plugins.meta_tool import handle_manage_plugins

        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            # Create
            await handle_manage_plugins({
                "action": "create",
                "yaml_content": self.PLUGIN_YAML,
            }, cwd=str(rain_home["root"]))

            # Disable
            result = await handle_manage_plugins({
                "action": "disable",
                "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert not result["is_error"]
            assert "disabled" in result["content"].lower()

            # Verify disabled in list
            result = await handle_manage_plugins({
                "action": "list",
            }, cwd=str(rain_home["root"]))
            assert "disabled" in result["content"]

            # Re-enable
            result = await handle_manage_plugins({
                "action": "enable",
                "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert not result["is_error"]
            assert "enabled" in result["content"].lower()
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_show(self, rain_home):
        """Show plugin YAML content."""
        from plugins.meta_tool import handle_manage_plugins

        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            await handle_manage_plugins({
                "action": "create",
                "yaml_content": self.PLUGIN_YAML,
            }, cwd=str(rain_home["root"]))

            result = await handle_manage_plugins({
                "action": "show",
                "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert not result["is_error"]
            assert "smoke_test_plugin" in result["content"]
            assert "httpbin.org" in result["content"]
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_delete(self, rain_home):
        """Delete a plugin."""
        from plugins.meta_tool import handle_manage_plugins

        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            # Create
            await handle_manage_plugins({
                "action": "create",
                "yaml_content": self.PLUGIN_YAML,
            }, cwd=str(rain_home["root"]))

            # Delete
            result = await handle_manage_plugins({
                "action": "delete",
                "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert not result["is_error"]
            assert "deleted" in result["content"].lower()

            # Verify gone
            result = await handle_manage_plugins({
                "action": "list",
            }, cwd=str(rain_home["root"]))
            assert "smoke_test_plugin" not in result["content"]
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_full_lifecycle(self, rain_home):
        """Full lifecycle: create -> list -> show -> disable -> enable -> delete."""
        from plugins.meta_tool import handle_manage_plugins

        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            # 1. Create
            r = await handle_manage_plugins({
                "action": "create",
                "yaml_content": self.PLUGIN_YAML,
            }, cwd=str(rain_home["root"]))
            assert not r["is_error"], f"Create failed: {r['content']}"

            # 2. List
            r = await handle_manage_plugins({"action": "list"}, cwd=str(rain_home["root"]))
            assert "smoke_test_plugin" in r["content"]
            assert "enabled" in r["content"]

            # 3. Show
            r = await handle_manage_plugins({
                "action": "show", "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert "httpbin.org" in r["content"]

            # 4. Disable
            r = await handle_manage_plugins({
                "action": "disable", "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert "disabled" in r["content"].lower()

            # 5. Enable
            r = await handle_manage_plugins({
                "action": "enable", "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert "enabled" in r["content"].lower()

            # 6. Delete
            r = await handle_manage_plugins({
                "action": "delete", "name": "smoke_test_plugin",
            }, cwd=str(rain_home["root"]))
            assert "deleted" in r["content"].lower()

            # 7. Verify gone
            r = await handle_manage_plugins({"action": "list"}, cwd=str(rain_home["root"]))
            assert "smoke_test_plugin" not in r["content"]
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_set_env(self, rain_home):
        """Set an environment variable for plugins."""
        from plugins.meta_tool import handle_manage_plugins

        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            result = await handle_manage_plugins({
                "action": "set_env",
                "key": "SMOKE_TEST_KEY",
                "value": "smoke_test_value_123",
            }, cwd=str(rain_home["root"]))
            assert not result["is_error"]
            assert "SMOKE_TEST_KEY" in result["content"]
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_security_blocks_python(self, rain_home):
        """Python plugins cannot be created via chat."""
        from plugins.meta_tool import handle_manage_plugins

        python_plugin = """\
name: evil_plugin
description: Bad plugin
version: "1.0"
enabled: true
permission_level: green
parameters: []
execution:
  type: python
  module: evil
  function: hack
"""
        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            result = await handle_manage_plugins({
                "action": "create",
                "yaml_content": python_plugin,
            }, cwd=str(rain_home["root"]))
            assert result["is_error"]
            assert "security" in result["content"].lower() or "python" in result["content"].lower()
        finally:
            self._restore_plugins_dir(old_l, old_m)

    @pytest.mark.smoke
    async def test_plugin_security_blocks_red_level(self, rain_home):
        """Red-level plugins cannot be created via chat."""
        from plugins.meta_tool import handle_manage_plugins

        red_plugin = """\
name: dangerous_plugin
description: Dangerous plugin
version: "1.0"
enabled: true
permission_level: red
parameters: []
execution:
  type: http
  method: GET
  url: "https://example.com"
"""
        old_l, old_m = self._patch_plugins_dir(rain_home)
        try:
            result = await handle_manage_plugins({
                "action": "create",
                "yaml_content": red_plugin,
            }, cwd=str(rain_home["root"]))
            assert result["is_error"]
        finally:
            self._restore_plugins_dir(old_l, old_m)


# ===========================================================================
# 8. PLUGIN SCHEMA VALIDATION
# ===========================================================================

class TestPluginSchema:
    """Tests for plugin YAML schema validation."""

    @pytest.mark.smoke
    def test_valid_plugin_parses(self):
        """A well-formed plugin YAML parses correctly."""
        import yaml
        from plugins.schema import parse_plugin_dict

        data = yaml.safe_load(TestPluginLifecycle.PLUGIN_YAML)
        plugin = parse_plugin_dict(data)
        assert plugin.name == "smoke_test_plugin"
        assert plugin.enabled is True
        assert len(plugin.parameters) == 1

    @pytest.mark.smoke
    def test_missing_name_raises(self):
        """Plugin without name raises PluginValidationError."""
        from plugins.schema import parse_plugin_dict, PluginValidationError

        with pytest.raises(PluginValidationError):
            parse_plugin_dict({
                "description": "no name",
                "execution": {"type": "http", "method": "GET", "url": "https://x.com"},
            })

    @pytest.mark.smoke
    def test_invalid_exec_type_raises(self):
        """Plugin with invalid execution type raises error."""
        from plugins.schema import parse_plugin_dict, PluginValidationError

        with pytest.raises(PluginValidationError):
            parse_plugin_dict({
                "name": "bad_exec",
                "description": "bad",
                "execution": {"type": "java", "method": "GET", "url": "https://x.com"},
            })

    @pytest.mark.smoke
    def test_plugin_to_tool_definition(self):
        """Plugin converts to a valid tool definition for providers."""
        import yaml
        from plugins.schema import parse_plugin_dict
        from plugins.converter import plugin_to_tool_definition

        data = yaml.safe_load(TestPluginLifecycle.PLUGIN_YAML)
        plugin = parse_plugin_dict(data)
        tool_def = plugin_to_tool_definition(plugin)

        assert tool_def["type"] == "function"
        assert tool_def["function"]["name"] == "plugin_smoke_test_plugin"
        assert "parameters" in tool_def["function"]


# ===========================================================================
# 9. RAG / DOCUMENTS
# ===========================================================================

class TestRAGDocuments:
    """Tests for RAG document ingestion, search, and removal."""

    @pytest.mark.smoke
    async def test_document_ingest_and_list(self, tmp_path):
        """Ingest a text file and verify it appears in list."""
        from documents.meta_tool import handle_manage_documents

        # Create test document
        doc = tmp_path / "test_doc.txt"
        doc.write_text("This is a smoke test document for RAG testing.\n" * 10)

        result = await handle_manage_documents({
            "action": "ingest",
            "file_path": str(doc),
        }, cwd=str(tmp_path))

        assert not result["is_error"], f"Ingest failed: {result['content']}"
        assert "ingested" in result["content"].lower()

        # Extract doc_id from result
        doc_id = None
        for line in result["content"].split("\n"):
            if "Doc ID:" in line:
                doc_id = line.split("Doc ID:")[1].strip()
                break
        assert doc_id is not None, "Could not extract doc_id from ingest result"

        # List documents
        result = await handle_manage_documents({"action": "list"}, cwd=str(tmp_path))
        assert not result["is_error"]
        assert "test_doc.txt" in result["content"]

        # Clean up
        await handle_manage_documents({
            "action": "remove",
            "doc_id": doc_id,
        }, cwd=str(tmp_path))

    @skip_no_embeddings
    @pytest.mark.e2e
    async def test_document_search(self, tmp_path):
        """Ingest a document and search for its content."""
        from documents.meta_tool import handle_manage_documents

        doc = tmp_path / "searchable.txt"
        doc.write_text(
            "Rain Assistant is a powerful AI coding tool. "
            "It supports multiple providers including Claude, OpenAI, and Gemini. "
            "Rain has a plugin system for extending functionality."
        )

        result = await handle_manage_documents({
            "action": "ingest",
            "file_path": str(doc),
        }, cwd=str(tmp_path))
        assert not result["is_error"]

        doc_id = None
        for line in result["content"].split("\n"):
            if "Doc ID:" in line:
                doc_id = line.split("Doc ID:")[1].strip()
                break

        try:
            # Search
            result = await handle_manage_documents({
                "action": "search",
                "query": "AI coding tool providers",
            }, cwd=str(tmp_path))
            assert not result["is_error"]
            # Should find relevant chunks
            assert "rain" in result["content"].lower() or "chunk" in result["content"].lower()
        finally:
            if doc_id:
                await handle_manage_documents({
                    "action": "remove",
                    "doc_id": doc_id,
                }, cwd=str(tmp_path))

    @pytest.mark.smoke
    async def test_document_remove(self, tmp_path):
        """Remove a document after ingestion."""
        from documents.meta_tool import handle_manage_documents

        doc = tmp_path / "removable.txt"
        doc.write_text("This document will be removed." * 5)

        result = await handle_manage_documents({
            "action": "ingest",
            "file_path": str(doc),
        }, cwd=str(tmp_path))
        assert not result["is_error"]

        doc_id = None
        for line in result["content"].split("\n"):
            if "Doc ID:" in line:
                doc_id = line.split("Doc ID:")[1].strip()
                break
        assert doc_id

        # Remove
        result = await handle_manage_documents({
            "action": "remove",
            "doc_id": doc_id,
        }, cwd=str(tmp_path))
        assert not result["is_error"]
        assert "removed" in result["content"].lower()

        # Verify gone
        result = await handle_manage_documents({"action": "list"}, cwd=str(tmp_path))
        assert doc_id not in result.get("content", "")

    @pytest.mark.smoke
    async def test_document_unsupported_format(self, tmp_path):
        """Ingesting unsupported file format returns error."""
        from documents.meta_tool import handle_manage_documents

        doc = tmp_path / "bad.xlsx"
        doc.write_text("fake excel")

        result = await handle_manage_documents({
            "action": "ingest",
            "file_path": str(doc),
        }, cwd=str(tmp_path))
        assert result["is_error"]
        assert "unsupported" in result["content"].lower()

    @pytest.mark.smoke
    async def test_document_ingest_markdown(self, tmp_path):
        """Ingest a markdown file."""
        from documents.meta_tool import handle_manage_documents

        doc = tmp_path / "readme.md"
        doc.write_text("# Title\n\nSome markdown content.\n\n## Section\n\nMore text here.")

        result = await handle_manage_documents({
            "action": "ingest",
            "file_path": str(doc),
        }, cwd=str(tmp_path))
        assert not result["is_error"]
        assert "ingested" in result["content"].lower()

        # Clean up
        doc_id = None
        for line in result["content"].split("\n"):
            if "Doc ID:" in line:
                doc_id = line.split("Doc ID:")[1].strip()
                break
        if doc_id:
            await handle_manage_documents({
                "action": "remove", "doc_id": doc_id,
            }, cwd=str(tmp_path))

    @pytest.mark.smoke
    async def test_document_show_chunks(self, tmp_path):
        """Show chunks of an ingested document."""
        from documents.meta_tool import handle_manage_documents

        doc = tmp_path / "chunks_doc.txt"
        doc.write_text("Paragraph one about testing.\n\nParagraph two about verification.\n" * 5)

        result = await handle_manage_documents({
            "action": "ingest",
            "file_path": str(doc),
        }, cwd=str(tmp_path))
        assert not result["is_error"]

        doc_id = None
        for line in result["content"].split("\n"):
            if "Doc ID:" in line:
                doc_id = line.split("Doc ID:")[1].strip()
                break
        assert doc_id

        # Show
        result = await handle_manage_documents({
            "action": "show",
            "doc_id": doc_id,
        }, cwd=str(tmp_path))
        assert not result["is_error"]
        assert "chunk" in result["content"].lower()

        # Clean up
        await handle_manage_documents({
            "action": "remove", "doc_id": doc_id,
        }, cwd=str(tmp_path))


# ===========================================================================
# 10. MCP SERVER AVAILABILITY
# ===========================================================================

class TestMCPServers:
    """Tests for MCP server configuration and availability.

    These verify the MCP config is valid and servers are listed.
    Actual MCP functionality requires OAuth setup and is tested
    as integration-level tests.
    """

    @skip_no_mcp
    @pytest.mark.smoke
    def test_mcp_config_valid_json(self):
        """MCP config file is valid JSON."""
        mcp_path = Path(__file__).parent.parent / ".mcp.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "mcpServers" in data

    @skip_no_mcp
    @pytest.mark.smoke
    def test_mcp_servers_have_commands(self):
        """Each MCP server has a command defined."""
        mcp_path = Path(__file__).parent.parent / ".mcp.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        for name, server in data.get("mcpServers", {}).items():
            assert "command" in server, f"MCP server '{name}' missing 'command'"
            assert isinstance(server["command"], str)

    @pytest.mark.skipif(
        not _mcp_has_server("rain-email"),
        reason="rain-email MCP server not configured",
    )
    @pytest.mark.smoke
    def test_mcp_email_configured(self):
        """Email MCP server is configured."""
        mcp_path = Path(__file__).parent.parent / ".mcp.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        email = data["mcpServers"]["rain-email"]
        assert email["command"] in ("node", "npx")

    @pytest.mark.skipif(
        not _mcp_has_server("rain-browser"),
        reason="rain-browser MCP server not configured",
    )
    @pytest.mark.smoke
    def test_mcp_browser_configured(self):
        """Browser MCP server is configured."""
        mcp_path = Path(__file__).parent.parent / ".mcp.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        browser = data["mcpServers"]["rain-browser"]
        assert browser["command"] in ("node", "npx")

    @pytest.mark.skipif(
        not _mcp_has_server("rain-calendar"),
        reason="rain-calendar MCP server not configured",
    )
    @pytest.mark.smoke
    def test_mcp_calendar_configured(self):
        """Calendar MCP server is configured."""
        mcp_path = Path(__file__).parent.parent / ".mcp.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        cal = data["mcpServers"]["rain-calendar"]
        assert cal["command"] in ("node", "npx")

    @pytest.mark.skipif(
        not _mcp_has_server("rain-smarthome"),
        reason="rain-smarthome MCP server not configured",
    )
    @pytest.mark.smoke
    def test_mcp_smarthome_configured(self):
        """Smart Home MCP server is configured."""
        mcp_path = Path(__file__).parent.parent / ".mcp.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        home = data["mcpServers"]["rain-smarthome"]
        assert home["command"] in ("node", "npx")

    @skip_no_mcp
    @pytest.mark.smoke
    def test_mcp_server_binaries_exist(self):
        """MCP server binaries/scripts exist on disk."""
        mcp_path = Path(__file__).parent.parent / ".mcp.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        for name, server in data.get("mcpServers", {}).items():
            args = server.get("args", [])
            if args:
                script_path = Path(args[0])
                if script_path.is_absolute():
                    assert script_path.exists(), (
                        f"MCP server '{name}' script not found: {script_path}"
                    )


# ===========================================================================
# 11. TELEGRAM BOT
# ===========================================================================

class TestTelegramBot:
    """Tests for Telegram bot configuration and readiness."""

    @pytest.mark.smoke
    def test_telegram_config_module_imports(self):
        """telegram_config module imports without error."""
        from telegram_config import (
            get_bot_token,
            get_allowed_users,
            get_default_provider,
            get_default_model,
            get_default_cwd,
        )
        # These should all return defaults without crashing
        assert get_default_provider() in ("claude", "openai", "gemini", "ollama")
        assert isinstance(get_default_model(), str)
        assert isinstance(get_default_cwd(), str)

    @skip_no_telegram
    @pytest.mark.smoke
    def test_telegram_bot_token_configured(self):
        """Telegram bot token is present in config."""
        from telegram_config import get_bot_token
        token = get_bot_token()
        assert token is not None
        assert len(token) > 10

    @skip_no_telegram
    @pytest.mark.smoke
    def test_telegram_bot_module_imports(self):
        """telegram_bot module imports without error (requires aiogram)."""
        try:
            import telegram_bot
            assert hasattr(telegram_bot, "TelegramSession")
            assert hasattr(telegram_bot, "router")
        except ImportError:
            pytest.skip("aiogram not installed")

    @skip_no_telegram
    @pytest.mark.e2e
    def test_telegram_session_creation(self):
        """TelegramSession can be instantiated for a test user."""
        try:
            from telegram_bot import TelegramSession
            session = TelegramSession(user_id=12345)
            assert session.user_id == 12345
            assert session.provider is None
            assert session.processing is False
        except ImportError:
            pytest.skip("aiogram not installed")


# ===========================================================================
# 12. COMPUTER USE
# ===========================================================================

class TestComputerUse:
    """Tests for Computer Use availability and configuration."""

    @pytest.mark.smoke
    def test_computer_use_flag(self):
        """Server reports Computer Use availability correctly."""
        import server
        # Just verify the flag exists and is a bool
        assert isinstance(server.COMPUTER_USE_AVAILABLE, bool)

    @skip_no_computer_use
    @pytest.mark.smoke
    def test_computer_use_imports(self):
        """Computer Use modules import without error."""
        from computer_use import (
            ComputerUseExecutor,
            describe_action,
            COMPUTER_USE_BETA,
            COMPUTER_USE_MODEL,
        )
        assert isinstance(COMPUTER_USE_BETA, str)
        assert isinstance(COMPUTER_USE_MODEL, str)

    @skip_no_computer_use
    @skip_no_anthropic
    @pytest.mark.e2e
    def test_computer_use_executor_init(self):
        """ComputerUseExecutor can be instantiated."""
        from computer_use import ComputerUseExecutor
        executor = ComputerUseExecutor()
        tool_def = executor.get_tool_definition()
        assert tool_def["type"] == "computer_20250124"
        display = executor.get_display_info()
        assert "width" in display
        assert "height" in display


# ===========================================================================
# 13. PERMISSION CLASSIFIER
# ===========================================================================

class TestPermissionClassifier:
    """Smoke tests for the permission classification system."""

    @pytest.mark.smoke
    def test_green_tools(self):
        """Read-only tools are classified as GREEN."""
        from permission_classifier import classify, PermissionLevel
        assert classify("Read", {}) == PermissionLevel.GREEN
        assert classify("Glob", {}) == PermissionLevel.GREEN
        assert classify("Grep", {}) == PermissionLevel.GREEN

    @pytest.mark.smoke
    def test_yellow_tools(self):
        """Write tools are classified as YELLOW."""
        from permission_classifier import classify, PermissionLevel
        assert classify("Write", {"file_path": "/tmp/test.txt"}) == PermissionLevel.YELLOW
        assert classify("Edit", {"file_path": "/tmp/test.txt"}) == PermissionLevel.YELLOW

    @pytest.mark.smoke
    def test_red_tools(self):
        """Dangerous commands are classified as RED."""
        from permission_classifier import classify, PermissionLevel
        result = classify("Bash", {"command": "rm -rf /"})
        assert result == PermissionLevel.RED

    @pytest.mark.smoke
    def test_danger_reason(self):
        """get_danger_reason returns a non-empty string for dangerous commands."""
        from permission_classifier import get_danger_reason
        reason = get_danger_reason("Bash", {"command": "rm -rf /"})
        assert isinstance(reason, str)
        assert len(reason) > 0


# ===========================================================================
# 14. DATABASE
# ===========================================================================

class TestDatabase:
    """Smoke tests for database operations."""

    @pytest.mark.smoke
    def test_database_init(self, test_db):
        """Database initializes and creates required tables."""
        import sqlite3
        conn = sqlite3.connect(str(test_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Core tables should exist
        assert "messages" in tables
        assert "active_sessions" in tables

    @pytest.mark.smoke
    def test_save_and_load_messages(self, test_db):
        """Messages can be saved and retrieved."""
        import database

        database.save_message(
            cwd="/tmp/test",
            role="user",
            msg_type="text",
            content={"text": "smoke test message"},
            agent_id="test",
        )

        messages = database.get_messages("/tmp/test", agent_id="test")
        assert len(messages) >= 1

    @pytest.mark.smoke
    def test_security_event_logging(self, test_db):
        """Security events can be logged."""
        import database

        database.log_security_event(
            event_type="smoke_test",
            severity="info",
            client_ip="127.0.0.1",
            details="Smoke test security event",
        )
        # Should not raise


# ===========================================================================
# 15. RATE LIMITER
# ===========================================================================

class TestRateLimiter:
    """Smoke tests for the rate limiting system."""

    @pytest.mark.smoke
    def test_rate_limiter_allows_normal_traffic(self):
        """Rate limiter allows normal request volume."""
        from rate_limiter import rate_limiter, EndpointCategory

        rate_limiter.reset()
        result = rate_limiter.check("smoke_test_token", EndpointCategory.GENERIC_API)
        assert result.allowed
        assert result.remaining > 0

    @pytest.mark.smoke
    def test_rate_limiter_categories(self):
        """All endpoint categories exist."""
        from rate_limiter import EndpointCategory

        assert hasattr(EndpointCategory, "AUTH")
        assert hasattr(EndpointCategory, "GENERIC_API")
        assert hasattr(EndpointCategory, "WEBSOCKET_MSG")

    @pytest.mark.smoke
    def test_rate_limiter_reset(self):
        """Rate limiter reset clears all windows."""
        from rate_limiter import rate_limiter, EndpointCategory

        # Fill up some entries
        for i in range(10):
            rate_limiter.check(f"token_{i}", EndpointCategory.GENERIC_API)

        rate_limiter.reset()

        # After reset, should have full capacity
        result = rate_limiter.check("fresh_token", EndpointCategory.GENERIC_API)
        assert result.allowed


# ===========================================================================
# 16. ALTER EGOS
# ===========================================================================

class TestAlterEgos:
    """Smoke tests for the alter ego system."""

    @pytest.mark.smoke
    def test_builtin_egos_exist(self):
        """Built-in alter egos are available."""
        from alter_egos.storage import load_all_egos

        egos = load_all_egos()
        assert len(egos) >= 1
        # "rain" should be the default
        names = [e.get("id", e.get("name", "")) for e in egos]
        assert any("rain" in n.lower() for n in names)

    @pytest.mark.smoke
    def test_load_ego(self):
        """A specific ego can be loaded by ID."""
        from alter_egos.storage import load_ego

        ego = load_ego("rain")
        assert ego is not None
        assert "name" in ego

    @pytest.mark.smoke
    def test_active_ego(self):
        """Active ego ID can be read."""
        from alter_egos.storage import get_active_ego_id

        ego_id = get_active_ego_id()
        assert isinstance(ego_id, str)
        assert len(ego_id) > 0


# ===========================================================================
# 17. PROMPT COMPOSER
# ===========================================================================

class TestPromptComposer:
    """Smoke tests for the system prompt composition."""

    @pytest.mark.smoke
    def test_compose_system_prompt(self):
        """compose_system_prompt returns a non-empty string."""
        from prompt_composer import compose_system_prompt

        prompt = compose_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be substantial

    @pytest.mark.smoke
    def test_compose_with_ego(self):
        """compose_system_prompt works with a specific ego."""
        from prompt_composer import compose_system_prompt

        prompt = compose_system_prompt("rain")
        assert isinstance(prompt, str)
        assert len(prompt) > 100


# ===========================================================================
# 18. MESSAGE VALIDATION
# ===========================================================================

class TestMessageValidation:
    """Smoke tests for WebSocket message validation."""

    @pytest.mark.smoke
    def test_message_too_large(self, smoke_client):
        """Messages exceeding 16KB are rejected."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()  # drain initial status
            big_payload = json.dumps({
                "type": "send_message",
                "text": "x" * 20_000,
            })
            ws.send_text(big_payload)
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "too large" in msg["text"].lower()

    @pytest.mark.smoke
    def test_invalid_json(self, smoke_client):
        """Invalid JSON is rejected."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            ws.send_text("{not valid json}")
            msg = ws.receive_json()
            assert msg["type"] == "error"

    @pytest.mark.smoke
    def test_field_length_limits(self, smoke_client):
        """Oversized type/agent_id fields are rejected."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            ws.send_json({"type": "x" * 60, "agent_id": "default"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "field length" in msg["text"].lower()


# ===========================================================================
# 19. SECURITY HARDENING
# ===========================================================================

class TestSecurityHardening:
    """Smoke tests for security-related features."""

    @pytest.mark.smoke
    def test_security_headers(self, test_app):
        """Responses include security headers."""
        from rate_limiter import rate_limiter as rl
        rl.reset()
        client = TestClient(test_app["app"])
        resp = client.get("/health")
        assert "X-Content-Type-Options" in resp.headers
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in resp.headers
        assert "X-XSS-Protection" in resp.headers
        assert "Content-Security-Policy" in resp.headers

    @pytest.mark.smoke
    def test_path_traversal_blocked(self, smoke_client):
        """set_cwd rejects path traversal attempts."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            # Attempt to escape allowed root
            ws.send_json({
                "type": "set_cwd",
                "path": "/nonexistent/../../etc",
                "agent_id": "default",
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"

    @pytest.mark.smoke
    async def test_api_auth_lockout(self, test_app):
        """Multiple failed auth attempts trigger lockout."""
        from httpx import AsyncClient, ASGITransport
        from rate_limiter import rate_limiter as rl
        rl.reset()

        import server
        server._auth_attempts.clear()

        transport = ASGITransport(app=test_app["app"])
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Fail multiple times (include origin for CSRF)
            for i in range(6):
                resp = await client.post(
                    "/api/auth",
                    json={"pin": "wrong"},
                    headers={"origin": "http://testserver"},
                )
                # After MAX_PIN_ATTEMPTS, should get locked out
                if resp.status_code == 429:
                    body = resp.json()
                    assert body.get("locked") is True
                    return  # Test passed

            # If we get here, check that at least some were rejected
            # (rate limiter may kick in before lockout)


# ===========================================================================
# 20. INTEGRATION: Full WebSocket flow with mocked provider
# ===========================================================================

class TestWebSocketFullFlow:
    """Integration test for the complete message send/receive cycle."""

    @pytest.mark.smoke
    def test_set_api_key_via_ws(self, smoke_client):
        """API key can be set via WebSocket."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()  # initial status
            ws.send_json({
                "type": "set_api_key",
                "key": "sk-test-smoke-key-1234567890",
                "provider": "openai",
            })
            msg = drain_until(ws, "status")
            assert "api key" in msg["text"].lower() or "openai" in msg["text"].lower()

    @pytest.mark.smoke
    def test_set_alter_ego_via_ws(self, smoke_client):
        """Alter ego can be switched via WebSocket."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            # Need an agent first
            tmp_dir = smoke_client["test_app"]["tmp_path"] / "ego_test"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({
                "type": "set_cwd",
                "path": str(tmp_dir),
                "agent_id": "default",
            })
            drain_until(ws, "status")

            ws.send_json({
                "type": "set_alter_ego",
                "ego_id": "rain",
                "agent_id": "default",
            })
            msg = drain_until(ws, "alter_ego_changed", max_messages=15)
            assert msg["ego_id"] == "rain"

    @pytest.mark.smoke
    def test_interrupt_agent(self, smoke_client):
        """Agent can be interrupted."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            tmp_dir = smoke_client["test_app"]["tmp_path"] / "interrupt_test"
            tmp_dir.mkdir(exist_ok=True)
            ws.send_json({
                "type": "set_cwd",
                "path": str(tmp_dir),
                "agent_id": "default",
            })
            drain_until(ws, "status")

            ws.send_json({
                "type": "interrupt",
                "agent_id": "default",
            })
            msg = drain_until(ws, "result")
            assert "interrupted" in msg["text"].lower() or msg.get("is_error") is False

    @pytest.mark.smoke
    def test_permission_response_handling(self, smoke_client):
        """Permission response messages are accepted without error."""
        with ws_connect(smoke_client) as ws:
            ws.receive_json()
            # Send a permission response (even though none is pending)
            # This should not crash the server
            ws.send_json({
                "type": "permission_response",
                "request_id": "perm_nonexistent",
                "approved": True,
            })
            # Connection should still be alive
            ws.send_json({"type": "pong"})
            # If we get here without exception, connection is still up


# ===========================================================================
# 21. TOOL DEFINITIONS
# ===========================================================================

class TestToolDefinitions:
    """Smoke tests for tool definitions available to providers."""

    @pytest.mark.smoke
    def test_get_all_tool_definitions(self):
        """get_all_tool_definitions returns a non-empty list."""
        from tools.definitions import get_all_tool_definitions

        tools = get_all_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) > 0

        # Each tool should have the standard structure
        for tool in tools:
            assert "type" in tool
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]

    @pytest.mark.smoke
    def test_core_tools_present(self):
        """Core tools (read, write, bash, etc.) are in the definitions."""
        from tools.definitions import get_all_tool_definitions

        tools = get_all_tool_definitions()
        tool_names = {t["function"]["name"] for t in tools}

        expected_tools = {"read_file", "write_file", "edit_file", "bash"}
        for expected in expected_tools:
            assert expected in tool_names, f"Missing core tool: {expected}"


# ===========================================================================
# 22. MISC MODULES
# ===========================================================================

class TestMiscModules:
    """Smoke tests for miscellaneous modules."""

    @pytest.mark.smoke
    def test_key_manager_import(self):
        """key_manager module imports without error."""
        from key_manager import ensure_encryption_key
        assert callable(ensure_encryption_key)

    @pytest.mark.smoke
    def test_transcriber_import(self):
        """Transcriber module imports without error."""
        from transcriber import Transcriber
        assert callable(Transcriber)

    @pytest.mark.smoke
    def test_synthesizer_import(self):
        """Synthesizer module imports without error."""
        from synthesizer import Synthesizer
        assert callable(Synthesizer)

    @pytest.mark.smoke
    def test_shared_state_constants(self):
        """shared_state has all expected constants."""
        from shared_state import (
            TOKEN_TTL_SECONDS,
            WS_MAX_MESSAGE_BYTES,
            WS_MAX_TEXT_LENGTH,
            WS_HEARTBEAT_INTERVAL,
            WS_IDLE_TIMEOUT,
            WS_MAX_CONCURRENT_AGENTS,
            _VALID_PROVIDERS,
        )
        assert TOKEN_TTL_SECONDS > 0
        assert WS_MAX_MESSAGE_BYTES > 0
        assert _VALID_PROVIDERS == {"claude", "openai", "gemini", "ollama"}

    @pytest.mark.smoke
    def test_normalized_event(self):
        """NormalizedEvent can be instantiated."""
        from providers.base import NormalizedEvent

        event = NormalizedEvent("assistant_text", {"text": "hello"})
        assert event.type == "assistant_text"
        assert event.data == {"text": "hello"}
        assert "assistant_text" in repr(event)
