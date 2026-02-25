"""Director execution engine — runs directors with configurable tool access.

Creates a temporary provider instance, builds a director-specific system prompt
and permission callback, executes, and stores results in the inbox.

Strategy for director-specific actions (save_to_inbox, delegate_task, update_my_context):
  - ClaudeProvider runs tools inside its own SDK subprocess, so we can't inject
    custom Python tool handlers. Instead, we instruct the director to emit a
    structured :::DIRECTOR_ACTIONS::: block at the end of its response, then
    post-process it to execute the actions.
  - For OpenAI/Gemini providers that have a _tool_executor, we register handlers
    directly (legacy path).
"""

import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger("rain.directors")

# ---------------------------------------------------------------------------
# Structured output markers
# ---------------------------------------------------------------------------

ACTIONS_START = "RAIN_ACTIONS_START"
ACTIONS_END = "RAIN_ACTIONS_END"

# Regex to extract the actions block — tries code fences first, then raw JSON
_ACTIONS_RE = re.compile(
    rf"{re.escape(ACTIONS_START)}\s*```(?:json)?\s*(.*?)\s*```\s*{re.escape(ACTIONS_END)}",
    re.DOTALL,
)

# Fallback: raw JSON between markers (no code fences)
_ACTIONS_RE_FALLBACK = re.compile(
    rf"{re.escape(ACTIONS_START)}\s*(\[.*?\])\s*{re.escape(ACTIONS_END)}",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Director-specific tool definitions (for OpenAI/Gemini providers)
# ---------------------------------------------------------------------------

DELEGATE_TASK_DEFINITION = {
    "type": "function",
    "function": {
        "name": "delegate_task",
        "description": (
            "Create a task for another director to work on. Use this to delegate "
            "work to directors with the right expertise. For example, delegate "
            "content creation to 'content', coding to 'development', etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Clear, actionable task title",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description with context and requirements",
                },
                "assignee": {
                    "type": "string",
                    "description": "Director ID to assign the task to (e.g., 'content', 'development')",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority 1 (highest) to 10 (lowest). Default: 5",
                },
                "task_type": {
                    "type": "string",
                    "enum": ["analysis", "content", "code", "review", "report", "custom"],
                    "description": "Type of task. Default: 'analysis'",
                },
                "input_data": {
                    "type": "object",
                    "description": "Additional context data as key-value pairs",
                },
            },
            "required": ["title", "assignee"],
        },
    },
}

SAVE_TO_INBOX_DEFINITION = {
    "type": "function",
    "function": {
        "name": "save_to_inbox",
        "description": (
            "Save a deliverable to the user's inbox for review. Use this to submit "
            "reports, drafts, analyses, code summaries, or notifications. The user "
            "will see these when they open the Directors Inbox."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Clear, descriptive title for the deliverable",
                },
                "content": {
                    "type": "string",
                    "description": "Full content in markdown format",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["report", "draft", "analysis", "code", "notification"],
                    "description": "Type of deliverable. Default: 'report'",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority 1 (highest) to 10 (lowest). Default: 5",
                },
            },
            "required": ["title", "content"],
        },
    },
}

UPDATE_MY_CONTEXT_DEFINITION = {
    "type": "function",
    "function": {
        "name": "update_my_context",
        "description": (
            "Update your persistent context. This data persists across runs and "
            "helps you maintain state between executions. Use it to store notes, "
            "metrics, dates, or any data you need to remember."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Context key (e.g., 'last_analysis_date', 'tracked_metrics')",
                },
                "value": {
                    "type": "string",
                    "description": "Context value. Empty string removes the key.",
                },
            },
            "required": ["key", "value"],
        },
    },
}


