"""
Tool executor for non-Claude providers (OpenAI / Gemini).

Executes tools within a sandboxed working directory with permission checks.
"""

import asyncio
from typing import Callable, Awaitable, Any

from .file_ops import read_file, write_file, edit_file, list_directory
from .search_ops import search_files, grep_search
from .bash_ops import run_bash

# Permission levels for tools
GREEN_TOOLS = {"read_file", "list_directory", "search_files", "grep_search", "manage_memories", "manage_alter_egos"}
YELLOW_TOOLS = {"write_file", "edit_file"}
# bash is classified by command content (handled by permission_callback)


class ToolExecutor:
    """Executes tools in a sandboxed working directory with permission checks."""

    def __init__(
        self,
        cwd: str,
        permission_callback: Callable[[str, str, dict], Awaitable[bool]] | None = None,
    ):
        self.cwd = cwd
        self.permission_callback = permission_callback

        self._handlers = {
            "read_file": read_file,
            "write_file": write_file,
            "edit_file": edit_file,
            "bash": run_bash,
            "list_directory": list_directory,
            "search_files": search_files,
            "grep_search": grep_search,
        }

        # Register plugin handlers
        self._load_plugin_handlers()

    def _load_plugin_handlers(self) -> None:
        """Load plugin handlers, meta-tools, and Rain system tools."""
        from plugins import (
            load_all_plugins, execute_plugin,
            handle_manage_plugins, clear_reload_flag,
        )
        from memories import handle_manage_memories
        from alter_egos import handle_manage_alter_egos

        self._handlers["manage_plugins"] = handle_manage_plugins
        self._handlers["manage_memories"] = handle_manage_memories
        self._handlers["manage_alter_egos"] = handle_manage_alter_egos

        for plugin in load_all_plugins():
            tool_name = f"plugin_{plugin.name}"
            # Capture plugin in closure to avoid late binding
            self._handlers[tool_name] = (
                lambda args, cwd, p=plugin: execute_plugin(p, args, cwd)
            )

        clear_reload_flag()

    def reload_plugin_handlers(self) -> None:
        """Reload plugin handlers (called after manage_plugins creates/modifies plugins)."""
        # Remove old plugin handlers
        to_remove = [k for k in self._handlers if k.startswith("plugin_")]
        for k in to_remove:
            del self._handlers[k]

        self._load_plugin_handlers()

    def _is_green_plugin(self, tool_name: str) -> bool:
        """Check if a plugin tool has green permission level."""
        if not tool_name.startswith("plugin_"):
            return False
        from plugins import load_all_plugins
        plugin_name = tool_name[7:]  # Remove "plugin_" prefix
        for p in load_all_plugins():
            if p.name == plugin_name and p.permission_level == "green":
                return True
        return False

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return {content: str, is_error: bool}.

        Checks permissions before executing write/dangerous operations.
        """
        # Check if plugins need reloading
        from plugins import is_reload_needed
        if is_reload_needed():
            self.reload_plugin_handlers()

        handler = self._handlers.get(tool_name)
        if not handler:
            return {"content": f"Error: Unknown tool '{tool_name}'", "is_error": True}

        # Check permissions for non-green tools
        if tool_name not in GREEN_TOOLS and not self._is_green_plugin(tool_name):
            if self.permission_callback:
                approved = await self.permission_callback(tool_name, tool_name, arguments)
                if not approved:
                    return {"content": "Permission denied by user.", "is_error": True}

        try:
            return await handler(arguments, self.cwd)
        except Exception as e:
            return {"content": f"Tool execution error: {e}", "is_error": True}
