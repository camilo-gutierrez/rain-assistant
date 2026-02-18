"""Plugin data model and validation for Rain Assistant."""

import re
from dataclasses import dataclass, field
from typing import Any

NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
VALID_TYPES = {"string", "integer", "number", "boolean"}
VALID_LEVELS = {"green", "yellow", "red"}
VALID_EXEC_TYPES = {"http", "bash", "python"}
VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


class PluginValidationError(Exception):
    pass


@dataclass
class PluginParameter:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class PluginExecution:
    type: str = "http"
    # HTTP
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    extract: str = ""
    # Bash
    command: str = ""
    # Python
    script: str = ""


@dataclass
class Plugin:
    name: str
    description: str
    version: str = "1.0"
    author: str = "rain-auto"
    enabled: bool = True
    permission_level: str = "yellow"
    parameters: list[PluginParameter] = field(default_factory=list)
    execution: PluginExecution = field(default_factory=PluginExecution)

    def validate(self) -> None:
        """Validate plugin data. Raises PluginValidationError on invalid data."""
        if not NAME_PATTERN.match(self.name):
            raise PluginValidationError(
                f"Invalid plugin name '{self.name}'. Must match [a-z_][a-z0-9_]*"
            )
        if not self.description:
            raise PluginValidationError("Plugin must have a description")
        if self.permission_level not in VALID_LEVELS:
            raise PluginValidationError(
                f"Invalid permission_level '{self.permission_level}'. Must be one of: {VALID_LEVELS}"
            )
        if self.execution.type not in VALID_EXEC_TYPES:
            raise PluginValidationError(
                f"Invalid execution type '{self.execution.type}'. Must be one of: {VALID_EXEC_TYPES}"
            )
        if self.execution.type == "http" and not self.execution.url:
            raise PluginValidationError("HTTP plugins require a 'url' in execution")
        if self.execution.type == "bash" and not self.execution.command:
            raise PluginValidationError("Bash plugins require a 'command' in execution")
        if self.execution.type == "python" and not self.execution.script:
            raise PluginValidationError("Python plugins require a 'script' in execution")
        if self.execution.type == "http" and self.execution.method.upper() not in VALID_HTTP_METHODS:
            raise PluginValidationError(
                f"Invalid HTTP method '{self.execution.method}'. Must be one of: {VALID_HTTP_METHODS}"
            )
        for param in self.parameters:
            if not param.name:
                raise PluginValidationError("Parameter must have a name")
            if param.type not in VALID_TYPES:
                raise PluginValidationError(
                    f"Invalid parameter type '{param.type}'. Must be one of: {VALID_TYPES}"
                )


def parse_plugin_dict(data: dict) -> Plugin:
    """Parse a raw dict (from YAML) into a validated Plugin object."""
    if not isinstance(data, dict):
        raise PluginValidationError("Plugin data must be a dict")

    # Parse parameters
    params = []
    for p in data.get("parameters", []):
        if isinstance(p, dict):
            params.append(PluginParameter(
                name=p.get("name", ""),
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", True),
                default=p.get("default"),
            ))

    # Parse execution
    exec_data = data.get("execution", {})
    if not isinstance(exec_data, dict):
        exec_data = {}

    execution = PluginExecution(
        type=exec_data.get("type", "http"),
        method=exec_data.get("method", "GET"),
        url=exec_data.get("url", ""),
        headers=exec_data.get("headers", {}),
        params=exec_data.get("params", {}),
        body=exec_data.get("body", {}),
        extract=exec_data.get("extract", ""),
        command=exec_data.get("command", ""),
        script=exec_data.get("script", ""),
    )

    plugin = Plugin(
        name=data.get("name", ""),
        description=data.get("description", ""),
        version=str(data.get("version", "1.0")),
        author=data.get("author", "rain-auto"),
        enabled=data.get("enabled", True),
        permission_level=data.get("permission_level", "yellow"),
        parameters=params,
        execution=execution,
    )

    plugin.validate()
    return plugin
