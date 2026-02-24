"""Plugin loader — reads YAML files from ~/.rain-assistant/plugins/."""

import json
import os
from pathlib import Path

from .schema import Plugin, PluginValidationError, parse_plugin_dict

PLUGINS_DIR = Path.home() / ".rain-assistant" / "plugins"


def ensure_plugins_dir() -> Path:
    """Create plugins directory if it doesn't exist."""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    return PLUGINS_DIR


def load_all_plugins() -> list[Plugin]:
    """Load and validate all YAML plugin files. Returns only valid, enabled plugins."""
    import yaml

    ensure_plugins_dir()
    plugins: list[Plugin] = []

    for yaml_file in sorted(PLUGINS_DIR.glob("*.yaml")):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            plugin = parse_plugin_dict(data)
            if plugin.enabled:
                plugins.append(plugin)
        except PluginValidationError as e:
            print(f"  [PLUGIN] Skipping {yaml_file.name}: {e}")
        except Exception as e:
            print(f"  [PLUGIN] Error loading {yaml_file.name}: {e}")

    return plugins


def load_plugin_by_name(name: str) -> Plugin | None:
    """Load a specific plugin by name (including disabled)."""
    import yaml
    from .schema import NAME_PATTERN

    if not NAME_PATTERN.match(name):
        return None

    yaml_path = PLUGINS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        return None

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return None

    return parse_plugin_dict(data)


def save_plugin_yaml(name: str, yaml_content: str) -> Path:
    """Save YAML content to a plugin file. Returns the file path."""
    import yaml

    ensure_plugins_dir()

    # Validate by parsing first
    data = yaml.safe_load(yaml_content)
    plugin = parse_plugin_dict(data)

    # Use the plugin name from content, not the argument
    file_path = (PLUGINS_DIR / f"{plugin.name}.yaml").resolve()
    plugins_root = PLUGINS_DIR.resolve()
    if not str(file_path).startswith(str(plugins_root) + os.sep) and file_path.parent != plugins_root:
        raise ValueError(f"Plugin name resolves outside plugins directory: {plugin.name}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    return file_path


def delete_plugin(name: str) -> bool:
    """Delete a plugin file. Returns True if deleted."""
    from .schema import NAME_PATTERN

    if not NAME_PATTERN.match(name):
        return False

    file_path = PLUGINS_DIR / f"{name}.yaml"
    if file_path.exists():
        file_path.unlink()
        return True
    return False


def set_plugin_enabled(name: str, enabled: bool) -> bool:
    """Enable or disable a plugin by modifying its YAML file."""
    import yaml
    from .schema import NAME_PATTERN

    if not NAME_PATTERN.match(name):
        return False

    file_path = PLUGINS_DIR / f"{name}.yaml"
    if not file_path.exists():
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["enabled"] = enabled

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return True


def get_plugin_env() -> dict[str, str]:
    """Read plugin environment variables from config.json."""
    config_path = Path.home() / ".rain-assistant" / "config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return config.get("plugin_env", {})
    except Exception:
        return {}


def set_plugin_env(key: str, value: str) -> None:
    """Save a plugin environment variable to config.json."""
    config_path = Path.home() / ".rain-assistant" / "config.json"
    config = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            pass

    if "plugin_env" not in config:
        config["plugin_env"] = {}
    config["plugin_env"][key] = value

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
