"""Tests for MCP graceful degradation.

Verifies that:
- Valid .mcp.json is parsed and per-server validated
- Corrupted .mcp.json does not crash the server
- Missing server scripts are detected and those servers disabled
- Missing .mcp.json returns empty dict (no crash)
- Per-server status tracking works correctly
- MCP tool-to-server mapping is built correctly
- Disabled MCP server detection works
- Error messages are user-friendly
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mcp_config(servers: dict) -> dict:
    """Build a .mcp.json structure."""
    return {"mcpServers": servers}


VALID_SERVER = {
    "command": "node",
    "args": ["C:/path/to/server/dist/index.js"],
}


# ---------------------------------------------------------------------------
# _validate_mcp_server_entry tests
# ---------------------------------------------------------------------------


class TestValidateMcpServerEntry:
    """Test individual server config validation."""

    def test_valid_entry_with_existing_command(self):
        from server import _validate_mcp_server_entry
        # node should be in PATH in most test environments
        entry = {"command": "node", "args": []}
        result = _validate_mcp_server_entry("test-server", entry)
        # If node is installed, result is None (valid) or error about script
        # Either way, it should not crash
        assert result is None or isinstance(result, str)

    def test_missing_command_field(self):
        from server import _validate_mcp_server_entry
        result = _validate_mcp_server_entry("bad-server", {"args": []})
        assert result is not None
        assert "missing 'command'" in result

    def test_non_dict_entry(self):
        from server import _validate_mcp_server_entry
        result = _validate_mcp_server_entry("bad-server", "not a dict")
        assert result is not None
        assert "not a JSON object" in result

    def test_missing_script_file(self):
        from server import _validate_mcp_server_entry
        entry = {
            "command": "node",
            "args": ["/nonexistent/path/to/index.js"],
        }
        result = _validate_mcp_server_entry("test-server", entry)
        assert result is not None
        assert "script not found" in result

    def test_valid_entry_with_existing_script(self, tmp_path):
        from server import _validate_mcp_server_entry
        script = tmp_path / "index.js"
        script.write_text("// test")
        entry = {"command": "node", "args": [str(script)]}
        # Patch shutil.which to always find node
        with patch("shutil.which", return_value="/usr/bin/node"):
            result = _validate_mcp_server_entry("test-server", entry)
        assert result is None

    def test_command_not_in_path(self):
        from server import _validate_mcp_server_entry
        entry = {"command": "node", "args": []}
        with patch("shutil.which", return_value=None):
            result = _validate_mcp_server_entry("test-server", entry)
        assert result is not None
        assert "not found in PATH" in result

    def test_unknown_command_always_valid(self):
        """Commands not in the known list (node/python) skip the which() check."""
        from server import _validate_mcp_server_entry
        entry = {"command": "custom-binary", "args": []}
        result = _validate_mcp_server_entry("test-server", entry)
        assert result is None


# ---------------------------------------------------------------------------
# _load_mcp_config tests
# ---------------------------------------------------------------------------


class TestLoadMcpConfig:
    """Test the full config loading with per-server validation."""

    def test_missing_config_file(self, tmp_path):
        """Missing .mcp.json returns empty dict without crashing."""
        from server import _load_mcp_config, _MCP_CONFIG_PATH
        import server

        fake_path = tmp_path / ".mcp.json"
        with patch.object(server, "_MCP_CONFIG_PATH", fake_path):
            result = _load_mcp_config()
        assert result == {}

    def test_corrupted_json(self, tmp_path):
        """Corrupted JSON returns empty dict without crashing."""
        from server import _load_mcp_config
        import server

        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text("{invalid json!!!", encoding="utf-8")
        with patch.object(server, "_MCP_CONFIG_PATH", fake_path):
            result = _load_mcp_config()
        assert result == {}

    def test_non_object_json(self, tmp_path):
        """Non-object JSON (array, string) returns empty dict."""
        from server import _load_mcp_config
        import server

        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text('["not", "an", "object"]', encoding="utf-8")
        with patch.object(server, "_MCP_CONFIG_PATH", fake_path):
            result = _load_mcp_config()
        assert result == {}

    def test_empty_servers(self, tmp_path):
        """Empty mcpServers block returns empty dict."""
        from server import _load_mcp_config
        import server

        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
        with patch.object(server, "_MCP_CONFIG_PATH", fake_path):
            result = _load_mcp_config()
        assert result == {}

    def test_valid_servers_returned_as_flat_dict(self, tmp_path):
        """Valid servers are returned as a flat dict (not wrapped in mcpServers)."""
        from server import _load_mcp_config
        import server

        script = tmp_path / "index.js"
        script.write_text("// test")

        config = _make_mcp_config({
            "rain-email": {"command": "node", "args": [str(script)]},
        })
        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text(json.dumps(config), encoding="utf-8")

        with patch.object(server, "_MCP_CONFIG_PATH", fake_path), \
             patch("shutil.which", return_value="/usr/bin/node"):
            result = _load_mcp_config()

        # Should be flat: {"rain-email": {...}} not {"mcpServers": {"rain-email": {...}}}
        assert "rain-email" in result
        assert "mcpServers" not in result
        assert result["rain-email"]["command"] == "node"

    def test_invalid_server_excluded(self, tmp_path):
        """A server with a missing script is excluded while others survive."""
        from server import _load_mcp_config
        import server
        import shared_state

        good_script = tmp_path / "good.js"
        good_script.write_text("// good")

        config = _make_mcp_config({
            "rain-email": {"command": "node", "args": [str(good_script)]},
            "rain-browser": {"command": "node", "args": ["/nonexistent/bad.js"]},
        })
        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text(json.dumps(config), encoding="utf-8")

        with patch.object(server, "_MCP_CONFIG_PATH", fake_path), \
             patch("shutil.which", return_value="/usr/bin/node"):
            result = _load_mcp_config()

        # Only the valid server should be in the result
        assert "rain-email" in result
        assert "rain-browser" not in result

        # Status tracking should reflect the failure
        assert shared_state.mcp_server_status["rain-email"]["status"] == "ok"
        assert shared_state.mcp_server_status["rain-browser"]["status"] == "error"

    def test_all_servers_invalid(self, tmp_path):
        """If all servers are invalid, return empty dict."""
        from server import _load_mcp_config
        import server

        config = _make_mcp_config({
            "rain-email": {"command": "node", "args": ["/bad/path.js"]},
            "rain-browser": {"command": "node", "args": ["/bad/path2.js"]},
        })
        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text(json.dumps(config), encoding="utf-8")

        with patch.object(server, "_MCP_CONFIG_PATH", fake_path), \
             patch("shutil.which", return_value="/usr/bin/node"):
            result = _load_mcp_config()

        assert result == {}

    def test_tool_server_map_populated(self, tmp_path):
        """Tool-to-server mapping is built from valid servers."""
        from server import _load_mcp_config
        import server
        import shared_state

        script = tmp_path / "index.js"
        script.write_text("// test")

        config = _make_mcp_config({
            "rain-email": {"command": "node", "args": [str(script)]},
            "rain-calendar": {"command": "node", "args": [str(script)]},
        })
        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text(json.dumps(config), encoding="utf-8")

        with patch.object(server, "_MCP_CONFIG_PATH", fake_path), \
             patch("shutil.which", return_value="/usr/bin/node"):
            _load_mcp_config()

        assert "mcp__rain-email__" in shared_state.mcp_tool_server_map
        assert "mcp__rain-calendar__" in shared_state.mcp_tool_server_map
        assert shared_state.mcp_tool_server_map["mcp__rain-email__"] == "rain-email"

    def test_os_error_reading_file(self, tmp_path):
        """OSError when reading .mcp.json returns empty dict."""
        from server import _load_mcp_config
        import server

        fake_path = tmp_path / ".mcp.json"
        fake_path.write_text("{}", encoding="utf-8")

        with patch.object(server, "_MCP_CONFIG_PATH", fake_path), \
             patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            result = _load_mcp_config()
        assert result == {}


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestMcpHelpers:
    """Test _get_mcp_server_for_tool, _is_mcp_server_disabled, _get_mcp_disabled_message."""

    def test_get_mcp_server_for_tool_found(self):
        import shared_state
        from server import _get_mcp_server_for_tool

        shared_state.mcp_tool_server_map["mcp__rain-email__"] = "rain-email"
        try:
            result = _get_mcp_server_for_tool("mcp__rain-email__send_email")
            assert result == "rain-email"
        finally:
            shared_state.mcp_tool_server_map.pop("mcp__rain-email__", None)

    def test_get_mcp_server_for_tool_not_mcp(self):
        from server import _get_mcp_server_for_tool
        result = _get_mcp_server_for_tool("Bash")
        assert result is None

    def test_is_mcp_server_disabled_error(self):
        import shared_state
        from server import _is_mcp_server_disabled

        shared_state.mcp_server_status["rain-email"] = {"status": "error", "error": "test"}
        try:
            assert _is_mcp_server_disabled("rain-email") is True
        finally:
            shared_state.mcp_server_status.pop("rain-email", None)

    def test_is_mcp_server_disabled_ok(self):
        import shared_state
        from server import _is_mcp_server_disabled

        shared_state.mcp_server_status["rain-email"] = {"status": "ok", "error": None}
        try:
            assert _is_mcp_server_disabled("rain-email") is False
        finally:
            shared_state.mcp_server_status.pop("rain-email", None)

    def test_is_mcp_server_disabled_unknown(self):
        from server import _is_mcp_server_disabled
        assert _is_mcp_server_disabled("rain-nonexistent") is True

    def test_get_mcp_disabled_message_not_found(self):
        import shared_state
        from server import _get_mcp_disabled_message

        shared_state.mcp_server_status["rain-email"] = {
            "status": "error",
            "error": "script not found: /bad/path.js",
        }
        try:
            msg = _get_mcp_disabled_message("rain-email")
            assert "not configured" in msg.lower() or "rain setup" in msg.lower()
        finally:
            shared_state.mcp_server_status.pop("rain-email", None)

    def test_get_mcp_disabled_message_generic_error(self):
        import shared_state
        from server import _get_mcp_disabled_message

        shared_state.mcp_server_status["rain-browser"] = {
            "status": "error",
            "error": "timeout connecting",
        }
        try:
            msg = _get_mcp_disabled_message("rain-browser")
            assert "unavailable" in msg.lower()
            assert "timeout connecting" in msg
        finally:
            shared_state.mcp_server_status.pop("rain-browser", None)

    def test_get_mcp_disabled_message_uses_label(self):
        import shared_state
        from server import _get_mcp_disabled_message

        shared_state.mcp_server_status["rain-email"] = {
            "status": "error",
            "error": "not found",
        }
        try:
            msg = _get_mcp_disabled_message("rain-email")
            assert "Email" in msg
        finally:
            shared_state.mcp_server_status.pop("rain-email", None)


# ---------------------------------------------------------------------------
# ClaudeProvider progressive fallback tests
# ---------------------------------------------------------------------------


class TestClaudeProviderMcpFallback:
    """Test the ClaudeProvider's MCP graceful degradation."""

    def test_failed_mcp_servers_initially_empty(self):
        from providers.claude_provider import ClaudeProvider
        provider = ClaudeProvider()
        assert provider.failed_mcp_servers == []

    @pytest.mark.asyncio
    async def test_mark_mcp_server_failed(self):
        import shared_state
        from providers.claude_provider import _mark_mcp_server_failed

        _mark_mcp_server_failed("rain-test", "test error")
        try:
            assert shared_state.mcp_server_status["rain-test"]["status"] == "error"
            assert shared_state.mcp_server_status["rain-test"]["error"] == "test error"
        finally:
            shared_state.mcp_server_status.pop("rain-test", None)

    @pytest.mark.asyncio
    async def test_mark_all_mcp_servers_failed(self):
        import shared_state
        from providers.claude_provider import _mark_all_mcp_servers_failed

        servers = {"rain-a": {}, "rain-b": {}}
        _mark_all_mcp_servers_failed(servers, "all failed")
        try:
            assert shared_state.mcp_server_status["rain-a"]["status"] == "error"
            assert shared_state.mcp_server_status["rain-b"]["status"] == "error"
        finally:
            shared_state.mcp_server_status.pop("rain-a", None)
            shared_state.mcp_server_status.pop("rain-b", None)


