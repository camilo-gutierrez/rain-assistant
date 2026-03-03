"""Tests for the Director Projects system.

Covers: project CRUD, limit enforcement, cascade delete, team template
auto-install, project isolation, and backward compatibility.
"""

import json
import time
from unittest.mock import patch, AsyncMock

import pytest

# A role_prompt that passes the 20-char minimum
RP = "You are a test director that handles various automated tasks for the team."


# ===========================================================================
# Project Storage tests
# ===========================================================================


class TestProjectStorage:
    """Tests for directors.storage project CRUD operations."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        """Redirect the DB to a temp directory so tests are isolated."""
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    def test_create_and_get_project(self):
        from directors.storage import create_project, get_project
        p = create_project(name="My Project", user_id="u1", emoji="🚀")
        assert p is not None
        assert p["name"] == "My Project"
        assert p["emoji"] == "🚀"
        assert len(p["id"]) == 8  # UUID[:8]

        fetched = get_project(p["id"], user_id="u1")
        assert fetched is not None
        assert fetched["name"] == "My Project"

    def test_create_project_wrong_user(self):
        from directors.storage import create_project, get_project
        p = create_project(name="P1", user_id="u1")
        fetched = get_project(p["id"], user_id="u2")
        assert fetched is None

    def test_list_projects(self):
        from directors.storage import create_project, list_projects
        create_project(name="P1", user_id="u1")
        create_project(name="P2", user_id="u1")
        create_project(name="P3", user_id="u2")
        assert len(list_projects(user_id="u1")) == 2
        assert len(list_projects(user_id="u2")) == 1

    def test_update_project(self):
        from directors.storage import create_project, update_project
        p = create_project(name="Old Name", user_id="u1")
        updated = update_project(p["id"], user_id="u1", name="New Name", color="#FF0000")
        assert updated is not None
        assert updated["name"] == "New Name"
        assert updated["color"] == "#FF0000"

    def test_update_nonexistent_project(self):
        from directors.storage import update_project
        result = update_project("nonexistent", user_id="u1", name="Foo")
        assert result is None

    def test_delete_project(self):
        from directors.storage import create_project, delete_project, get_project
        p = create_project(name="ToDelete", user_id="u1")
        assert delete_project(p["id"], user_id="u1") is True
        assert get_project(p["id"], user_id="u1") is None

    def test_cannot_delete_default_project(self):
        from directors.storage import delete_project
        assert delete_project("default", user_id="u1") is False

    def test_count_projects(self):
        from directors.storage import create_project, count_projects
        assert count_projects(user_id="u1") == 0
        create_project(name="P1", user_id="u1")
        create_project(name="P2", user_id="u1")
        assert count_projects(user_id="u1") == 2

    def test_project_limit_enforcement(self):
        from directors.storage import create_project, count_projects, MAX_PROJECTS_PER_USER
        for i in range(MAX_PROJECTS_PER_USER):
            p = create_project(name=f"Project {i}", user_id="u1")
            assert p is not None

        # 6th project should fail
        over_limit = create_project(name="Over Limit", user_id="u1")
        assert over_limit is None
        assert count_projects(user_id="u1") == MAX_PROJECTS_PER_USER


# ===========================================================================
# Cascade Delete tests
# ===========================================================================


class TestCascadeDelete:
    """Tests that deleting a project removes all associated data."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    def test_cascade_deletes_directors(self):
        from directors.storage import (
            create_project, delete_project, add_director, list_directors,
        )
        p = create_project(name="Cascade Test", user_id="u1")
        add_director(
            id=f"{p['id']}_strategy", name="Strategy",
            role_prompt=RP, user_id="u1", project_id=p["id"],
        )
        add_director(
            id=f"{p['id']}_content", name="Content",
            role_prompt=RP, user_id="u1", project_id=p["id"],
        )
        assert len(list_directors(user_id="u1", project_id=p["id"])) == 2

        delete_project(p["id"], user_id="u1")
        assert len(list_directors(user_id="u1", project_id=p["id"])) == 0

    def test_cascade_deletes_inbox(self):
        from directors.storage import create_project, delete_project
        from directors.inbox import add_inbox_item, list_inbox
        p = create_project(name="Inbox Test", user_id="u1")
        add_inbox_item(
            director_id="d1", director_name="D1",
            title="Report", content="Hello",
            user_id="u1", project_id=p["id"],
        )
        assert len(list_inbox(user_id="u1", project_id=p["id"])) == 1

        delete_project(p["id"], user_id="u1")
        assert len(list_inbox(user_id="u1", project_id=p["id"])) == 0

    def test_cascade_deletes_tasks(self):
        from directors.storage import create_project, delete_project
        from directors.task_queue import create_task, list_tasks
        p = create_project(name="Task Test", user_id="u1")
        create_task(
            title="Do something", creator_id="d1",
            user_id="u1", project_id=p["id"],
        )
        assert len(list_tasks(user_id="u1", project_id=p["id"])) == 1

        delete_project(p["id"], user_id="u1")
        assert len(list_tasks(user_id="u1", project_id=p["id"])) == 0

    def test_cascade_preserves_other_projects(self):
        from directors.storage import (
            create_project, delete_project, add_director, list_directors,
        )
        p1 = create_project(name="Keep", user_id="u1")
        p2 = create_project(name="Delete", user_id="u1")
        add_director(
            id=f"{p1['id']}_strategy", name="S1",
            role_prompt=RP, user_id="u1", project_id=p1["id"],
        )
        add_director(
            id=f"{p2['id']}_strategy", name="S2",
            role_prompt=RP, user_id="u1", project_id=p2["id"],
        )

        delete_project(p2["id"], user_id="u1")
        # P1's directors should be untouched
        assert len(list_directors(user_id="u1", project_id=p1["id"])) == 1
        # P2's should be gone
        assert len(list_directors(user_id="u1", project_id=p2["id"])) == 0