def _build_director_tools(director: dict) -> list[dict]:
    """Build the list of tool definitions available to this director."""
    from tools.definitions import get_all_tool_definitions

    all_tools = get_all_tool_definitions()
    tools_allowed = director.get("tools_allowed", ["*"])
    plugins_allowed = director.get("plugins_allowed", ["*"])

    if isinstance(tools_allowed, str):
        tools_allowed = json.loads(tools_allowed)
    if isinstance(plugins_allowed, str):
        plugins_allowed = json.loads(plugins_allowed)

    # Filter built-in tools
    if "*" in tools_allowed:
        result = list(all_tools)
    else:
        result = []
        for t in all_tools:
            name = t["function"]["name"]
            if name.startswith("plugin_"):
                # Handle plugins separately
                result.append(t)
            elif name in tools_allowed:
                result.append(t)

    # Filter plugins
    if "*" not in plugins_allowed:
        result = [
            t for t in result
            if not t["function"]["name"].startswith("plugin_")
            or t["function"]["name"][7:] in plugins_allowed
        ]

    # Remove manage_directors from director execution to prevent recursion
    result = [t for t in result if t["function"]["name"] != "manage_directors"]

    # Inject director-specific tools
    if director.get("can_delegate"):
        result.append(DELEGATE_TASK_DEFINITION)
    result.append(SAVE_TO_INBOX_DEFINITION)
    result.append(UPDATE_MY_CONTEXT_DEFINITION)

    return result


def _is_tool_allowed(
    tool_name: str,
    max_level: str,
    allow_all_tools: bool,
    tools_allowed: list[str],
    allow_all_plugins: bool,
    plugins_allowed: list[str],
) -> bool:
    """Core logic: decide if a director is allowed to use a tool."""
    from tools.executor import GREEN_TOOLS

    # Plugin tools
    if tool_name.startswith("plugin_"):
        plugin_name = tool_name[7:]
        if not allow_all_plugins and plugin_name not in plugins_allowed:
            return False
        try:
            from plugins import load_plugin_by_name
            plugin = load_plugin_by_name(plugin_name)
            if plugin:
                if plugin.permission_level == "green":
                    return True
                if plugin.permission_level == "yellow" and max_level == "yellow":
                    return True
                return False
        except Exception:
            return False

    # Built-in GREEN tools — always allow if in allowed list
    if tool_name in GREEN_TOOLS:
        if allow_all_tools or tool_name in tools_allowed:
            return True

    # YELLOW tools — only if director has yellow permission
    if max_level == "yellow":
        if allow_all_tools or tool_name in tools_allowed:
            return True

    return False


def _build_permission_callback(director: dict, provider_name: str = "claude"):
    """Build a permission callback based on the director's configuration.

    For ClaudeProvider: returns PermissionResultAllow / PermissionResultDeny (SDK types).
    For OpenAI/Gemini/Ollama: returns bool.
    """
    tools_allowed = director.get("tools_allowed", ["*"])
    plugins_allowed = director.get("plugins_allowed", ["*"])
    max_level = director.get("permission_level", "green")

    if isinstance(tools_allowed, str):
        tools_allowed = json.loads(tools_allowed)
    if isinstance(plugins_allowed, str):
        plugins_allowed = json.loads(plugins_allowed)

    allow_all_tools = "*" in tools_allowed
    allow_all_plugins = "*" in plugins_allowed

    if provider_name == "claude":
        # Claude SDK callback: returns PermissionResult types
        from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

        async def claude_callback(tool_name: str, tool_input: dict, context=None):
            allowed = _is_tool_allowed(
                tool_name, max_level, allow_all_tools, tools_allowed,
                allow_all_plugins, plugins_allowed,
            )
            if allowed:
                return PermissionResultAllow()
            return PermissionResultDeny(
                message=f"Director '{director['id']}' (permission_level={max_level}) "
                        f"is not allowed to use tool '{tool_name}'."
            )

        return claude_callback
    else:
        # OpenAI/Gemini/Ollama callback: returns bool
        async def bool_callback(tool_name: str, _tool_name2: str = "", tool_input: dict = None) -> bool:
            return _is_tool_allowed(
                tool_name, max_level, allow_all_tools, tools_allowed,
                allow_all_plugins, plugins_allowed,
            )

        return bool_callback


# ---------------------------------------------------------------------------
# Structured output instructions (injected into system prompt for Claude)
# ---------------------------------------------------------------------------

