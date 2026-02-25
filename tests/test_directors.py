"""Tests for the Autonomous Directors system.

Covers: storage, task_queue, inbox, meta_tool, and builtin templates.
"""

import json
import time
from unittest.mock import patch, AsyncMock

import pytest

# A role_prompt that passes the 20-char minimum
RP = "You are a test director that handles various automated tasks for the team."


# ===========================================================================
# Storage tests
# ===========================================================================


class TestDirectorStorage:
    """Tests for directors.storage CRUD operations."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        """Redirect the DB to a temp directory so tests are isolated."""
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    def test_add_and_get(self):
        from directors.storage import add_director, get_director
        d = add_director(
            id="test_dir",
            name="Test Director",
            role_prompt=RP,
            user_id="u1",
        )
        assert d["id"] == "test_dir"
        assert d["name"] == "Test Director"
        assert d["enabled"] is True

        fetched = get_director("test_dir", user_id="u1")
        assert fetched is not None
        assert fetched["id"] == "test_dir"

    def test_add_duplicate_returns_none(self):
        from directors.storage import add_director
        add_director(id="dup", name="A", role_prompt=RP, user_id="u1")
        result = add_director(id="dup", name="B", role_prompt=RP, user_id="u1")
        assert result is None

    def test_list_directors(self):
        from directors.storage import add_director, list_directors
        add_director(id="d1", name="D1", role_prompt=RP, user_id="u1")
        add_director(id="d2", name="D2", role_prompt=RP, user_id="u1")
        add_director(id="d3", name="D3", role_prompt=RP, user_id="u2")
        assert len(list_directors(user_id="u1")) == 2
        assert len(list_directors(user_id="u2")) == 1

    def test_update_director(self):
        from directors.storage import add_director, update_director, get_director
        add_director(id="upd", name="Old", role_prompt=RP, user_id="u1")
        update_director("upd", user_id="u1", name="New")
        d = get_director("upd", user_id="u1")
        assert d["name"] == "New"

    def test_delete_director(self):
        from directors.storage import add_director, delete_director, get_director
        add_director(id="del", name="D", role_prompt=RP, user_id="u1")
        assert delete_director("del", user_id="u1") is True
        assert get_director("del", user_id="u1") is None

    def test_delete_nonexistent(self):
        from directors.storage import delete_director
        assert delete_director("nope", user_id="u1") is False

    def test_enable_disable(self):
        from directors.storage import add_director, enable_director, disable_director, get_director
        add_director(id="tog", name="T", role_prompt=RP, user_id="u1")
        disable_director("tog", user_id="u1")
        assert get_director("tog", user_id="u1")["enabled"] is False
        enable_director("tog", user_id="u1")
        assert get_director("tog", user_id="u1")["enabled"] is True

    def test_update_context(self):
        from directors.storage import add_director, update_context, get_director
        add_director(id="ctx", name="C", role_prompt=RP, user_id="u1")
        update_context("ctx", user_id="u1", key="mykey", value="myvalue")
        d = get_director("ctx", user_id="u1")
        assert d["context_window"]["mykey"] == "myvalue"

    def test_mark_director_run(self):
        from directors.storage import add_director, mark_director_run, get_director
        add_director(id="run", name="R", role_prompt=RP, user_id="u1")
        mark_director_run("run", result="done", error=None, cost=0.05)
        d = get_director("run", user_id="u1")
        assert d["run_count"] == 1
        assert d["total_cost"] == pytest.approx(0.05)
        assert d["last_result"] == "done"
        assert d["last_error"] is None

    def test_get_pending_directors_none(self):
        from directors.storage import add_director, get_pending_directors
        # Director with no schedule should not appear
        add_director(id="nosched", name="N", role_prompt=RP, user_id="u1")
        pending = get_pending_directors()
        assert all(p["id"] != "nosched" for p in pending)

    def test_json_fields_parsed(self):
        from directors.storage import add_director, get_director
        add_director(
            id="json_test",
            name="J",
            role_prompt=RP,
            tools_allowed=["bash", "read_file"],
            plugins_allowed=["*"],
            user_id="u1",
        )
        d = get_director("json_test", user_id="u1")
        assert d["tools_allowed"] == ["bash", "read_file"]
        assert d["plugins_allowed"] == ["*"]
        assert isinstance(d["context_window"], dict)


# ===========================================================================
# Task Queue tests
# ===========================================================================


class TestTaskQueue:
    """Tests for directors.task_queue operations."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    def test_create_and_get(self):
        from directors.task_queue import create_task, get_task
        t = create_task(
            title="Test task",
            creator_id="strategy",
            assignee_id="content",
            user_id="u1",
        )
        assert t["title"] == "Test task"
        assert t["status"] == "pending"
        fetched = get_task(t["id"], user_id="u1")
        assert fetched is not None
        assert fetched["creator_id"] == "strategy"

    def test_list_tasks(self):
        from directors.task_queue import create_task, list_tasks
        create_task(title="T1", creator_id="a", user_id="u1")
        create_task(title="T2", creator_id="b", user_id="u1")
        create_task(title="T3", creator_id="c", user_id="u2")
        assert len(list_tasks(user_id="u1")) == 2

    def test_claim_task(self):
        from directors.task_queue import create_task, claim_task, get_task
        t = create_task(title="Claim me", creator_id="a", assignee_id="b", user_id="u1")
        result = claim_task(t["id"], "b", user_id="u1")
        assert result is not None
        fetched = get_task(t["id"], user_id="u1")
        assert fetched["status"] == "running"
        assert fetched["claimed_by"] == "b"

    def test_claim_already_running(self):
        from directors.task_queue import create_task, claim_task
        t = create_task(title="X", creator_id="a", user_id="u1")
        claim_task(t["id"], "b", user_id="u1")
        # Already running, so second claim should fail
        result = claim_task(t["id"], "c", user_id="u1")
        assert result is None

    def test_complete_task(self):
        from directors.task_queue import create_task, claim_task, complete_task, get_task
        t = create_task(title="Do it", creator_id="a", user_id="u1")
        claim_task(t["id"], "b", user_id="u1")
        complete_task(t["id"], {"result": "all good"}, user_id="u1")
        fetched = get_task(t["id"], user_id="u1")
        assert fetched["status"] == "completed"
        assert fetched["completed_at"] is not None

    def test_fail_task_with_retry(self):
        from directors.task_queue import create_task, claim_task, fail_task, get_task
        t = create_task(title="Fail me", creator_id="a", user_id="u1")
        claim_task(t["id"], "b", user_id="u1")
        fail_task(t["id"], "oops", user_id="u1")
        fetched = get_task(t["id"], user_id="u1")
        # Should retry (back to pending) since retry_count < max_retries
        assert fetched["status"] == "pending"
        assert fetched["retry_count"] == 1

    def test_fail_task_exhausted_retries(self):
        from directors.task_queue import create_task, claim_task, fail_task, get_task
        t = create_task(title="Exhaust", creator_id="a", user_id="u1")
        # Exhaust retries (default max_retries=2, so 3 fails should exhaust)
        for _ in range(3):
            claim_task(t["id"], "b", user_id="u1")
            fail_task(t["id"], "nope", user_id="u1")
        fetched = get_task(t["id"], user_id="u1")
        assert fetched["status"] == "failed"

    def test_cancel_task(self):
        from directors.task_queue import create_task, cancel_task, get_task
        t = create_task(title="Cancel me", creator_id="a", user_id="u1")
        cancel_task(t["id"], user_id="u1")
        assert get_task(t["id"], user_id="u1")["status"] == "cancelled"

    def test_get_ready_tasks_respects_dependencies(self):
        from directors.task_queue import create_task, complete_task, claim_task, get_ready_tasks
        t1 = create_task(title="First", creator_id="a", assignee_id="b", user_id="u1")
        t2 = create_task(title="Second", creator_id="a", assignee_id="b",
                         depends_on=[t1["id"]], user_id="u1")
        # t2 should NOT be ready (depends on t1)
        ready = get_ready_tasks(user_id="u1")
        ready_ids = [r["id"] for r in ready]
        assert t1["id"] in ready_ids
        assert t2["id"] not in ready_ids

        # Complete t1 -> t2 should become ready
        claim_task(t1["id"], "b", user_id="u1")
        complete_task(t1["id"], {}, user_id="u1")
        ready = get_ready_tasks(user_id="u1")
        ready_ids = [r["id"] for r in ready]
        assert t2["id"] in ready_ids

    def test_get_task_stats(self):
        from directors.task_queue import create_task, claim_task, complete_task, get_task_stats
        create_task(title="A", creator_id="x", user_id="u1")
        t2 = create_task(title="B", creator_id="x", user_id="u1")
        claim_task(t2["id"], "y", user_id="u1")
        complete_task(t2["id"], {}, user_id="u1")
        stats = get_task_stats(user_id="u1")
        assert stats["pending"] == 1
        assert stats["completed"] == 1


