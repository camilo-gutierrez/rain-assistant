"""Rain Assistant Plugin System.

Plugins are YAML files in ~/.rain-assistant/plugins/ that define
new tools Rain can use (HTTP APIs, bash commands, Python scripts).
"""

from .schema import Plugin, PluginParameter, PluginExecution, PluginValidationError, parse_plugin_dict
from .loader import load_all_plugins, load_plugin_by_name, PLUGINS_DIR
from .converter import plugin_to_tool_definition
from .executor import execute_plugin
from .meta_tool import (
    MANAGE_PLUGINS_DEFINITION,
    handle_manage_plugins,
    is_reload_needed,
    clear_reload_flag,
    mark_reload_needed,
)

__all__ = [
    "Plugin",
    "PluginParameter",
    "PluginExecution",
    "PluginValidationError",
    "parse_plugin_dict",
    "load_all_plugins",
    "load_plugin_by_name",
    "plugin_to_tool_definition",
    "execute_plugin",
    "MANAGE_PLUGINS_DEFINITION",
    "handle_manage_plugins",
    "is_reload_needed",
    "clear_reload_flag",
    "mark_reload_needed",
    "PLUGINS_DIR",
]
