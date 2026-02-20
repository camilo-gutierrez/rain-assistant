"""
Tool definitions for non-Claude providers (OpenAI / Gemini).

Defined in OpenAI function calling format. Gemini uses a converted version.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file at the given path. "
                "Returns the file content as text with line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file to read",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Line number to start reading from (1-based). Optional.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read. Optional.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file. Creates the file if it doesn't exist, "
                "overwrites if it does. Creates parent directories automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Make a targeted edit to a file by replacing a specific string "
                "with new content. The old_string must appear exactly once in the file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to edit",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace it with",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Execute a shell command and return stdout + stderr. "
                "Commands run in the project working directory. "
                "Use for git, npm, pip, running tests, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds. Default: 120.",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": (
                "List files and directories at the given path. "
                "Returns names with type indicators (/ for dirs)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list. Defaults to project root.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Search for files matching a glob pattern. "
                "Returns matching file paths relative to the search root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Root directory to search from. Defaults to project root.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": (
                "Search file contents for a regex pattern. "
                "Returns matching lines with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in. Defaults to project root.",
                    },
                    "include": {
                        "type": "string",
                        "description": "Glob to filter files (e.g., '*.py', '*.ts'). Optional.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": (
                "Navigate to a URL in a headless browser. Returns page title and status. "
                "Use this to browse websites, read documentation, check APIs, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to (e.g., 'https://example.com')",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": (
                "Take a screenshot of the current browser page. "
                "Returns a base64-encoded PNG image."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "If true, capture the entire scrollable page. Default: false.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": (
                "Click an element on the current browser page. "
                "Identify the element by CSS selector or visible text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector (e.g., '#submit-btn', '.link') or visible text if by_text is true",
                    },
                    "by_text": {
                        "type": "boolean",
                        "description": "If true, find element by its visible text instead of CSS selector. Default: false.",
                    },
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": (
                "Type text into a form field on the current browser page. "
                "The field is identified by CSS selector."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector of the input field (e.g., '#search', 'input[name=email]')",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type into the field",
                    },
                    "clear_first": {
                        "type": "boolean",
                        "description": "If true, clear the field before typing. Default: true.",
                    },
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_extract_text",
            "description": (
                "Extract text content from the current browser page or a specific element. "
                "Useful for reading web pages, scraping data, or checking page content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to extract from. If omitted, extracts entire page body.",
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum characters to return. Default: 10000.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "Scroll the current browser page up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Scroll direction: 'up' or 'down'. Default: 'down'.",
                        "enum": ["up", "down"],
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Pixels to scroll. Default: 500.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_close",
            "description": "Close the browser. Call this when done browsing to free resources.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


def get_tool_definitions_gemini() -> list[dict]:
    """Convert OpenAI-format tool definitions to Gemini format.

    Gemini expects:
      [{"function_declarations": [{"name": ..., "description": ..., "parameters": {...}}]}]
    """
    declarations = []
    for tool in TOOL_DEFINITIONS:
        func = tool["function"]
        declarations.append({
            "name": func["name"],
            "description": func["description"],
            "parameters": func["parameters"],
        })
    return [{"function_declarations": declarations}]


def _to_gemini_format(tool_defs: list[dict]) -> list[dict]:
    """Convert a list of OpenAI-format tool defs to Gemini format."""
    declarations = []
    for tool in tool_defs:
        func = tool["function"]
        declarations.append({
            "name": func["name"],
            "description": func["description"],
            "parameters": func["parameters"],
        })
    return [{"function_declarations": declarations}]


def get_all_tool_definitions() -> list[dict]:
    """Return built-in tools + manage_plugins + memories + alter_egos + all enabled plugin tools."""
    from plugins import load_all_plugins, plugin_to_tool_definition, MANAGE_PLUGINS_DEFINITION
    from memories import MANAGE_MEMORIES_DEFINITION
    from alter_egos import MANAGE_ALTER_EGOS_DEFINITION

    from scheduled_tasks import MANAGE_SCHEDULED_TASKS_DEFINITION
    from subagents import MANAGE_SUBAGENTS_DEFINITION
    from marketplace import MANAGE_MARKETPLACE_DEFINITION
    from documents import MANAGE_DOCUMENTS_DEFINITION

    all_tools = list(TOOL_DEFINITIONS)
    all_tools.append(MANAGE_PLUGINS_DEFINITION)
    all_tools.append(MANAGE_MEMORIES_DEFINITION)
    all_tools.append(MANAGE_ALTER_EGOS_DEFINITION)
    all_tools.append(MANAGE_SCHEDULED_TASKS_DEFINITION)
    all_tools.append(MANAGE_SUBAGENTS_DEFINITION)
    all_tools.append(MANAGE_MARKETPLACE_DEFINITION)
    all_tools.append(MANAGE_DOCUMENTS_DEFINITION)

    for plugin in load_all_plugins():
        all_tools.append(plugin_to_tool_definition(plugin))

    return all_tools


def get_all_tool_definitions_gemini() -> list[dict]:
    """Gemini-format version of get_all_tool_definitions."""
    return _to_gemini_format(get_all_tool_definitions())
