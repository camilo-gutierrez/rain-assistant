"""Convert Plugin objects to OpenAI/Gemini tool definition formats."""

from .schema import Plugin


def plugin_to_tool_definition(plugin: Plugin) -> dict:
    """Convert a Plugin to OpenAI function-calling format.

    Plugin tools are prefixed with 'plugin_' to avoid collisions with built-in tools.
    """
    properties = {}
    required = []

    for param in plugin.parameters:
        prop: dict = {
            "type": param.type,
            "description": param.description,
        }
        if param.default is not None:
            prop["default"] = param.default
        if param.required:
            required.append(param.name)
        properties[param.name] = prop

    return {
        "type": "function",
        "function": {
            "name": f"plugin_{plugin.name}",
            "description": plugin.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