def _build_actions_prompt(delegate_section: str = "") -> str:
    """Build the actions prompt instructing the director to emit structured output."""
    actions_path = str(_get_actions_file_path()).replace("\\", "/")
    return (
        "\n\n## Director Actions (MANDATORY)\n\n"
        "You are running as an autonomous director. You MUST output your actions so "
        "your deliverables get saved and tasks get delegated.\n\n"
        "You have TWO options (try both — at least one must work):\n\n"
        f"**Option A (preferred):** Write the JSON array to the file `{actions_path}`\n\n"
        "**Option B (fallback):** Include the JSON at the very end of your text response "
        "between these exact markers:\n\n"
        "RAIN_ACTIONS_START\n"
        "[your JSON array here]\n"
        "RAIN_ACTIONS_END\n\n"
        "### JSON format — array of action objects:\n\n"
        "Action types:\n\n"
        "1. **save_to_inbox** (REQUIRED — always include at least one):\n"
        '   - action: "save_to_inbox"\n'
        "   - title: descriptive title string\n"
        "   - content: FULL markdown deliverable (not a summary!)\n"
        '   - content_type: "report" or "draft" or "analysis" or "code" or "notification"\n'
        "   - priority: number 1-10\n\n"
        "2. **update_my_context** (recommended — persist notes for next run):\n"
        '   - action: "update_my_context"\n'
        "   - key: context key name\n"
        "   - value: data to store\n\n"
        f"{delegate_section}"
        "### Rules:\n"
        "- Include at least one save_to_inbox action with your FULL deliverable\n"
        "- Use update_my_context to remember what you did for continuity between runs\n"
        "- Try Option A first. If writing the file fails, use Option B in your text output\n"
    )

_DELEGATE_SECTION = (
    "3. delegate_task (assign work to another director):\n"
    '   Fields: action, title, assignee (director ID), description, priority (1-10), '
    'task_type (analysis|content|code|review|report|custom)\n\n'
)


def _compose_director_prompt(director: dict, task: dict | None = None) -> str:
    """Build the director's system prompt for execution."""
    parts = [director["role_prompt"]]

    # Persistent context
    context = director.get("context_window", {})
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except (json.JSONDecodeError, TypeError):
            context = {}

    if context:
        parts.append("\n\n## Your Persistent Context")
        for k, v in context.items():
            parts.append(f"- **{k}**: {v}")

    # Available directors for delegation
    if director.get("can_delegate"):
        try:
            from .storage import list_directors
            others = list_directors(user_id=director.get("user_id", "default"), enabled_only=True)
            others = [d for d in others if d["id"] != director["id"]]
            if others:
                parts.append("\n\n## Available Directors for Delegation")
                for d in others:
                    parts.append(f"- **{d['id']}** ({d.get('emoji', '')} {d['name']}): {d.get('description', 'N/A')}")
        except Exception:
            pass

    # Task-specific instructions
    if task:
        parts.append("\n\n## Current Task (Delegated to You)")
        parts.append(f"**Title**: {task['title']}")
        if task.get("description"):
            parts.append(f"**Description**: {task['description']}")
        input_data = task.get("input_data", {})
        if input_data:
            parts.append(f"**Input Data**: {json.dumps(input_data, indent=2)}")
        parts.append(f"**Priority**: {task.get('priority', 5)}/10")
        parts.append(f"**Type**: {task.get('task_type', 'analysis')}")
    else:
        parts.append("\n\n## Execution Mode: Scheduled Run")
        parts.append("This is an autonomous scheduled execution. Follow your role's workflow.")

    # Structured output instructions for actions
    delegate_section = _DELEGATE_SECTION if director.get("can_delegate") else ""
    parts.append(_build_actions_prompt(delegate_section))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Post-processing: parse and execute actions from response
# ---------------------------------------------------------------------------

def _get_actions_file_path() -> Path:
    """Get the path for the director actions file (cross-platform)."""
    if os.name == "nt":
        return Path.home() / ".rain-assistant" / "director_actions.json"
    return Path("/tmp/rain_director_actions.json")


