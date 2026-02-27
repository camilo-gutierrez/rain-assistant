"""
Permission classifier for Rain Assistant Security.

Classifies tool usage into security levels:
- GREEN:    Read-only operations, auto-approved
- YELLOW:   Write operations, require user confirmation
- RED:      Dangerous operations, require PIN confirmation
- COMPUTER: Computer Use actions, require confirmation (default for screen control)
"""

import re
from enum import Enum
from typing import Any


class PermissionLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    COMPUTER = "computer"


# ──────────────────────────────────────────────────────────────
# Tool classification tables
# ──────────────────────────────────────────────────────────────

# Tools that are always safe (read-only)
GREEN_TOOLS: set[str] = {
    "Read",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "TodoWrite",
    "Task",
    "browser_extract_text",
    "browser_screenshot",
    "manage_subagents",
    "manage_marketplace",
    "render_surface",
}

# Tools that modify files (require confirmation)
YELLOW_TOOLS: set[str] = {
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_close",
}

# Bash is special: classified by command content (see below)
# Any unknown tool defaults to YELLOW


# ──────────────────────────────────────────────────────────────
# Dangerous Bash patterns (RED level)
# ──────────────────────────────────────────────────────────────

DANGEROUS_PATTERNS: list[re.Pattern] = [
    # File deletion
    re.compile(r"\brm\s+(-[a-zA-Z]*[rf])", re.IGNORECASE),
    re.compile(r"\brm\b.*--no-preserve-root", re.IGNORECASE),
    re.compile(r"\brmdir\b", re.IGNORECASE),
    re.compile(r"\bdel\b\s+/[sS]", re.IGNORECASE),
    re.compile(r"\brd\b\s+/[sS]", re.IGNORECASE),
    re.compile(r"\bRemove-Item\b.*-Recurse", re.IGNORECASE),

    # Disk / format operations
    re.compile(r"\bformat\b\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bdiskpart\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\b\s+.*of=", re.IGNORECASE),

    # System shutdown / reboot
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
    re.compile(r"\bpoweroff\b", re.IGNORECASE),
    re.compile(r"\binit\s+[06]\b", re.IGNORECASE),

    # Registry manipulation (Windows)
    re.compile(r"\breg\b\s+(delete|add)", re.IGNORECASE),
    re.compile(r"\bregedit\b", re.IGNORECASE),

    # Permission / ownership changes
    re.compile(r"\bchmod\b\s+[0-7]{3,4}\s+/", re.IGNORECASE),
    re.compile(r"\bchown\b.*-R\s+.*/", re.IGNORECASE),
    re.compile(r"\bicacls\b", re.IGNORECASE),
    re.compile(r"\btakeown\b", re.IGNORECASE),

    # Process termination of system services
    re.compile(r"\btaskkill\b\s+/f", re.IGNORECASE),
    re.compile(r"\bkill\b\s+-9", re.IGNORECASE),
    re.compile(r"\bnet\s+stop\b", re.IGNORECASE),
    re.compile(r"\bsc\s+delete\b", re.IGNORECASE),

    # Network / firewall changes
    re.compile(r"\bnetsh\b.*firewall", re.IGNORECASE),
    re.compile(r"\biptables\b", re.IGNORECASE),

    # Piping to execution (code injection vectors)
    re.compile(r"\bcurl\b.*\|\s*(bash|sh|python|powershell)", re.IGNORECASE),
    re.compile(r"\bwget\b.*\|\s*(bash|sh|python|powershell)", re.IGNORECASE),
    re.compile(r"\bInvoke-Expression\b", re.IGNORECASE),
    re.compile(r"\biex\b\s*\(", re.IGNORECASE),

    # Env variable manipulation of critical vars
    re.compile(r"\bsetx?\b\s+PATH\b", re.IGNORECASE),
    re.compile(r"\bexport\s+PATH=", re.IGNORECASE),

    # Git destructive operations
    re.compile(r"\bgit\b\s+push\b.*--force", re.IGNORECASE),
    re.compile(r"\bgit\b\s+reset\b.*--hard", re.IGNORECASE),
    re.compile(r"\bgit\b\s+clean\b.*-[a-zA-Z]*f", re.IGNORECASE),
]


def classify(tool_name: str, tool_input: dict[str, Any]) -> PermissionLevel:
    """Classify a tool usage into a permission level.

    Args:
        tool_name: Name of the tool (e.g. "Bash", "Write", "Read")
        tool_input: Tool input parameters

    Returns:
        PermissionLevel indicating required authorization level
    """
    if tool_name in GREEN_TOOLS:
        return PermissionLevel.GREEN

    if tool_name in YELLOW_TOOLS:
        return PermissionLevel.YELLOW

    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        return _classify_bash_command(command)

    # Plugin tools: use the permission_level from the plugin YAML
    if tool_name.startswith("plugin_"):
        return _classify_plugin(tool_name[7:])

    # manage_documents: read-only actions are GREEN, write actions are YELLOW
    if tool_name == "manage_documents":
        action = str(tool_input.get("action", ""))
        if action in ("search", "list", "show", "stats"):
            return PermissionLevel.GREEN
        return PermissionLevel.YELLOW

    # manage_plugins modifies the system, requires confirmation
    if tool_name == "manage_plugins":
        return PermissionLevel.YELLOW

    # manage_scheduled_tasks: list/show are safe, create/update/delete need confirmation
    if tool_name == "manage_scheduled_tasks":
        return PermissionLevel.YELLOW

    # manage_directors: all actions need confirmation
    if tool_name == "manage_directors":
        return PermissionLevel.YELLOW

    # Unknown tools default to YELLOW (safe default)
    return PermissionLevel.YELLOW


def _classify_plugin(plugin_name: str) -> PermissionLevel:
    """Classify a plugin tool by reading its permission_level from YAML."""
    try:
        from plugins import load_plugin_by_name
        plugin = load_plugin_by_name(plugin_name)
        if plugin:
            level_map = {
                "green": PermissionLevel.GREEN,
                "yellow": PermissionLevel.YELLOW,
                "red": PermissionLevel.RED,
            }
            return level_map.get(plugin.permission_level, PermissionLevel.YELLOW)
    except Exception:
        pass
    return PermissionLevel.YELLOW


def _classify_bash_command(command: str) -> PermissionLevel:
    """Classify a Bash command by analyzing its content."""
    if not command.strip():
        return PermissionLevel.GREEN

    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(command):
            return PermissionLevel.RED

    # Non-dangerous Bash commands still require confirmation (YELLOW)
    return PermissionLevel.YELLOW


def get_danger_reason(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Return a human-readable reason why a tool call is classified as RED."""
    if tool_name != "Bash":
        return f"Tool '{tool_name}' requires elevated confirmation"

    command = str(tool_input.get("command", ""))
    for pattern in DANGEROUS_PATTERNS:
        match = pattern.search(command)
        if match:
            return f"Dangerous command detected: '{match.group()}'"

    return "Unknown dangerous pattern"
