"""manage_plugins meta-tool — allows Rain to create/manage plugins via chat."""

import json

from .loader import (
    load_all_plugins,
    load_plugin_by_name,
    save_plugin_yaml,
    delete_plugin,
    set_plugin_enabled,
    get_plugin_env,
    set_plugin_env,
    PLUGINS_DIR,
)
from .schema import PluginValidationError

# Flag for signaling that plugins need to be reloaded
_reload_needed = False


def is_reload_needed() -> bool:
    global _reload_needed
    return _reload_needed


def clear_reload_flag() -> None:
    global _reload_needed
    _reload_needed = False


def mark_reload_needed() -> None:
    global _reload_needed
    _reload_needed = True


MANAGE_PLUGINS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_plugins",
        "description": (
            "Create, list, enable, disable, delete, or show Rain plugins. "
            "Plugins add new capabilities like web search, API integrations, "
            "weather, notifications, etc. When creating a plugin, provide the "
            "full YAML definition as yaml_content. Use set_env to store API keys "
            "that plugins reference via {{env.KEY_NAME}}."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "enable", "disable", "delete", "show", "set_env"],
                    "description": "Action to perform",
                },
                "name": {
                    "type": "string",
                    "description": "Plugin name (required for enable/disable/delete/show)",
                },
                "yaml_content": {
                    "type": "string",
                    "description": "Full YAML content for the plugin (required for 'create' action)",
                },
                "key": {
                    "type": "string",
                    "description": "Environment variable name (for 'set_env' action)",
                },
                "value": {
                    "type": "string",
                    "description": "Environment variable value (for 'set_env' action)",
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_manage_plugins(args: dict, cwd: str) -> dict:
    """Handle manage_plugins tool calls from Rain."""
    action = args.get("action", "")

    try:
        if action == "create":
            return _action_create(args)
        elif action == "list":
            return _action_list()
        elif action == "enable":
            return _action_enable(args)
        elif action == "disable":
            return _action_disable(args)
        elif action == "delete":
            return _action_delete(args)
        elif action == "show":
            return _action_show(args)
        elif action == "set_env":
            return _action_set_env(args)
        else:
            return {"content": f"Unknown action: {action}", "is_error": True}
    except Exception as e:
        return {"content": f"Error: {e}", "is_error": True}


def _action_create(args: dict) -> dict:
    import yaml

    yaml_content = args.get("yaml_content", "")
    if not yaml_content:
        return {"content": "Error: 'yaml_content' is required for create action", "is_error": True}

    try:
        parsed = yaml.safe_load(yaml_content)

        # Block Python plugins via chat — must be installed manually
        exec_type = None
        if isinstance(parsed, dict):
            exec_data = parsed.get("execution", {})
            if isinstance(exec_data, dict):
                exec_type = exec_data.get("type", "")

        if exec_type == "python":
            return {
                "content": "⚠️ Python plugins cannot be created via chat for security reasons. "
                           "Install them manually as files in ~/.rain-assistant/plugins/",
                "is_error": True,
            }

        perm = parsed.get("permission_level", "yellow") if isinstance(parsed, dict) else "yellow"
        if perm == "red":
            return {
                "content": "Cannot create plugins with 'red' permission level via chat. "
                           "Install them manually in ~/.rain-assistant/plugins/",
                "is_error": True,
            }
        if perm not in ("green", "yellow"):
            return {
                "content": f"Invalid permission_level '{perm}'. Must be 'green' or 'yellow'.",
                "is_error": True,
            }
    except yaml.YAMLError as e:
        return {"content": f"Invalid YAML: {e}", "is_error": True}

    try:
        file_path = save_plugin_yaml("", yaml_content)
        mark_reload_needed()
        return {
            "content": f"Plugin created successfully at {file_path}. It will be available for use immediately.",
            "is_error": False,
        }
    except PluginValidationError as e:
        return {"content": f"Validation error: {e}", "is_error": True}


def _action_list() -> dict:
    import yaml

    plugins_dir = PLUGINS_DIR
    if not plugins_dir.exists():
        return {"content": "No plugins directory found. No plugins installed.", "is_error": False}

    yaml_files = sorted(plugins_dir.glob("*.yaml"))
    if not yaml_files:
        return {"content": "No plugins installed.", "is_error": False}

    lines = []
    for f in yaml_files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            name = data.get("name", f.stem)
            desc = data.get("description", "No description")
            enabled = data.get("enabled", True)
            status = "enabled" if enabled else "disabled"
            lines.append(f"  - {name} ({status}): {desc}")
        except Exception:
            lines.append(f"  - {f.stem} (error reading)")

    return {"content": f"Installed plugins ({len(lines)}):\n" + "\n".join(lines), "is_error": False}


def _action_enable(args: dict) -> dict:
    name = args.get("name", "")
    if not name:
        return {"content": "Error: 'name' is required", "is_error": True}
    if set_plugin_enabled(name, True):
        mark_reload_needed()
        return {"content": f"Plugin '{name}' enabled.", "is_error": False}
    return {"content": f"Plugin '{name}' not found.", "is_error": True}


def _action_disable(args: dict) -> dict:
    name = args.get("name", "")
    if not name:
        return {"content": "Error: 'name' is required", "is_error": True}
    if set_plugin_enabled(name, False):
        mark_reload_needed()
        return {"content": f"Plugin '{name}' disabled.", "is_error": False}
    return {"content": f"Plugin '{name}' not found.", "is_error": True}


def _action_delete(args: dict) -> dict:
    name = args.get("name", "")
    if not name:
        return {"content": "Error: 'name' is required", "is_error": True}
    if delete_plugin(name):
        mark_reload_needed()
        return {"content": f"Plugin '{name}' deleted.", "is_error": False}
    return {"content": f"Plugin '{name}' not found.", "is_error": True}


def _action_show(args: dict) -> dict:
    name = args.get("name", "")
    if not name:
        return {"content": "Error: 'name' is required", "is_error": True}

    file_path = PLUGINS_DIR / f"{name}.yaml"
    if not file_path.exists():
        return {"content": f"Plugin '{name}' not found.", "is_error": True}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {"content": f"Plugin '{name}' definition:\n```yaml\n{content}\n```", "is_error": False}


_BLOCKED_ENV_VARS = {
    # System critical
    "PATH", "HOME", "USER", "SHELL", "LOGNAME",
    # Code injection vectors
    "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP",
    "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
    # Git credential theft
    "GIT_SSH_COMMAND", "GIT_ASKPASS", "GIT_PROXY_COMMAND",
    # Misc dangerous
    "HISTFILE", "HISTCONTROL", "EDITOR", "VISUAL",
    "COMSPEC", "SYSTEMROOT", "PATHEXT",
    # Rain internal
    "RAIN_PLUGIN_ARGS",
}


def _action_set_env(args: dict) -> dict:
    key = args.get("key", "")
    value = args.get("value", "")
    if not key:
        return {"content": "Error: 'key' is required for set_env", "is_error": True}
    if not value:
        return {"content": "Error: 'value' is required for set_env", "is_error": True}

    if key.upper() in _BLOCKED_ENV_VARS:
        return {
            "content": f"⚠️ Environment variable '{key}' is blocked for security reasons.",
            "is_error": True,
        }
    if len(key) > 64:
        return {"content": "Error: key name too long (max 64 chars)", "is_error": True}
    if len(value) > 10000:
        return {"content": "Error: value too large (max 10000 chars)", "is_error": True}

    set_plugin_env(key, value)
    return {
        "content": f"Environment variable '{key}' saved. Plugins can reference it as {{{{env.{key}}}}}.",
        "is_error": False,
    }