def _read_actions_file() -> list[dict]:
    """Read actions from the file the director wrote."""
    actions_file = _get_actions_file_path()
    try:
        if not actions_file.exists():
            return []
        raw = actions_file.read_text(encoding="utf-8")
        # Clean up and delete file
        actions_file.unlink(missing_ok=True)
        actions = json.loads(raw)
        if isinstance(actions, dict):
            actions = [actions]
        if isinstance(actions, list):
            return actions
        return []
    except (json.JSONDecodeError, OSError, TypeError) as e:
        logger.warning("[DIRECTORS] Failed to read actions file: %s", e)
        return []


def _extract_actions(text: str) -> list[dict]:
    """Extract the structured actions block from the director's response."""
    match = _ACTIONS_RE.search(text)
    if not match:
        match = _ACTIONS_RE_FALLBACK.search(text)
    if not match:
        return []

    raw = match.group(1).strip()
    try:
        actions = json.loads(raw)
        if isinstance(actions, dict):
            actions = [actions]
        if not isinstance(actions, list):
            return []
        return actions
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("[DIRECTORS] Failed to parse actions JSON: %s", e)
        return []


def _strip_actions_block(text: str) -> str:
    """Remove the actions block from the response text (for clean display)."""
    text = _ACTIONS_RE.sub("", text)
    text = _ACTIONS_RE_FALLBACK.sub("", text)
    return text.rstrip()


def _execute_actions(
    actions: list[dict],
    director: dict,
    task: dict | None,
    user_id: str,
) -> dict:
    """Execute parsed actions (save_to_inbox, delegate_task, update_my_context).

    Returns a summary dict with counts.
    """
    from .task_queue import create_task
    from .inbox import add_inbox_item
    from .storage import update_context

    director_id = director["id"]
    director_name = director.get("name", director_id)

    summary = {"inbox_saved": 0, "tasks_delegated": 0, "context_updated": 0, "errors": []}

    for action_data in actions:
        action = action_data.get("action", "")

        try:
            if action == "save_to_inbox":
                title = action_data.get("title", "").strip()
                content = action_data.get("content", "").strip()
                if not title or not content:
                    summary["errors"].append("save_to_inbox: missing title or content")
                    continue

                add_inbox_item(
                    director_id=director_id,
                    director_name=director_name,
                    title=title,
                    content=content,
                    content_type=action_data.get("content_type", "report"),
                    priority=action_data.get("priority", 5),
                    task_id=task["id"] if task else None,
                    metadata={"trigger": "director_action", "director": director_id},
                    user_id=user_id,
                )
                summary["inbox_saved"] += 1
                logger.info("[DIRECTORS] %s saved to inbox: '%s'", director_id, title)

            elif action == "delegate_task":
                if not director.get("can_delegate"):
                    summary["errors"].append("delegate_task: director cannot delegate")
                    continue

                assignee = action_data.get("assignee", "").strip()
                title = action_data.get("title", "").strip()
                if not assignee or not title:
                    summary["errors"].append("delegate_task: missing assignee or title")
                    continue

                create_task(
                    title=title,
                    creator_id=director_id,
                    assignee_id=assignee,
                    description=action_data.get("description", ""),
                    priority=action_data.get("priority", 5),
                    task_type=action_data.get("task_type", "analysis"),
                    input_data=action_data.get("input_data"),
                    user_id=user_id,
                )
                summary["tasks_delegated"] += 1
                logger.info("[DIRECTORS] %s delegated task '%s' to %s", director_id, title, assignee)

            elif action == "update_my_context":
                key = action_data.get("key", "").strip()
                value = action_data.get("value", "")
                if not key:
                    summary["errors"].append("update_my_context: missing key")
                    continue

                update_context(director_id, user_id=user_id, key=key, value=value)
                summary["context_updated"] += 1
                logger.info("[DIRECTORS] %s context updated: '%s'", director_id, key)

            else:
                summary["errors"].append(f"Unknown action: '{action}'")

        except Exception as e:
            err = f"{action}: {e}"
            summary["errors"].append(err)
            logger.error("[DIRECTORS] Action error: %s", err)

    return summary


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

