"""manage_scheduled_tasks meta-tool — allows Rain to create and manage scheduled/recurring tasks."""

import time
from datetime import datetime, timezone

from .storage import (
    add_task,
    list_tasks,
    get_task,
    update_task,
    delete_task,
    enable_task,
    disable_task,
)

# Common cron aliases for the AI to use
_CRON_HELP = (
    "Cron format: 'minute hour day month weekday'. "
    "Examples: '0 9 * * 1' (Mon 9am), '0 8 * * *' (daily 8am), "
    "'0 */2 * * *' (every 2h), '30 14 1 * *' (1st of month 2:30pm). "
    "Aliases: '@hourly', '@daily', '@weekly', '@monthly'."
)

MANAGE_SCHEDULED_TASKS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_scheduled_tasks",
        "description": (
            "Create and manage scheduled/recurring tasks. Use this when the user "
            "says things like 'remind me every Monday', 'run X every hour', "
            "'schedule a daily check', etc. Tasks persist across sessions and "
            "execute automatically at their scheduled times. "
            "Task types: 'reminder' (sends a message to the user), "
            "'bash' (runs a shell command), 'ai_prompt' (Rain processes a prompt). "
            + _CRON_HELP
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "show", "update", "delete", "enable", "disable"],
                    "description": "Action to perform",
                },
                "name": {
                    "type": "string",
                    "description": "Task name (for 'create'/'update')",
                },
                "schedule": {
                    "type": "string",
                    "description": (
                        "Cron expression for when to run. " + _CRON_HELP
                    ),
                },
                "task_type": {
                    "type": "string",
                    "enum": ["reminder", "bash", "ai_prompt"],
                    "description": "Type of task (default: 'reminder')",
                },
                "description": {
                    "type": "string",
                    "description": "Longer description of the task",
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message (for task_type 'reminder')",
                },
                "command": {
                    "type": "string",
                    "description": "Shell command (for task_type 'bash')",
                },
                "prompt": {
                    "type": "string",
                    "description": "AI prompt to process (for task_type 'ai_prompt')",
                },
                "id": {
                    "type": "string",
                    "description": "Task ID (for 'show'/'update'/'delete'/'enable'/'disable')",
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_manage_scheduled_tasks(args: dict, cwd: str) -> dict:
    """Handle manage_scheduled_tasks tool calls from Rain."""
    action = args.get("action", "")
    # Extract user_id injected by ToolExecutor (defaults to "default" for backward compat)
    user_id = args.pop("_user_id", "default")

    try:
        if action == "create":
            return _action_create(args, user_id=user_id)
        elif action == "list":
            return _action_list(user_id=user_id)
        elif action == "show":
            return _action_show(args, user_id=user_id)
        elif action == "update":
            return _action_update(args, user_id=user_id)
        elif action == "delete":
            return _action_delete(args, user_id=user_id)
        elif action == "enable":
            return _action_enable(args, user_id=user_id)
        elif action == "disable":
            return _action_disable(args, user_id=user_id)
        else:
            return {"content": f"Unknown action: {action}", "is_error": True}
    except Exception as e:
        return {"content": f"Error: {e}", "is_error": True}


def _format_time(ts: float | None) -> str:
    """Format a Unix timestamp as a human-readable string."""
    if not ts:
        return "never"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _format_task(task: dict, include_result: bool = True) -> str:
    """Format a task dict as a readable string.

    Args:
        task: Task dict from storage.
        include_result: Whether to include last_result/last_error (verbose mode).
    """
    status = "ENABLED" if task.get("enabled") else "DISABLED"
    lines = [
        f"  ID: {task['id']}",
        f"  Name: {task['name']}",
        f"  Status: {status}",
        f"  Schedule: {task['schedule']}",
        f"  Type: {task['task_type']}",
    ]
    if task.get("description"):
        lines.append(f"  Description: {task['description']}")

    data = task.get("task_data", {})
    if data.get("message"):
        lines.append(f"  Message: {data['message']}")
    if data.get("command"):
        lines.append(f"  Command: {data['command']}")
    if data.get("prompt"):
        lines.append(f"  Prompt: {data['prompt']}")

    lines.append(f"  Next run: {_format_time(task.get('next_run'))}")
    lines.append(f"  Last run: {_format_time(task.get('last_run'))}")

    if include_result:
        last_error = task.get("last_error")
        last_result = task.get("last_result")
        if last_error:
            # Truncate long errors for display
            err_display = last_error[:500] + "..." if len(last_error) > 500 else last_error
            lines.append(f"  Last error: {err_display}")
        if last_result:
            # Truncate long results for display
            res_display = last_result[:500] + "..." if len(last_result) > 500 else last_result
            lines.append(f"  Last result: {res_display}")

    return "\n".join(lines)


def _action_create(args: dict, user_id: str = "default") -> dict:
    name = args.get("name", "").strip()
    schedule = args.get("schedule", "").strip()

    if not name:
        return {"content": "Error: 'name' is required", "is_error": True}
    if not schedule:
        return {"content": "Error: 'schedule' (cron expression) is required", "is_error": True}

    task_type = args.get("task_type", "reminder")

    # Build task_data from type-specific fields
    task_data = {}
    if task_type == "reminder":
        task_data["message"] = args.get("message", args.get("description", name))
    elif task_type == "bash":
        cmd = args.get("command", "")
        if not cmd:
            return {"content": "Error: 'command' is required for bash tasks", "is_error": True}
        task_data["command"] = cmd
    elif task_type == "ai_prompt":
        prompt = args.get("prompt", "")
        if not prompt:
            return {"content": "Error: 'prompt' is required for ai_prompt tasks", "is_error": True}
        task_data["prompt"] = prompt

    task = add_task(
        name=name,
        schedule=schedule,
        task_type=task_type,
        description=args.get("description", ""),
        task_data=task_data,
        user_id=user_id,
    )

    if task is None:
        return {
            "content": (
                f"Error: Invalid cron expression '{schedule}'. "
                "Use format: 'minute hour day month weekday' "
                "(e.g., '0 9 * * 1' for Monday 9am). "
                "Make sure croniter is installed: pip install rain-assistant[scheduler]"
            ),
            "is_error": True,
        }

    return {
        "content": (
            f"Task created successfully!\n{_format_task(task)}"
        ),
        "is_error": False,
    }


def _action_list(user_id: str = "default") -> dict:
    tasks = list_tasks(user_id=user_id)
    if not tasks:
        return {"content": "No scheduled tasks.", "is_error": False}

    lines = [f"Scheduled tasks ({len(tasks)} total):"]
    for t in tasks:
        status = "ON" if t.get("enabled") else "OFF"
        next_str = _format_time(t.get("next_run"))
        last_str = _format_time(t.get("last_run"))
        # Brief execution status indicator
        exec_status = ""
        if t.get("last_error"):
            exec_status = " [LAST RUN: ERROR]"
        elif t.get("last_result"):
            exec_status = " [LAST RUN: OK]"
        lines.append(
            f"  [{status}] {t['name']} (id: {t['id']}) — {t['schedule']} "
            f"— next: {next_str} — last: {last_str}{exec_status}"
        )

    return {"content": "\n".join(lines), "is_error": False}


def _action_show(args: dict, user_id: str = "default") -> dict:
    task_id = args.get("id", "")
    if not task_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    task = get_task(task_id, user_id=user_id)
    if not task:
        return {"content": f"Task '{task_id}' not found.", "is_error": True}

    return {"content": _format_task(task), "is_error": False}


def _action_update(args: dict, user_id: str = "default") -> dict:
    task_id = args.get("id", "")
    if not task_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    kwargs = {}
    for field in ("name", "description", "schedule", "task_type"):
        if field in args and args[field]:
            kwargs[field] = args[field]

    # Rebuild task_data if type-specific fields are provided
    if any(k in args for k in ("message", "command", "prompt")):
        task_data = {}
        if args.get("message"):
            task_data["message"] = args["message"]
        if args.get("command"):
            task_data["command"] = args["command"]
        if args.get("prompt"):
            task_data["prompt"] = args["prompt"]
        kwargs["task_data"] = task_data

    task = update_task(task_id, user_id=user_id, **kwargs)
    if task is None:
        return {"content": f"Failed to update task '{task_id}'. Check cron expression.", "is_error": True}

    return {"content": f"Task updated:\n{_format_task(task)}", "is_error": False}


def _action_delete(args: dict, user_id: str = "default") -> dict:
    task_id = args.get("id", "")
    if not task_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    if delete_task(task_id, user_id=user_id):
        return {"content": f"Task '{task_id}' deleted.", "is_error": False}
    return {"content": f"Task '{task_id}' not found.", "is_error": True}


def _action_enable(args: dict, user_id: str = "default") -> dict:
    task_id = args.get("id", "")
    if not task_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    task = enable_task(task_id, user_id=user_id)
    if task is None:
        return {"content": f"Task '{task_id}' not found.", "is_error": True}
    return {
        "content": f"Task '{task_id}' enabled. Next run: {_format_time(task.get('next_run'))}",
        "is_error": False,
    }


def _action_disable(args: dict, user_id: str = "default") -> dict:
    task_id = args.get("id", "")
    if not task_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    task = disable_task(task_id, user_id=user_id)
    if task is None:
        return {"content": f"Task '{task_id}' not found.", "is_error": True}
    return {"content": f"Task '{task_id}' disabled.", "is_error": False}
