"""
Tool executor for non-Claude providers (OpenAI / Gemini).

Executes tools within a sandboxed working directory with permission checks.
"""

import asyncio
from typing import Callable, Awaitable, Any

from .file_ops import read_file, write_file, edit_file, list_directory
from .search_ops import search_files, grep_search
from .bash_ops import run_bash
from .browser_ops import (
    browser_navigate, browser_screenshot, browser_click,
    browser_type, browser_extract_text, browser_scroll, browser_close,
    get_pool as _get_browser_pool,
)

# Permission levels for tools
GREEN_TOOLS = {"read_file", "list_directory", "search_files", "grep_search", "browser_extract_text", "browser_screenshot", "render_surface"}
YELLOW_TOOLS = {"write_file", "edit_file", "browser_navigate", "browser_click", "browser_type", "browser_scroll", "browser_close", "manage_memories", "manage_alter_egos", "manage_scheduled_tasks", "manage_subagents", "manage_marketplace", "manage_documents"}
# bash is classified by command content (handled by permission_callback)


async def _dummy_subagent_handler(args: dict, cwd: str) -> dict:
    """Placeholder until the real handler is injected from server.py."""
    return {
        "content": "Sub-agents require runtime binding. This agent was not initialized with sub-agent support.",
        "is_error": True,
    }


class ToolExecutor:
    """Executes tools in a sandboxed working directory with permission checks."""

    # Tool names that operate on the browser and need agent_id injection
    _BROWSER_TOOLS = frozenset({
        "browser_navigate", "browser_screenshot", "browser_click",
        "browser_type", "browser_extract_text", "browser_scroll",
        "browser_close",
    })

    # Meta-tools that need per-user isolation via _user_id injection
    _META_TOOLS_WITH_USER = frozenset({
        "manage_memories", "manage_alter_egos", "manage_documents",
        "manage_scheduled_tasks", "manage_directors",
    })

    def __init__(
        self,
        cwd: str,
        permission_callback: Callable[[str, str, dict], Awaitable[bool]] | None = None,
        agent_id: str = "default",
        user_id: str = "default",
    ):
        self.cwd = cwd
        self.permission_callback = permission_callback
        self.agent_id = agent_id
        self.user_id = user_id

        self._handlers = {
            "read_file": read_file,
            "write_file": write_file,
            "edit_file": edit_file,
            "bash": run_bash,
            "list_directory": list_directory,
            "search_files": search_files,
            "grep_search": grep_search,
            "browser_navigate": browser_navigate,
            "browser_screenshot": browser_screenshot,
            "browser_click": browser_click,
            "browser_type": browser_type,
            "browser_extract_text": browser_extract_text,
            "browser_scroll": browser_scroll,
            "browser_close": browser_close,
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

        from scheduled_tasks import handle_manage_scheduled_tasks
        from marketplace import handle_manage_marketplace
        from documents import handle_manage_documents
        from a2ui import handle_render_surface
        from directors import handle_manage_directors

        self._handlers["manage_plugins"] = handle_manage_plugins
        self._handlers["manage_memories"] = handle_manage_memories
        self._handlers["manage_alter_egos"] = handle_manage_alter_egos
        self._handlers["manage_scheduled_tasks"] = handle_manage_scheduled_tasks
        self._handlers["manage_marketplace"] = handle_manage_marketplace
        self._handlers["manage_documents"] = handle_manage_documents
        self._handlers["render_surface"] = handle_render_surface
        self._handlers["manage_directors"] = handle_manage_directors
        # manage_subagents handler is injected at runtime from server.py
        # (it requires a bound SubAgentManager + caller agent_id)
        if "manage_subagents" not in self._handlers:
            self._handlers["manage_subagents"] = _dummy_subagent_handler

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
            if not self.permission_callback:
                return {"content": "Permission denied: no permission handler configured.", "is_error": True}
            approved = await self.permission_callback(tool_name, tool_name, arguments)
            if not approved:
                return {"content": "Permission denied by user.", "is_error": True}

        try:
            # Inject agent_id for browser tools so each agent gets its own page
            if tool_name in self._BROWSER_TOOLS:
                arguments = {**arguments, "_agent_id": self.agent_id}
            # Inject user_id for meta-tools that need per-user isolation
            if tool_name in self._META_TOOLS_WITH_USER:
                arguments = {**arguments, "_user_id": self.user_id}
            return await handler(arguments, self.cwd)
        except Exception as e:
            return {"content": f"Tool execution error: {e}", "is_error": True}

    async def cleanup(self) -> None:
        """Release resources held by this executor (e.g. browser page)."""
        try:
            await _get_browser_pool().release(self.agent_id)
        except Exception:
            pass