async def execute_director(
    director: dict,
    trigger: str = "schedule",
    task: dict | None = None,
    user_id: str = "default",
) -> tuple[str | None, str | None, float]:
    """Execute a director using a temporary provider instance.

    Args:
        director: Director dict from storage.
        trigger: What triggered this execution ('schedule', 'manual', 'task').
        task: If executing a delegated task, the task dict.
        user_id: User ID for isolation.

    Returns:
        (result_text, error_text, cost) — one of result/error will be None.
    """
    from providers import get_provider
    import shared_state

    config = shared_state.config
    provider_name = config.get("default_provider", "claude")
    provider_keys_cfg = config.get("provider_keys", {})
    api_key = config.get("default_api_key", "")

    if isinstance(provider_keys_cfg, dict) and provider_name in provider_keys_cfg:
        api_key = provider_keys_cfg[provider_name]

    if not api_key:
        # Allow Claude provider to work without API key in OAuth mode (Claude Max/Pro)
        auth_mode = config.get("auth_mode", "api_key")
        if provider_name == "claude" and auth_mode == "oauth":
            logger.info("[DIRECTORS] Using Claude OAuth mode (no API key needed)")
            api_key = ""  # ClaudeProvider uses ~/.claude/.credentials.json
        else:
            msg = f"No API key configured for provider '{provider_name}'. Cannot execute director."
            logger.warning("[DIRECTORS] %s", msg)
            return None, msg, 0.0

    # Unset CLAUDECODE to allow nested sessions (when running inside Claude Code)
    env_backup = os.environ.pop("CLAUDECODE", None)

    # Clean up any leftover actions file from previous runs
    try:
        _get_actions_file_path().unlink(missing_ok=True)
    except OSError:
        pass

    provider = None
    start_time = time.time()
    cost = 0.0

    try:
        provider = get_provider(provider_name)

        system_prompt = _compose_director_prompt(director, task=task)
        cwd = str(Path.home())
        permission_callback = _build_permission_callback(director, provider_name=provider_name)

        await provider.initialize(
            api_key=api_key,
            model="auto",
            cwd=cwd,
            system_prompt=system_prompt,
            can_use_tool=permission_callback,
        )

        # For providers with _tool_executor (OpenAI, Gemini), register tool handlers
        _register_director_tools(provider, director, task, user_id)

        # Build the execution prompt
        if task:
            exec_prompt = (
                f"Execute the delegated task: {task['title']}\n\n"
                f"{task.get('description', '')}"
            )
        else:
            exec_prompt = (
                f"Execute your scheduled run. Today is {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. "
                f"Follow your role workflow and produce deliverables."
            )

        await provider.send_message(exec_prompt)

        # Collect response
        collected_text = ""
        async for event in provider.stream_response():
            if event.type == "assistant_text":
                collected_text += event.data.get("text", "")
            elif event.type == "result":
                result_text = event.data.get("text", "")
                if result_text:
                    collected_text = result_text
                # Extract cost if available
                usage = event.data.get("usage", {})
                cost = usage.get("cost", 0.0) or 0.0
            elif event.type == "error":
                error_text = event.data.get("text", "Unknown provider error")
                logger.error("[DIRECTORS] %s error: %s", director["id"], error_text)
                return None, error_text, cost

        if not collected_text:
            collected_text = "(empty response)"

        # Post-process: extract and execute structured actions
        # Strategy 1: Read from the file the director wrote
        actions = _read_actions_file()
        # Strategy 2: Parse inline markers from the response text
        if not actions:
            actions = _extract_actions(collected_text)
        if actions:
            summary = _execute_actions(actions, director, task, user_id)
            logger.info(
                "[DIRECTORS] %s actions: %d inbox, %d delegated, %d context, %d errors",
                director["id"],
                summary["inbox_saved"],
                summary["tasks_delegated"],
                summary["context_updated"],
                len(summary["errors"]),
            )
            # Clean the response text (remove the actions block)
            collected_text = _strip_actions_block(collected_text)
        else:
            # No structured actions found — auto-save entire response to inbox
            logger.info("[DIRECTORS] %s: no actions block found, auto-saving to inbox", director["id"])
            from .inbox import add_inbox_item
            add_inbox_item(
                director_id=director["id"],
                director_name=director.get("name", director["id"]),
                title=f"{director.get('emoji', '')} {director['name']} — {trigger} run",
                content=collected_text,
                content_type="report",
                priority=5,
                task_id=task["id"] if task else None,
                metadata={"trigger": trigger, "director": director["id"], "auto_saved": True},
                user_id=user_id,
            )

        duration = time.time() - start_time
        logger.info(
            "[DIRECTORS] %s completed (trigger=%s, %d chars, %.1fs, $%.4f)",
            director["id"], trigger, len(collected_text), duration, cost,
        )

        return collected_text, None, cost

    except Exception as e:
        error_msg = f"Director execution error ({provider_name}): {e}"
        logger.error("[DIRECTORS] %s failed: %s", director.get("id", "?"), error_msg)
        return None, error_msg, cost
    finally:
        # Restore CLAUDECODE env var
        if env_backup is not None:
            os.environ["CLAUDECODE"] = env_backup

        if provider:
            try:
                await provider.disconnect()
            except Exception:
                pass