# ===========================================================================
# Team Template Auto-Install tests
# ===========================================================================


class TestTeamTemplates:
    """Tests for team template definitions and auto-install."""

    def test_team_templates_exist(self):
        from directors.builtin import TEAM_TEMPLATES
        assert len(TEAM_TEMPLATES) >= 4  # At least 4 templates
        ids = [t["id"] for t in TEAM_TEMPLATES]
        assert "digital_business" in ids
        assert "software_dev" in ids
        assert "youtube_creator" in ids
        assert "freelance" in ids
        assert "empty" in ids

    def test_team_template_fields(self):
        from directors.builtin import TEAM_TEMPLATES
        required_fields = {"id", "name", "emoji", "description", "color", "directors"}
        for t in TEAM_TEMPLATES:
            assert required_fields.issubset(t.keys()), f"Template {t['id']} missing fields"

    def test_team_templates_reference_valid_directors(self):
        from directors.builtin import TEAM_TEMPLATES, DIRECTOR_TEMPLATES
        valid_ids = {t["id"] for t in DIRECTOR_TEMPLATES}
        for team in TEAM_TEMPLATES:
            for dir_id in team.get("directors", []):
                assert dir_id in valid_ids, (
                    f"Team '{team['id']}' references unknown director '{dir_id}'"
                )

    def test_get_team_template(self):
        from directors.builtin import get_team_template
        t = get_team_template("digital_business")
        assert t is not None
        assert t["name"] == "Digital Business"
        assert get_team_template("nonexistent") is None

    def test_get_director_template(self):
        from directors.builtin import get_director_template
        d = get_director_template("strategy")
        assert d is not None
        assert d["name"] == "Strategy Director"
        assert get_director_template("nonexistent") is None


# ===========================================================================
# Project Isolation tests
# ===========================================================================


