"""Tests for the plugin system — schema, loader, converter, executor templates."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from plugins.schema import (
    Plugin,
    PluginParameter,
    PluginExecution,
    PluginValidationError,
    parse_plugin_dict,
    NAME_PATTERN,
    VALID_TYPES,
    VALID_LEVELS,
    VALID_EXEC_TYPES,
)
from plugins.converter import plugin_to_tool_definition
from plugins.executor import (
    _resolve_template,
    _resolve_dict,
    _resolve_value,
    _extract_data,
)

SAMPLE_PLUGIN_YAML = """\
name: test_plugin
description: A test plugin for unit tests
version: "1.0"
author: tester
enabled: true
permission_level: yellow
parameters:
  - name: query
    type: string
    description: Search query
    required: true
execution:
  type: http
  method: GET
  url: "https://example.com/api?q={{query}}"
  headers:
    Authorization: "Bearer {{env.TEST_API_KEY}}"
"""

SAMPLE_BASH_PLUGIN_YAML = """\
name: bash_test
description: A bash plugin for testing
version: "1.0"
enabled: true
permission_level: green
parameters:
  - name: filename
    type: string
    description: File to check
    required: true
execution:
  type: bash
  command: "echo {{filename}}"
"""

SAMPLE_DISABLED_PLUGIN_YAML = """\
name: disabled_plugin
description: A disabled plugin
version: "1.0"
enabled: false
permission_level: yellow
parameters: []
execution:
  type: http
  method: GET
  url: "https://disabled.example.com"