def _register_director_tools(provider, director: dict, task: dict | None, user_id: str):
    """Register handler functions for director-specific tools on the provider's executor.

    This only works for providers that have a _tool_executor (OpenAI, Gemini, Ollama).
    For ClaudeProvider, actions are handled via structured output post-processing.
    """
    executor = getattr(provider, "_tool_executor", None)
    if not executor:
        return

    from .task_queue import create_task
    from .inbox import add_inbox_item
    from .storage import update_context

    director_id = director["id"]
    director_name = director.get("name", director_id)

    # delegate_task handler
    async def _handle_delegate_task(args: dict, cwd: str) -> dict:
        assignee = args.get("assignee", "")
        title = args.get("title", "")
        if not assignee or not title:
            return {"content": "Error: 'assignee' and 'title' are required", "is_error": True}

        new_task = create_task(
            title=title,
            creator_id=director_id,
            assignee_id=assignee,
            description=args.get("description", ""),
            priority=args.get("priority", 5),
            task_type=args.get("task_type", "analysis"),
            input_data=args.get("input_data"),
            user_id=user_id,
        )
        return {
            "content": f"Task '{title}' created and assigned to director '{assignee}' (id: {new_task['id']})",
            "is_error": False,
        }

    # save_to_inbox handler
    async def _handle_save_to_inbox(args: dict, cwd: str) -> dict:
        title = args.get("title", "")
        content = args.get("content", "")
        if not title or not content:
            return {"content": "Error: 'title' and 'content' are required", "is_error": True}

        item = add_inbox_item(
            director_id=director_id,
            director_name=director_name,
            title=title,
            content=content,
            content_type=args.get("content_type", "report"),
            priority=args.get("priority", 5),
            task_id=task["id"] if task else None,
            metadata={"trigger": "director_tool", "director": director_id},
            user_id=user_id,
        )
        return {
            "content": f"Saved to inbox: '{title}' (id: {item['id']})",
            "is_error": False,
        }

    # update_my_context handler
    async def _handle_update_context(args: dict, cwd: str) -> dict:
        key = args.get("key", "").strip()
        value = args.get("value", "")
        if not key:
            return {"content": "Error: 'key' is required", "is_error": True}

        result = update_context(director_id, user_id=user_id, key=key, value=value)
        if result is None:
            return {"content": "Error: Failed to update context", "is_error": True}

        action = "updated" if value else "removed"
        return {"content": f"Context key '{key}' {action}.", "is_error": False}

    # Register on the executor
    if director.get("can_delegate"):
        executor._handlers["delegate_task"] = _handle_delegate_task
    executor._handlers["save_to_inbox"] = _handle_save_to_inbox
    executor._handlers["update_my_context"] = _handle_update_context