class TestProjectIsolation:
    """Tests that directors/tasks/inbox are properly isolated by project."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    def test_directors_isolated_by_project(self):
        from directors.storage import add_director, list_directors
        add_director(id="p1_s", name="S1", role_prompt=RP, user_id="u1", project_id="proj_a")
        add_director(id="p2_s", name="S2", role_prompt=RP, user_id="u1", project_id="proj_b")
        add_director(id="p3_s", name="S3", role_prompt=RP, user_id="u1", project_id="proj_a")

        assert len(list_directors(user_id="u1", project_id="proj_a")) == 2
        assert len(list_directors(user_id="u1", project_id="proj_b")) == 1
        # Without project filter, returns all
        assert len(list_directors(user_id="u1")) == 3

    def test_tasks_isolated_by_project(self):
        from directors.task_queue import create_task, list_tasks
        create_task(title="T1", creator_id="d1", user_id="u1", project_id="proj_a")
        create_task(title="T2", creator_id="d1", user_id="u1", project_id="proj_b")

        assert len(list_tasks(user_id="u1", project_id="proj_a")) == 1
        assert len(list_tasks(user_id="u1", project_id="proj_b")) == 1

    def test_inbox_isolated_by_project(self):
        from directors.inbox import add_inbox_item, list_inbox, get_unread_count
        add_inbox_item(
            director_id="d1", director_name="D1",
            title="R1", content="Content A",
            user_id="u1", project_id="proj_a",
        )
        add_inbox_item(
            director_id="d1", director_name="D1",
            title="R2", content="Content B",
            user_id="u1", project_id="proj_b",
        )
        add_inbox_item(
            director_id="d1", director_name="D1",
            title="R3", content="Content C",
            user_id="u1", project_id="proj_a",
        )

        assert len(list_inbox(user_id="u1", project_id="proj_a")) == 2
        assert len(list_inbox(user_id="u1", project_id="proj_b")) == 1
        assert get_unread_count(user_id="u1", project_id="proj_a") == 2
        assert get_unread_count(user_id="u1", project_id="proj_b") == 1

    def test_task_stats_by_project(self):
        from directors.task_queue import create_task, get_task_stats
        create_task(title="T1", creator_id="d1", user_id="u1", project_id="proj_a")
        create_task(title="T2", creator_id="d1", user_id="u1", project_id="proj_a")
        create_task(title="T3", creator_id="d1", user_id="u1", project_id="proj_b")

        stats_a = get_task_stats(user_id="u1", project_id="proj_a")
        assert stats_a.get("pending", 0) == 2

        stats_b = get_task_stats(user_id="u1", project_id="proj_b")
        assert stats_b.get("pending", 0) == 1


# ===========================================================================
# Backward Compatibility tests
# ===========================================================================


class TestBackwardCompatibility:
    """Tests that existing data without project_id continues to work."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    def test_directors_default_project(self):
        from directors.storage import add_director, list_directors
        # Creating without explicit project_id should use 'default'
        d = add_director(id="legacy", name="Legacy", role_prompt=RP, user_id="u1")
        assert d is not None

        # Should appear when querying default project
        dirs = list_directors(user_id="u1", project_id="default")
        assert len(dirs) == 1
        assert dirs[0]["id"] == "legacy"

    def test_tasks_default_project(self):
        from directors.task_queue import create_task, list_tasks
        create_task(title="Legacy Task", creator_id="d1", user_id="u1")
        tasks = list_tasks(user_id="u1", project_id="default")
        assert len(tasks) == 1

    def test_inbox_default_project(self):
        from directors.inbox import add_inbox_item, list_inbox
        add_inbox_item(
            director_id="d1", director_name="D1",
            title="Legacy", content="Content",
            user_id="u1",
        )
        items = list_inbox(user_id="u1", project_id="default")
        assert len(items) == 1

    def test_pending_directors_include_project_id(self):
        """Scheduler's get_pending_directors returns project_id in the dict."""
        from directors.storage import add_director, get_pending_directors, _get_db
        import time

        d = add_director(
            id="sched", name="Scheduled", role_prompt=RP,
            schedule="* * * * *", user_id="u1", project_id="proj_x",
        )
        # Force next_run to past
        conn = _get_db()
        conn.execute(
            "UPDATE directors SET next_run = ? WHERE id = ?",
            (time.time() - 60, "sched"),
        )
        conn.commit()
        conn.close()

        pending = get_pending_directors()
        assert len(pending) >= 1
        found = [d for d in pending if d["id"] == "sched"]
        assert len(found) == 1
        assert found[0].get("project_id") == "proj_x"

    def test_migration_idempotent(self):
        """Calling migrate_directors multiple times should not error."""
        from directors.storage import migrate_directors
        result1 = migrate_directors()
        result2 = migrate_directors()
        assert result1["status"] == "ok"
        assert result2["status"] == "ok"


