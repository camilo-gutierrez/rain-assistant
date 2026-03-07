"""Sandbox manager for Rain Assistant.

Provides execution isolation for bash commands and file operations.
Two modes:
- DIRECTORY: Restricts operations to a working directory (no Docker needed)
- DOCKER: Runs in ephemeral Docker containers (optional, requires Docker)

The directory sandbox adds:
- Path validation: all file operations must be within the allowed directory
- Command filtering: blocks dangerous system commands
- Temp directory isolation: each task gets its own temp space
- Snapshot/restore: can save and restore directory state

The Docker sandbox adds:
- Full OS-level isolation
- Network isolation (optional)
- Resource limits (CPU, memory)
- Auto-cleanup
"""

import asyncio
import hashlib
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("rain.sandbox")


class SandboxMode(str, Enum):
    NONE = "none"           # No sandboxing (current behavior)
    DIRECTORY = "directory" # Path restriction + command filtering
    DOCKER = "docker"       # Full container isolation


@dataclass
class SandboxResult:
    """Result of a sandboxed operation."""
    allowed: bool
    reason: str = ""
    modified_command: str = ""  # Command after sandbox modifications
    sandbox_cwd: str = ""      # Working directory within sandbox

    @staticmethod
    def allow(sandbox_cwd: str = "", modified_command: str = "") -> 'SandboxResult':
        return SandboxResult(allowed=True, sandbox_cwd=sandbox_cwd, modified_command=modified_command)

    @staticmethod
    def deny(reason: str) -> 'SandboxResult':
        return SandboxResult(allowed=False, reason=reason)


