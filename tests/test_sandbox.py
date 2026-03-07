"""Tests for the sandbox module."""

import os
import pytest
from pathlib import Path
from sandbox import SandboxManager, SandboxMode, SandboxResult


class TestSandboxResult:
    def test_allow(self):
        r = SandboxResult.allow()
        assert r.allowed is True

    def test_deny(self):
        r = SandboxResult.deny("blocked")
        assert r.allowed is False
        assert r.reason == "blocked"


class TestSandboxNoneMode:
    """In NONE mode, everything is allowed."""

    def test_check_path_allows_all(self):
        sb = SandboxManager(mode=SandboxMode.NONE)
        assert sb.check_path("/etc/passwd").allowed is True

    def test_check_command_allows_all(self):
        sb = SandboxManager(mode=SandboxMode.NONE)
        assert sb.check_command("rm -rf /").allowed is True

    def test_check_file_size_allows_all(self):
        sb = SandboxManager(mode=SandboxMode.NONE)
        assert sb.check_file_size("/nonexistent").allowed is True


class TestSandboxDirectoryMode:
    def test_path_within_allowed(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        result = sb.check_path(str(tmp_path / "file.txt"))
        assert result.allowed is True

    def test_path_outside_allowed(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        result = sb.check_path("/etc/passwd")
        assert result.allowed is False
        assert "outside sandbox" in result.reason

    def test_blocked_path_ssh(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        result = sb.check_path(str(tmp_path / ".ssh" / "id_rsa"))
        assert result.allowed is False
        assert ".ssh" in result.reason

    def test_blocked_path_aws(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        result = sb.check_path(str(tmp_path / ".aws" / "credentials"))
        assert result.allowed is False

    def test_command_allowed(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        result = sb.check_command("ls -la")
        assert result.allowed is True

    def test_network_command_blocked(self, tmp_path):
        sb = SandboxManager(
            mode=SandboxMode.DIRECTORY,
            allowed_dir=str(tmp_path),
            network_enabled=False,
        )
        result = sb.check_command("curl https://example.com")
        assert result.allowed is False
        assert "network" in result.reason.lower()

    def test_network_command_allowed_when_enabled(self, tmp_path):
        sb = SandboxManager(
            mode=SandboxMode.DIRECTORY,
            allowed_dir=str(tmp_path),
            network_enabled=True,
        )
        result = sb.check_command("curl https://example.com")
        assert result.allowed is True

    def test_file_size_under_limit(self, tmp_path):
        f = tmp_path / "small.txt"
        f.write_text("hello")
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        assert sb.check_file_size(str(f)).allowed is True

    def test_file_size_nonexistent(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        assert sb.check_file_size(str(tmp_path / "nope.txt")).allowed is True


class TestSnapshots:
    def test_create_and_list(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        (work_dir / "file.txt").write_text("original")

        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(work_dir))
        sid = sb.create_snapshot()

        assert sid != ""
        assert len(sb.list_snapshots()) == 1

    def test_restore_snapshot(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        (work_dir / "file.txt").write_text("original")

        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(work_dir))
        sid = sb.create_snapshot()

        # Modify the file
        (work_dir / "file.txt").write_text("modified")
        assert (work_dir / "file.txt").read_text() == "modified"

        # Restore
        assert sb.restore_snapshot(sid) is True
        assert (work_dir / "file.txt").read_text() == "original"

    def test_delete_snapshot(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        (work_dir / "f.txt").write_text("x")

        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(work_dir))
        sid = sb.create_snapshot()
        assert sb.delete_snapshot(sid) is True
        assert len(sb.list_snapshots()) == 0

    def test_restore_nonexistent(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        assert sb.restore_snapshot("nonexistent") is False

    def test_cleanup_all(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        (work_dir / "f.txt").write_text("x")

        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(work_dir))
        sb.create_snapshot()
        sb.create_snapshot()
        sb.cleanup_snapshots()
        assert len(sb.list_snapshots()) == 0


class TestSandboxInfo:
    def test_get_info_none(self):
        sb = SandboxManager(mode=SandboxMode.NONE)
        info = sb.get_info()
        assert info["mode"] == "none"

    def test_get_info_directory(self, tmp_path):
        sb = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir=str(tmp_path))
        info = sb.get_info()
        assert info["mode"] == "directory"
        assert info["allowed_dir"] == str(tmp_path)


class TestDockerSandbox:
    def test_docker_not_available_returns_error(self):
        sb = SandboxManager(mode=SandboxMode.DOCKER)
        sb._docker_available = False
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            sb.run_in_docker("echo hello")
        )
        assert result["returncode"] == 1
        assert "not available" in result["stderr"]