# ===========================================================================
# Projects Meta-tool tests
# ===========================================================================


class TestProjectsMetaTool:
    """Tests for the manage_projects meta-tool."""

    @pytest.fixture(autouse=True)
    def _patch_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "directors.db")
        monkeypatch.setattr("directors.storage.DIRECTORS_DB", db_path)
        from directors.storage import migrate_directors
        migrate_directors()

    @pytest.mark.asyncio
    async def test_create_project(self):
        from directors.projects_tool import handle_manage_projects
        result = await handle_manage_projects(
            {"action": "create", "name": "Test Project", "team_template": "empty", "_user_id": "u1"},
            cwd="/tmp",
        )
        assert result["is_error"] is False
        assert "Test Project" in result["content"]

    @pytest.mark.asyncio
    async def test_create_with_team_template(self):
        from directors.projects_tool import handle_manage_projects
        result = await handle_manage_projects(
            {
                "action": "create",
                "name": "Business",
                "team_template": "digital_business",
                "_user_id": "u1",
            },
            cwd="/tmp",
        )
        assert result["is_error"] is False
        assert "Directors installed" in result["content"]

    @pytest.mark.asyncio
    async def test_list_projects(self):
        from directors.projects_tool import handle_manage_projects
        await handle_manage_projects(
            {"action": "create", "name": "P1", "team_template": "empty", "_user_id": "u1"},
            cwd="/tmp",
        )
        result = await handle_manage_projects(
            {"action": "list", "_user_id": "u1"},
            cwd="/tmp",
        )
        assert result["is_error"] is False
        assert "P1" in result["content"]

    @pytest.mark.asyncio
    async def test_show_project(self):
        from directors.projects_tool import handle_manage_projects
        from directors.storage import list_projects

        await handle_manage_projects(
            {"action": "create", "name": "Show Test", "team_template": "software_dev", "_user_id": "u1"},
            cwd="/tmp",
        )
        projects = list_projects(user_id="u1")
        assert len(projects) == 1

        result = await handle_manage_projects(
            {"action": "show", "project_id": projects[0]["id"], "_user_id": "u1"},
            cwd="/tmp",
        )
        assert result["is_error"] is False
        assert "Show Test" in result["content"]

    @pytest.mark.asyncio
    async def test_delete_project(self):
        from directors.projects_tool import handle_manage_projects
        from directors.storage import list_projects

        await handle_manage_projects(
            {"action": "create", "name": "To Delete", "team_template": "empty", "_user_id": "u1"},
            cwd="/tmp",
        )
        projects = list_projects(user_id="u1")
        result = await handle_manage_projects(
            {"action": "delete", "project_id": projects[0]["id"], "_user_id": "u1"},
            cwd="/tmp",
        )
        assert result["is_error"] is False
        assert "deleted" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_team_templates_action(self):
        from directors.projects_tool import handle_manage_projects
        result = await handle_manage_projects(
            {"action": "team_templates", "_user_id": "u1"},
            cwd="/tmp",
        )
        assert result["is_error"] is False
        assert "Digital Business" in result["content"]

    @pytest.mark.asyncio
    async def test_create_without_name(self):
        from directors.projects_tool import handle_manage_projects
        result = await handle_manage_projects(
            {"action": "create", "_user_id": "u1"},
            cwd="/tmp",
        )
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        from directors.projects_tool import handle_manage_projects
        result = await handle_manage_projects(
            {"action": "fly_to_moon", "_user_id": "u1"},
            cwd="/tmp",
        )
        assert result["is_error"] is True