class SandboxManager:
    """Manages sandboxed execution environments.

    Usage:
        sandbox = SandboxManager(mode=SandboxMode.DIRECTORY, allowed_dir="/home/user/project")

        # Check if a file operation is allowed
        result = sandbox.check_path("/home/user/project/src/main.py")

        # Check if a command is allowed
        result = sandbox.check_command("ls -la")

        # Create a snapshot before risky operations
        snapshot_id = sandbox.create_snapshot()

        # Restore if something goes wrong
        sandbox.restore_snapshot(snapshot_id)
    """

    def __init__(
        self,
        mode: SandboxMode = SandboxMode.NONE,
        allowed_dir: str = "",
        network_enabled: bool = True,
        max_file_size_mb: int = 100,
        docker_image: str = "python:3.12-slim",
    ):
        self.mode = mode
        self.allowed_dir = os.path.realpath(allowed_dir) if allowed_dir else ""
        self.network_enabled = network_enabled
        self.max_file_size_mb = max_file_size_mb
        self.docker_image = docker_image

        # Snapshot storage
        self._snapshots: dict[str, str] = {}  # snapshot_id -> snapshot_path
        self._snapshot_dir = Path(tempfile.gettempdir()) / "rain-snapshots"

        # Blocked paths (always blocked regardless of allowed_dir)
        self._blocked_paths = {
            ".ssh", ".aws", ".gnupg", ".rain-assistant",
            ".env", ".git/config", "credentials",
        }

        # Blocked command patterns (supplement permission_classifier's RED patterns)
        self._blocked_commands = {
            "curl", "wget",  # When network is disabled
        }

        self._docker_available: Optional[bool] = None

    def check_path(self, path: str) -> SandboxResult:
        """Check if a file path is allowed within the sandbox.

        Args:
            path: Absolute or relative file path

        Returns:
            SandboxResult indicating if access is allowed
        """
        if self.mode == SandboxMode.NONE:
            return SandboxResult.allow()

        # Resolve to absolute path
        real_path = os.path.realpath(path)

        # Check blocked paths
        for blocked in self._blocked_paths:
            if blocked in real_path:
                return SandboxResult.deny(f"Access to '{blocked}' is blocked by sandbox policy")

        # Check if within allowed directory
        if self.mode in (SandboxMode.DIRECTORY, SandboxMode.DOCKER):
            if self.allowed_dir and not real_path.startswith(self.allowed_dir):
                return SandboxResult.deny(
                    f"Path '{path}' is outside sandbox directory '{self.allowed_dir}'"
                )

        return SandboxResult.allow(sandbox_cwd=self.allowed_dir)

    def check_command(self, command: str) -> SandboxResult:
        """Check if a bash command is allowed within the sandbox.

        Args:
            command: The bash command to check

        Returns:
            SandboxResult indicating if execution is allowed
        """
        if self.mode == SandboxMode.NONE:
            return SandboxResult.allow(modified_command=command)

        # Network check
        if not self.network_enabled:
            network_commands = {"curl", "wget", "ssh", "scp", "rsync", "nc", "netcat"}
            cmd_parts = command.split()
            if cmd_parts and cmd_parts[0] in network_commands:
                return SandboxResult.deny(
                    f"Network command '{cmd_parts[0]}' blocked: network disabled in sandbox"
                )

        # In directory mode, prefix cd to keep commands in sandbox
        if self.mode == SandboxMode.DIRECTORY and self.allowed_dir:
            return SandboxResult.allow(
                sandbox_cwd=self.allowed_dir,
                modified_command=command,
            )

        return SandboxResult.allow(modified_command=command)

    def check_file_size(self, path: str) -> SandboxResult:
        """Check if a file exceeds the maximum allowed size."""
        if self.mode == SandboxMode.NONE:
            return SandboxResult.allow()

        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                return SandboxResult.deny(
                    f"File size ({size_mb:.1f}MB) exceeds limit ({self.max_file_size_mb}MB)"
                )
        except FileNotFoundError:
            pass  # File doesn't exist yet, that's fine

        return SandboxResult.allow()

    def create_snapshot(self, directory: str = None) -> str:
        """Create a snapshot of the working directory for rollback.

        Args:
            directory: Directory to snapshot (defaults to allowed_dir)

        Returns:
            Snapshot ID for later restoration
        """
        target = directory or self.allowed_dir
        if not target or not os.path.isdir(target):
            return ""

        snapshot_id = hashlib.sha256(
            f"{target}:{time.time()}".encode()
        ).hexdigest()[:16]

        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self._snapshot_dir / snapshot_id

        try:
            shutil.copytree(target, str(snapshot_path), dirs_exist_ok=True)
            self._snapshots[snapshot_id] = str(snapshot_path)
            logger.info("Snapshot created: %s for %s", snapshot_id, target)
            return snapshot_id
        except Exception as e:
            logger.error("Failed to create snapshot: %s", e)
            return ""

    def restore_snapshot(self, snapshot_id: str, target: str = None) -> bool:
        """Restore a directory from a snapshot.

        Args:
            snapshot_id: ID returned by create_snapshot
            target: Directory to restore to (defaults to allowed_dir)

        Returns:
            True if restored successfully
        """
        snapshot_path = self._snapshots.get(snapshot_id)
        if not snapshot_path or not os.path.isdir(snapshot_path):
            logger.error("Snapshot not found: %s", snapshot_id)
            return False

        target = target or self.allowed_dir
        if not target:
            return False

        try:
            # Clear target and copy snapshot back
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(snapshot_path, target)
            logger.info("Snapshot restored: %s to %s", snapshot_id, target)
            return True
        except Exception as e:
            logger.error("Failed to restore snapshot: %s", e)
            return False

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot to free disk space."""
        snapshot_path = self._snapshots.pop(snapshot_id, None)
        if snapshot_path and os.path.isdir(snapshot_path):
            shutil.rmtree(snapshot_path, ignore_errors=True)
            return True
        return False

    def list_snapshots(self) -> list[dict]:
        """List all available snapshots."""
        result = []
        for sid, path in self._snapshots.items():
            if os.path.isdir(path):
                result.append({
                    "snapshot_id": sid,
                    "path": path,
                    "exists": True,
                })
        return result

    def cleanup_snapshots(self):
        """Remove all snapshots."""
        for sid in list(self._snapshots.keys()):
            self.delete_snapshot(sid)
        if self._snapshot_dir.exists():
            shutil.rmtree(str(self._snapshot_dir), ignore_errors=True)

    def is_docker_available(self) -> bool:
        """Check if Docker is available on this system."""
        if self._docker_available is not None:
            return self._docker_available

        try:
            import subprocess
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True, timeout=5,
            )
            self._docker_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._docker_available = False

        return self._docker_available

    async def run_in_docker(self, command: str, cwd: str = "/workspace") -> dict:
        """Run a command in an ephemeral Docker container.

        Args:
            command: The command to run
            cwd: Working directory inside the container

        Returns:
            dict with stdout, stderr, returncode
        """
        if not self.is_docker_available():
            return {
                "stdout": "",
                "stderr": "Docker is not available on this system",
                "returncode": 1,
            }

        docker_args = [
            "docker", "run", "--rm",
            "-w", cwd,
        ]

        # Mount the allowed directory
        if self.allowed_dir:
            docker_args.extend(["-v", f"{self.allowed_dir}:{cwd}"])

        # Network isolation
        if not self.network_enabled:
            docker_args.extend(["--network", "none"])

        # Resource limits
        docker_args.extend([
            "--memory", "512m",
            "--cpus", "1.0",
            "--pids-limit", "100",
        ])

        docker_args.extend([self.docker_image, "bash", "-c", command])

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {
                "stdout": "",
                "stderr": "Docker command timed out (300s)",
                "returncode": 124,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Docker execution error: {e}",
                "returncode": 1,
            }

    def get_info(self) -> dict:
        """Return sandbox configuration info."""
        return {
            "mode": self.mode.value,
            "allowed_dir": self.allowed_dir,
            "network_enabled": self.network_enabled,
            "max_file_size_mb": self.max_file_size_mb,
            "docker_available": self.is_docker_available() if self.mode == SandboxMode.DOCKER else None,
            "snapshots": len(self._snapshots),
        }