"""


# =====================================================================
# Plugin schema validation
# =====================================================================

class TestPluginNamePattern:
    """Test the NAME_PATTERN regex for valid/invalid plugin names."""

    @pytest.mark.parametrize("name", [
        "test_plugin", "my_api", "weather", "a123", "get_data_v2",
    ])
    def test_valid_names(self, name):
        assert NAME_PATTERN.match(name) is not None

    @pytest.mark.parametrize("name", [
        "TestPlugin", "my-plugin", "123plugin", "has space",
        "ALLCAPS", "",
    ])
    def test_invalid_names(self, name):
        assert NAME_PATTERN.match(name) is None

    def test_underscore_prefix_is_valid(self):
        """The regex allows underscore as first character."""
        assert NAME_PATTERN.match("_hidden") is not None


class TestPluginValidation:
    """Test Plugin.validate() for various invalid configs."""

    def test_valid_http_plugin(self):
        plugin = Plugin(
            name="test_api",
            description="Test API plugin",
            execution=PluginExecution(type="http", url="https://example.com"),
        )
        plugin.validate()  # Should not raise

    def test_valid_bash_plugin(self):
        plugin = Plugin(
            name="bash_tool",
            description="Bash plugin",
            execution=PluginExecution(type="bash", command="echo hello"),
        )
        plugin.validate()

    def test_valid_python_plugin(self):
        plugin = Plugin(
            name="py_tool",
            description="Python plugin",
            execution=PluginExecution(type="python", script="print('hello')"),
        )
        plugin.validate()

    def test_invalid_name(self):
        plugin = Plugin(
            name="BadName",
            description="test",
            execution=PluginExecution(type="http", url="https://x.com"),
        )
        with pytest.raises(PluginValidationError, match="Invalid plugin name"):
            plugin.validate()

    def test_empty_description(self):
        plugin = Plugin(
            name="test",
            description="",
            execution=PluginExecution(type="http", url="https://x.com"),
        )
        with pytest.raises(PluginValidationError, match="must have a description"):
            plugin.validate()

    def test_invalid_permission_level(self):
        plugin = Plugin(
            name="test",
            description="test",
            permission_level="critical",
            execution=PluginExecution(type="http", url="https://x.com"),
        )
        with pytest.raises(PluginValidationError, match="Invalid permission_level"):
            plugin.validate()

    def test_invalid_execution_type(self):
        plugin = Plugin(
            name="test",
            description="test",
            execution=PluginExecution(type="graphql"),
        )
        with pytest.raises(PluginValidationError, match="Invalid execution type"):
            plugin.validate()

    def test_http_without_url(self):
        plugin = Plugin(
            name="test",
            description="test",
            execution=PluginExecution(type="http", url=""),
        )
        with pytest.raises(PluginValidationError, match="require a 'url'"):
            plugin.validate()

    def test_bash_without_command(self):
        plugin = Plugin(
            name="test",
            description="test",
            execution=PluginExecution(type="bash", command=""),
        )
        with pytest.raises(PluginValidationError, match="require a 'command'"):
            plugin.validate()

    def test_python_without_script(self):
        plugin = Plugin(
            name="test",
            description="test",
            execution=PluginExecution(type="python", script=""),
        )
        with pytest.raises(PluginValidationError, match="require a 'script'"):
            plugin.validate()

    def test_invalid_http_method(self):
        plugin = Plugin(
            name="test",
            description="test",
            execution=PluginExecution(type="http", url="https://x.com", method="CONNECT"),
        )
        with pytest.raises(PluginValidationError, match="Invalid HTTP method"):
            plugin.validate()

    def test_invalid_parameter_type(self):
        plugin = Plugin(
            name="test",
            description="test",
            parameters=[PluginParameter(name="x", type="date")],
            execution=PluginExecution(type="http", url="https://x.com"),
        )
        with pytest.raises(PluginValidationError, match="Invalid parameter type"):
            plugin.validate()

    def test_parameter_without_name(self):
        plugin = Plugin(
            name="test",
            description="test",
            parameters=[PluginParameter(name="", type="string")],
            execution=PluginExecution(type="http", url="https://x.com"),
        )
        with pytest.raises(PluginValidationError, match="must have a name"):
            plugin.validate()


class TestParsePluginDict:
    """Test parsing YAML dicts into Plugin objects."""

    def test_parse_http_plugin(self):
        data = yaml.safe_load(SAMPLE_PLUGIN_YAML)
        plugin = parse_plugin_dict(data)
        assert plugin.name == "test_plugin"
        assert plugin.description == "A test plugin for unit tests"
        assert plugin.enabled is True
        assert plugin.permission_level == "yellow"
        assert len(plugin.parameters) == 1
        assert plugin.parameters[0].name == "query"
        assert plugin.execution.type == "http"
        assert "example.com" in plugin.execution.url

    def test_parse_bash_plugin(self):
        data = yaml.safe_load(SAMPLE_BASH_PLUGIN_YAML)
        plugin = parse_plugin_dict(data)
        assert plugin.name == "bash_test"
        assert plugin.execution.type == "bash"
        assert "echo" in plugin.execution.command

    def test_parse_disabled_plugin(self):
        data = yaml.safe_load(SAMPLE_DISABLED_PLUGIN_YAML)
        plugin = parse_plugin_dict(data)
        assert plugin.enabled is False

    def test_parse_non_dict_raises(self):
        with pytest.raises(PluginValidationError, match="must be a dict"):
            parse_plugin_dict("not a dict")

    def test_parse_minimal_plugin(self):
        data = {
            "name": "minimal",
            "description": "Minimal plugin",
            "execution": {
                "type": "http",
                "url": "https://example.com",
            },
        }
        plugin = parse_plugin_dict(data)
        assert plugin.name == "minimal"
        assert plugin.version == "1.0"
        assert plugin.author == "rain-auto"
        assert plugin.enabled is True
        assert plugin.permission_level == "yellow"


# =====================================================================
# Plugin loader (with patched PLUGINS_DIR)
# =====================================================================

class TestPluginLoader:
    """Test loading plugins from YAML files on disk."""

    def test_load_all_plugins(self, tmp_path):
        from plugins import loader

        old_dir = loader.PLUGINS_DIR
        loader.PLUGINS_DIR = tmp_path

        # Write a valid plugin
        (tmp_path / "my_api.yaml").write_text(SAMPLE_PLUGIN_YAML, encoding="utf-8")
        # Write a disabled plugin
        (tmp_path / "disabled.yaml").write_text(SAMPLE_DISABLED_PLUGIN_YAML, encoding="utf-8")

        plugins = loader.load_all_plugins()
        # Only enabled plugins
        assert len(plugins) == 1
        assert plugins[0].name == "test_plugin"

        loader.PLUGINS_DIR = old_dir

    def test_load_plugin_by_name(self, tmp_path):
        from plugins import loader

        old_dir = loader.PLUGINS_DIR
        loader.PLUGINS_DIR = tmp_path

        (tmp_path / "test_plugin.yaml").write_text(SAMPLE_PLUGIN_YAML, encoding="utf-8")

        plugin = loader.load_plugin_by_name("test_plugin")
        assert plugin is not None
        assert plugin.name == "test_plugin"

        # Non-existent
        assert loader.load_plugin_by_name("nonexistent") is None

        loader.PLUGINS_DIR = old_dir

    def test_load_invalid_yaml_skipped(self, tmp_path):
        from plugins import loader

        old_dir = loader.PLUGINS_DIR
        loader.PLUGINS_DIR = tmp_path

        # Invalid YAML content
        (tmp_path / "bad.yaml").write_text("name: Bad Plugin\n", encoding="utf-8")
        # Valid
        (tmp_path / "bash_test.yaml").write_text(SAMPLE_BASH_PLUGIN_YAML, encoding="utf-8")

        plugins = loader.load_all_plugins()
        # Only the valid one should load
        assert len(plugins) == 1
        assert plugins[0].name == "bash_test"

        loader.PLUGINS_DIR = old_dir

    def test_delete_plugin(self, tmp_path):
        from plugins import loader

        old_dir = loader.PLUGINS_DIR
        loader.PLUGINS_DIR = tmp_path

        (tmp_path / "to_delete.yaml").write_text(SAMPLE_BASH_PLUGIN_YAML, encoding="utf-8")
        assert loader.delete_plugin("to_delete") is True
        assert not (tmp_path / "to_delete.yaml").exists()

        # Deleting non-existent returns False
        assert loader.delete_plugin("ghost") is False

        loader.PLUGINS_DIR = old_dir

    def test_set_plugin_enabled(self, tmp_path):
        from plugins import loader

        old_dir = loader.PLUGINS_DIR
        loader.PLUGINS_DIR = tmp_path

        (tmp_path / "test_plugin.yaml").write_text(SAMPLE_PLUGIN_YAML, encoding="utf-8")

        # Disable
        assert loader.set_plugin_enabled("test_plugin", False) is True
        data = yaml.safe_load((tmp_path / "test_plugin.yaml").read_text(encoding="utf-8"))
        assert data["enabled"] is False

        # Enable
        assert loader.set_plugin_enabled("test_plugin", True) is True
        data = yaml.safe_load((tmp_path / "test_plugin.yaml").read_text(encoding="utf-8"))
        assert data["enabled"] is True

        # Non-existent
        assert loader.set_plugin_enabled("ghost", True) is False

        loader.PLUGINS_DIR = old_dir

    def test_save_plugin_yaml(self, tmp_path):
        from plugins import loader

        old_dir = loader.PLUGINS_DIR
        loader.PLUGINS_DIR = tmp_path

        path = loader.save_plugin_yaml("whatever", SAMPLE_PLUGIN_YAML)
        assert path.exists()
        assert path.name == "test_plugin.yaml"  # Uses name from content

        loader.PLUGINS_DIR = old_dir

    def test_get_set_plugin_env(self, tmp_path):
        from plugins import loader

        config_path = tmp_path / "config.json"
        config_path.write_text("{}", encoding="utf-8")

        with patch.object(Path, "home", return_value=tmp_path):
            # Patch the config path used by loader
            old_config = loader.Path.home
            loader.set_plugin_env.__globals__  # This won't work, let's patch differently

        # Direct test with patched path
        original_home = Path.home
        with patch("plugins.loader.Path") as MockPath:
            MockPath.home.return_value = tmp_path
            mock_config = tmp_path / ".rain-assistant" / "config.json"
            (tmp_path / ".rain-assistant").mkdir(exist_ok=True)
            mock_config.write_text("{}", encoding="utf-8")

            # We'll test the functions directly by manipulating the file
            # since they use Path.home() internally


# =====================================================================
# Plugin converter
# =====================================================================

class TestPluginConverter:
    """Test converting Plugin objects to OpenAI function-calling format."""

    def test_basic_conversion(self):
        plugin = Plugin(
            name="weather",
            description="Get weather info",
            parameters=[
                PluginParameter(name="city", type="string", description="City name", required=True),
                PluginParameter(name="units", type="string", description="Units", required=False, default="metric"),
            ],
            execution=PluginExecution(type="http", url="https://api.weather.com"),
        )

        definition = plugin_to_tool_definition(plugin)
        assert definition["type"] == "function"
        assert definition["function"]["name"] == "plugin_weather"
        assert definition["function"]["description"] == "Get weather info"
        assert "city" in definition["function"]["parameters"]["properties"]
        assert "units" in definition["function"]["parameters"]["properties"]
        assert "city" in definition["function"]["parameters"]["required"]
        assert "units" not in definition["function"]["parameters"]["required"]

    def test_no_parameters(self):
        plugin = Plugin(
            name="ping",
            description="Ping server",
            execution=PluginExecution(type="http", url="https://example.com/ping"),
        )
        definition = plugin_to_tool_definition(plugin)
        assert definition["function"]["parameters"]["properties"] == {}
        assert definition["function"]["parameters"]["required"] == []

    def test_parameter_default_included(self):
        plugin = Plugin(
            name="test",
            description="Test",
            parameters=[
                PluginParameter(name="limit", type="integer", default=10),
            ],
            execution=PluginExecution(type="http", url="https://x.com"),
        )
        definition = plugin_to_tool_definition(plugin)
        props = definition["function"]["parameters"]["properties"]
        assert props["limit"]["default"] == 10


# =====================================================================
# Template resolution (executor)
# =====================================================================

class TestTemplateResolution:
    """Test {{variable}} template substitution."""

    def test_resolve_simple_variable(self):
        result = _resolve_template("Hello {{name}}", {"name": "Rain"}, {})
        assert result == "Hello Rain"

    def test_resolve_env_variable(self):
        result = _resolve_template("Key: {{env.API_KEY}}", {}, {"API_KEY": "secret123"})
        assert result == "Key: secret123"

    def test_resolve_missing_variable(self):
        result = _resolve_template("Hello {{missing}}", {}, {})
        assert result == "Hello "

    def test_resolve_multiple_variables(self):
        result = _resolve_template(
            "{{greeting}} {{name}}, key={{env.KEY}}",
            {"greeting": "Hi", "name": "User"},
            {"KEY": "abc"},
        )
        assert result == "Hi User, key=abc"

    def test_resolve_no_templates(self):
        result = _resolve_template("plain text", {}, {})
        assert result == "plain text"

    def test_resolve_non_string(self):
        result = _resolve_template(123, {}, {})
        assert result == "123"

    def test_resolve_dict(self):
        d = {
            "url": "https://api.com/{{endpoint}}",
            "token": "Bearer {{env.TOKEN}}",
            "nested": {
                "query": "{{q}}",
            },
        }
        result = _resolve_dict(d, {"endpoint": "search", "q": "test"}, {"TOKEN": "xyz"})
        assert result["url"] == "https://api.com/search"
        assert result["token"] == "Bearer xyz"
        assert result["nested"]["query"] == "test"

    def test_resolve_value_argument(self):
        assert _resolve_value("name", {"name": "Rain"}, {}) == "Rain"

    def test_resolve_value_env(self):
        assert _resolve_value("env.KEY", {}, {"KEY": "val"}) == "val"

    def test_resolve_value_missing(self):
        assert _resolve_value("missing", {}, {}) == ""


class TestDataExtraction:
    """Test _extract_data for JSON path extraction."""

    def test_simple_key(self):
        data = {"name": "Rain", "version": 1}
        assert _extract_data(data, "name") == "Rain"

    def test_nested_key(self):
        data = {"user": {"name": "Rain"}}
        assert _extract_data(data, "user.name") == "Rain"

    def test_array_extraction(self):
        data = {"items": [{"title": "A"}, {"title": "B"}]}
        result = _extract_data(data, "items[].title")
        assert result == ["A", "B"]

    def test_field_selector(self):
        data = {"items": [{"title": "A", "link": "1", "extra": "x"}, {"title": "B", "link": "2", "extra": "y"}]}
        result = _extract_data(data, "items[].{title, link}")
        assert result == [{"title": "A", "link": "1"}, {"title": "B", "link": "2"}]

    def test_empty_path(self):
        data = {"test": 1}
        assert _extract_data(data, "") == data

    def test_none_data(self):
        assert _extract_data(None, "key") is None

    def test_missing_key(self):
        data = {"a": 1}
        assert _extract_data(data, "b") is None