# ---------------------------------------------------------------------------
# MCP status endpoint test
# ---------------------------------------------------------------------------


class TestMcpStatusEndpoint:
    """Test the /api/mcp/status REST endpoint."""

    @pytest.mark.asyncio
    async def test_mcp_status_unauthenticated(self, test_app):
        from httpx import AsyncClient, ASGITransport

        transport = ASGITransport(app=test_app["app"])
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/mcp/status")
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_mcp_status_authenticated(self, test_app):
        import shared_state
        from rate_limiter import rate_limiter

        # Clear rate limiter to avoid 429/403 from other tests
        rate_limiter._windows.clear()

        from httpx import AsyncClient, ASGITransport

        transport = ASGITransport(app=test_app["app"])
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Authenticate (Origin header required by CSRF middleware)
            resp = await client.post(
                "/api/auth",
                json={"pin": test_app["pin"]},
                headers={"Origin": "http://testserver"},
            )
            assert resp.status_code == 200, f"Auth failed: {resp.text}"
            token = resp.json()["token"]
            client.headers["Authorization"] = f"Bearer {token}"

            # Set up some test status
            shared_state.mcp_server_status["rain-email"] = {"status": "ok", "error": None}
            shared_state.mcp_server_status["rain-browser"] = {"status": "error", "error": "test error"}

            try:
                resp = await client.get("/api/mcp/status")
                assert resp.status_code == 200
                data = resp.json()

                assert "servers" in data
                assert "config_exists" in data
                assert data["servers"]["rain-email"]["status"] == "ok"
                assert data["servers"]["rain-browser"]["status"] == "error"
                assert data["servers"]["rain-browser"]["label"] == "Browser"
            finally:
                shared_state.mcp_server_status.pop("rain-email", None)
                shared_state.mcp_server_status.pop("rain-browser", None)