# ===========================================================================
# Inbox tests
# ===========================================================================


class TestInbox:
    """Tests for directors.inbox operations."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    def test_add_and_get(self):
        from directors.inbox import add_inbox_item, get_inbox_item
        item = add_inbox_item(
            director_id="strategy",
            director_name="Strategy",
            title="Daily Report",
            content="# Report\n\nAll good.",
            content_type="report",
            user_id="u1",
        )
        assert item["title"] == "Daily Report"
        assert item["status"] == "unread"
        fetched = get_inbox_item(item["id"], user_id="u1")
        assert fetched is not None
        assert fetched["content"] == "# Report\n\nAll good."

    def test_list_inbox(self):
        from directors.inbox import add_inbox_item, list_inbox
        add_inbox_item(director_id="a", director_name="A", title="T1",
                       content="c", user_id="u1")
        add_inbox_item(director_id="b", director_name="B", title="T2",
                       content="c", user_id="u1")
        add_inbox_item(director_id="c", director_name="C", title="T3",
                       content="c", user_id="u2")
        items = list_inbox(user_id="u1")
        assert len(items) == 2

    def test_list_inbox_filter_by_status(self):
        from directors.inbox import add_inbox_item, list_inbox, update_inbox_status
        i1 = add_inbox_item(director_id="a", director_name="A", title="T1",
                            content="c", user_id="u1")
        add_inbox_item(director_id="b", director_name="B", title="T2",
                       content="c", user_id="u1")
        update_inbox_status(i1["id"], "read", user_id="u1")
        unread = list_inbox(status="unread", user_id="u1")
        assert len(unread) == 1

    def test_update_status(self):
        from directors.inbox import add_inbox_item, update_inbox_status, get_inbox_item
        item = add_inbox_item(director_id="a", director_name="A", title="T",
                              content="c", user_id="u1")
        update_inbox_status(item["id"], "approved", user_comment="LGTM", user_id="u1")
        fetched = get_inbox_item(item["id"], user_id="u1")
        assert fetched["status"] == "approved"
        assert fetched["user_comment"] == "LGTM"

    def test_get_unread_count(self):
        from directors.inbox import add_inbox_item, get_unread_count, update_inbox_status
        add_inbox_item(director_id="a", director_name="A", title="T1",
                       content="c", user_id="u1")
        i2 = add_inbox_item(director_id="b", director_name="B", title="T2",
                            content="c", user_id="u1")
        assert get_unread_count(user_id="u1") == 2
        update_inbox_status(i2["id"], "read", user_id="u1")
        assert get_unread_count(user_id="u1") == 1

    def test_list_inbox_filter_by_director(self):
        from directors.inbox import add_inbox_item, list_inbox
        add_inbox_item(director_id="strategy", director_name="S", title="T1",
                       content="c", user_id="u1")
        add_inbox_item(director_id="content", director_name="C", title="T2",
                       content="c", user_id="u1")
        items = list_inbox(director_id="strategy", user_id="u1")
        assert len(items) == 1
        assert items[0]["director_id"] == "strategy"

    def test_list_inbox_filter_by_content_type(self):
        from directors.inbox import add_inbox_item, list_inbox
        add_inbox_item(director_id="a", director_name="A", title="T1",
                       content="c", content_type="report", user_id="u1")
        add_inbox_item(director_id="b", director_name="B", title="T2",
                       content="c", content_type="code", user_id="u1")
        items = list_inbox(content_type="code", user_id="u1")
        assert len(items) == 1
        assert items[0]["content_type"] == "code"


# ===========================================================================
# Meta-tool tests
# ===========================================================================


class TestMetaTool:
    """Tests for directors.meta_tool.handle_manage_directors."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    @pytest.mark.asyncio
    async def test_create_action(self):
        from directors.meta_tool import handle_manage_directors
        result = await handle_manage_directors({
            "action": "create",
            "id": "testmeta",
            "name": "Meta Director",
            "role_prompt": RP,
            "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False
        assert "testmeta" in result["content"]

    @pytest.mark.asyncio
    async def test_list_action(self):
        from directors.meta_tool import handle_manage_directors
        await handle_manage_directors({
            "action": "create", "id": "listone", "name": "L1",
            "role_prompt": RP, "_user_id": "u1",
        }, "/tmp")
        result = await handle_manage_directors({
            "action": "list", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False
        assert "listone" in result["content"]

    @pytest.mark.asyncio
    async def test_show_action(self):
        from directors.meta_tool import handle_manage_directors
        await handle_manage_directors({
            "action": "create", "id": "showone", "name": "S1",
            "role_prompt": RP, "_user_id": "u1",
        }, "/tmp")
        result = await handle_manage_directors({
            "action": "show", "id": "showone", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False
        assert "S1" in result["content"]

    @pytest.mark.asyncio
    async def test_delete_action(self):
        from directors.meta_tool import handle_manage_directors
        await handle_manage_directors({
            "action": "create", "id": "delone", "name": "D1",
            "role_prompt": RP, "_user_id": "u1",
        }, "/tmp")
        result = await handle_manage_directors({
            "action": "delete", "id": "delone", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False
        # Verify it's gone
        result = await handle_manage_directors({
            "action": "show", "id": "delone", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_enable_disable_actions(self):
        from directors.meta_tool import handle_manage_directors
        await handle_manage_directors({
            "action": "create", "id": "togone", "name": "T",
            "role_prompt": RP, "_user_id": "u1",
        }, "/tmp")
        result = await handle_manage_directors({
            "action": "disable", "id": "togone", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False
        result = await handle_manage_directors({
            "action": "enable", "id": "togone", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_templates_action(self):
        from directors.meta_tool import handle_manage_directors
        result = await handle_manage_directors({
            "action": "templates", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False
        assert "strategy" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_set_context_action(self):
        from directors.meta_tool import handle_manage_directors
        from directors.storage import get_director
        await handle_manage_directors({
            "action": "create", "id": "ctxone", "name": "C",
            "role_prompt": RP, "_user_id": "u1",
        }, "/tmp")
        result = await handle_manage_directors({
            "action": "set_context", "id": "ctxone",
            "context_key": "note",
            "context_value": "remember this",
            "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False
        d = get_director("ctxone", user_id="u1")
        assert d["context_window"]["note"] == "remember this"

    @pytest.mark.asyncio
    async def test_create_missing_fields(self):
        from directors.meta_tool import handle_manage_directors
        result = await handle_manage_directors({
            "action": "create", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        from directors.meta_tool import handle_manage_directors
        result = await handle_manage_directors({
            "action": "explode", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_run_now_action(self):
        from directors.meta_tool import handle_manage_directors
        # Create without schedule first (manual director), then enable + run
        await handle_manage_directors({
            "action": "create", "id": "runnow", "name": "R",
            "role_prompt": RP,
            "_user_id": "u1",
        }, "/tmp")
        result = await handle_manage_directors({
            "action": "run_now", "id": "runnow", "_user_id": "u1",
        }, "/tmp")
        assert result["is_error"] is False


# ===========================================================================
# Builtin templates tests
# ===========================================================================


class TestBuiltinTemplates:
    """Tests for directors.builtin template library."""

    def test_templates_exist(self):
        from directors.builtin import DIRECTOR_TEMPLATES
        assert len(DIRECTOR_TEMPLATES) >= 5
        ids = [t["id"] for t in DIRECTOR_TEMPLATES]
        assert "strategy" in ids
        assert "content" in ids
        assert "development" in ids

    def test_template_fields(self):
        from directors.builtin import DIRECTOR_TEMPLATES
        for tmpl in DIRECTOR_TEMPLATES:
            assert "id" in tmpl
            assert "name" in tmpl
            assert "emoji" in tmpl
            assert "role_prompt" in tmpl
            assert len(tmpl["role_prompt"]) > 50  # Should be substantial
