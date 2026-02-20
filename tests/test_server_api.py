"""Tests for server.py REST API endpoints — browse, history, metrics, memories, alter-egos."""

import json
import time
from pathlib import Path

import pytest


# =====================================================================
# Browse filesystem
# =====================================================================

class TestBrowseEndpoint:
    """Test /api/browse endpoint."""

    async def test_browse_home(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/browse", params={"path": "~"})
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "entries" in data

    async def test_browse_unauthorized(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/browse")
        assert resp.status_code == 401

    async def test_browse_default_path(self, test_app, authenticated_client):
        """Default path should be home directory."""
        resp = await authenticated_client.get("/api/browse")
        assert resp.status_code == 200

    async def test_browse_path_too_long(self, test_app, authenticated_client):
        long_path = "x" * 1000
        resp = await authenticated_client.get("/api/browse", params={"path": long_path})
        assert resp.status_code == 400


# =====================================================================
# Messages
# =====================================================================

class TestMessagesEndpoint:
    """Test /api/messages GET and DELETE."""

    async def test_get_messages_requires_cwd(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/messages")
        assert resp.status_code == 400

    async def test_get_messages_empty(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/messages", params={"cwd": "/tmp/empty"})
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    async def test_get_messages_unauthorized(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/messages", params={"cwd": "/tmp"})
        assert resp.status_code == 401

    async def test_delete_messages_requires_cwd(self, test_app, authenticated_client):
        resp = await authenticated_client.delete("/api/messages")
        assert resp.status_code == 400

    async def test_delete_messages_empty(self, test_app, authenticated_client):
        resp = await authenticated_client.delete("/api/messages", params={"cwd": "/tmp/empty"})
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0

    async def test_messages_parameter_too_long(self, test_app, authenticated_client):
        long_cwd = "x" * 1000
        resp = await authenticated_client.get("/api/messages", params={"cwd": long_cwd})
        assert resp.status_code == 400


# =====================================================================
# Metrics
# =====================================================================

class TestMetricsEndpoint:
    """Test /api/metrics endpoint."""

    async def test_get_metrics(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "totals" in data
        assert "by_hour" in data
        assert "by_dow" in data
        assert "by_day" in data
        assert "by_month" in data

    async def test_metrics_unauthorized(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/metrics")
        assert resp.status_code == 401

    async def test_metrics_structure(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/metrics")
        data = resp.json()
        assert len(data["by_hour"]) == 24
        assert len(data["by_dow"]) == 7
        assert "all_time" in data["totals"]
        assert "today" in data["totals"]
        assert "this_week" in data["totals"]
        assert "this_month" in data["totals"]


# =====================================================================
# Conversation History
# =====================================================================

class TestHistoryEndpoint:
    """Test /api/history CRUD endpoints."""

    async def test_list_empty_history(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/history")
        assert resp.status_code == 200
        assert resp.json()["conversations"] == []

    async def test_save_and_list_conversation(self, test_app, authenticated_client):
        conv = {
            "id": "conv_test_1",
            "createdAt": "2026-02-18T12:00:00Z",
            "updatedAt": "2026-02-18T12:00:00Z",
            "label": "Test conversation",
            "cwd": "/tmp/test",
            "messageCount": 5,
            "preview": "Hello world",
            "totalCost": 0.05,
            "messages": [{"role": "user", "content": "hello"}],
        }
        resp = await authenticated_client.post("/api/history", json=conv)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

        resp = await authenticated_client.get("/api/history")
        assert resp.status_code == 200
        convs = resp.json()["conversations"]
        assert len(convs) == 1
        assert convs[0]["id"] == "conv_test_1"
        assert convs[0]["label"] == "Test conversation"

    async def test_load_conversation(self, test_app, authenticated_client):
        conv = {
            "id": "conv_load",
            "createdAt": "2026-02-18T12:00:00Z",
            "updatedAt": "2026-02-18T12:00:00Z",
            "messages": [{"role": "user", "content": "test"}],
        }
        await authenticated_client.post("/api/history", json=conv)

        resp = await authenticated_client.get("/api/history/conv_load")
        assert resp.status_code == 200
        assert resp.json()["id"] == "conv_load"

    async def test_load_nonexistent_conversation(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/history/nonexistent")
        assert resp.status_code == 404

    async def test_delete_conversation(self, test_app, authenticated_client):
        conv = {
            "id": "conv_delete",
            "createdAt": "2026-02-18T12:00:00Z",
            "updatedAt": "2026-02-18T12:00:00Z",
        }
        await authenticated_client.post("/api/history", json=conv)

        resp = await authenticated_client.delete("/api/history/conv_delete")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Should be gone
        resp = await authenticated_client.get("/api/history/conv_delete")
        assert resp.status_code == 404

    async def test_delete_nonexistent_conversation(self, test_app, authenticated_client):
        resp = await authenticated_client.delete("/api/history/ghost")
        assert resp.status_code == 404

    async def test_update_existing_conversation(self, test_app, authenticated_client):
        """Saving a conversation with the same ID should update it."""
        conv = {
            "id": "conv_update",
            "createdAt": "2026-02-18T12:00:00Z",
            "updatedAt": "2026-02-18T12:00:00Z",
            "label": "Original",
        }
        await authenticated_client.post("/api/history", json=conv)

        conv["label"] = "Updated"
        conv["updatedAt"] = "2026-02-18T13:00:00Z"
        await authenticated_client.post("/api/history", json=conv)

        resp = await authenticated_client.get("/api/history/conv_update")
        assert resp.json()["label"] == "Updated"

    async def test_history_unauthorized(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/history")
        assert resp.status_code == 401

    async def test_max_conversations_enforced(self, test_app, authenticated_client):
        """Only MAX_CONVERSATIONS should be kept; oldest are deleted."""
        import server
        max_convs = server.MAX_CONVERSATIONS

        for i in range(max_convs + 2):
            conv = {
                "id": f"conv_{i}",
                "createdAt": f"2026-02-18T{i:02d}:00:00Z",
                "updatedAt": f"2026-02-18T{i:02d}:00:00Z",
            }
            await authenticated_client.post("/api/history", json=conv)
            # Small delay to ensure different mtime
            import asyncio
            await asyncio.sleep(0.05)

        resp = await authenticated_client.get("/api/history")
        convs = resp.json()["conversations"]
        assert len(convs) <= max_convs


# =====================================================================
# Memories API
# =====================================================================

class TestMemoriesAPI:
    """Test /api/memories endpoints."""

    async def test_get_memories_empty(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/memories")
        assert resp.status_code == 200
        assert resp.json()["memories"] == []

    async def test_add_memory(self, test_app, authenticated_client):
        resp = await authenticated_client.post("/api/memories", json={
            "content": "User prefers dark mode",
            "category": "preference",
        })
        assert resp.status_code == 200
        assert resp.json()["memory"]["content"] == "User prefers dark mode"

    async def test_add_memory_empty_content(self, test_app, authenticated_client):
        resp = await authenticated_client.post("/api/memories", json={
            "content": "",
        })
        assert resp.status_code == 400

    async def test_list_memories_after_add(self, test_app, authenticated_client):
        await authenticated_client.post("/api/memories", json={"content": "test memory"})
        resp = await authenticated_client.get("/api/memories")
        assert len(resp.json()["memories"]) == 1

    async def test_delete_memory(self, test_app, authenticated_client):
        resp = await authenticated_client.post("/api/memories", json={"content": "to delete"})
        mem_id = resp.json()["memory"]["id"]

        resp = await authenticated_client.delete(f"/api/memories/{mem_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_nonexistent_memory(self, test_app, authenticated_client):
        resp = await authenticated_client.delete("/api/memories/fake_id")
        assert resp.status_code == 404

    async def test_clear_memories(self, test_app, authenticated_client):
        await authenticated_client.post("/api/memories", json={"content": "m1"})
        await authenticated_client.post("/api/memories", json={"content": "m2"})

        resp = await authenticated_client.delete("/api/memories")
        assert resp.status_code == 200
        assert resp.json()["cleared"] == 2

    async def test_memories_unauthorized(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/memories")
        assert resp.status_code == 401


# =====================================================================
# Alter Egos API
# =====================================================================

class TestAlterEgosAPI:
    """Test /api/alter-egos endpoints."""

    async def test_get_alter_egos(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/alter-egos")
        assert resp.status_code == 200
        data = resp.json()
        assert "egos" in data
        assert "active_ego_id" in data
        # Built-in egos should be there
        names = [e["name"] for e in data["egos"]]
        assert "Rain" in names

    async def test_save_alter_ego(self, test_app, authenticated_client):
        ego = {
            "id": "tester",
            "name": "Test Ego",
            "system_prompt": "You are a test ego.",
        }
        resp = await authenticated_client.post("/api/alter-egos", json=ego)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

    async def test_save_alter_ego_invalid_id(self, test_app, authenticated_client):
        ego = {
            "id": "Bad-ID!",
            "name": "Bad",
            "system_prompt": "x",
        }
        resp = await authenticated_client.post("/api/alter-egos", json=ego)
        assert resp.status_code == 400

    async def test_delete_alter_ego(self, test_app, authenticated_client):
        ego = {
            "id": "deleteme",
            "name": "Delete Me",
            "system_prompt": "x",
        }
        await authenticated_client.post("/api/alter-egos", json=ego)

        resp = await authenticated_client.delete("/api/alter-egos/deleteme")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_nonexistent_ego(self, test_app, authenticated_client):
        resp = await authenticated_client.delete("/api/alter-egos/ghost")
        assert resp.status_code == 404

    async def test_cannot_delete_rain_ego(self, test_app, authenticated_client):
        # Ensure builtins exist first (the test has a fresh egos dir)
        import alter_egos.storage as ae_storage
        ae_storage.ensure_builtin_egos()
        resp = await authenticated_client.delete("/api/alter-egos/rain")
        assert resp.status_code == 400

    async def test_alter_egos_unauthorized(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/alter-egos")
        assert resp.status_code == 401


# =====================================================================
# Root and service worker
# =====================================================================

class TestStaticEndpoints:
    """Test static file serving endpoints."""

    async def test_root_serves_html(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/")
        assert resp.status_code == 200

    async def test_service_worker(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/sw.js")
        assert resp.status_code == 200
