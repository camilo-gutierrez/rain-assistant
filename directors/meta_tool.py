"""manage_directors meta-tool — allows Rain to create and manage autonomous directors."""

import re
import time
from datetime import datetime, timezone

from .storage import (
    add_director,
    list_directors,
    get_director,
    update_director,
    delete_director,
    enable_director,
    disable_director,
    update_context,
)

# Reuse prompt validation from alter_egos
_SUSPICIOUS_PROMPT_PATTERNS = [
    "ignore all previous",
    "ignore previous instructions",
    "disregard all",
    "disregard previous",
    "forget your instructions",
    "override your",
    "you are now unrestricted",
    "no safety guidelines",
    "no restrictions",
    "jailbreak",
    "DAN mode",
    "developer mode override",
]

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,29}$")

_CRON_HELP = (
    "Cron format: 'minute hour day month weekday'. "
    "Examples: '0 3 * * *' (daily 3am), '0 9 * * 1' (Mon 9am), "
    "'0 */2 * * *' (every 2h). "
    "Aliases: '@hourly', '@daily', '@weekly', '@monthly'."
)


def _validate_role_prompt(prompt: str) -> str | None:
    """Check for suspicious prompt injection patterns. Returns error message or None."""
    if len(prompt) > 10000:
        return "Role prompt too long (max 10000 characters)"
    if len(prompt) < 20:
        return "Role prompt too short (min 20 characters). Describe the director's role in detail."
    prompt_lower = prompt.lower()
    for pattern in _SUSPICIOUS_PROMPT_PATTERNS:
        if pattern.lower() in prompt_lower:
            return f"Role prompt contains suspicious pattern: '{pattern}'"
    return None


MANAGE_DIRECTORS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_directors",
        "description": (
            "Create and manage autonomous AI directors. Directors are persistent AI agents "
            "with specific roles (strategy, content, development, marketing, etc.) that run "
            "on cron schedules WITHOUT user interaction. They can delegate tasks to each other "
            "and produce deliverables (reports, drafts, code) that appear in the user's inbox. "
            "Actions: create, list, show, edit, delete, enable, disable, run_now, set_context, templates. "
            + _CRON_HELP
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "show", "edit", "delete", "enable", "disable", "run_now", "set_context", "templates"],
                    "description": "Action to perform",
                },
                "id": {
                    "type": "string",
                    "description": "Director ID (lowercase, underscores, e.g. 'strategy', 'content_lead')",
                },
                "name": {
                    "type": "string",
                    "description": "Display name (e.g. 'Strategy Director')",
                },
                "emoji": {
                    "type": "string",
                    "description": "Emoji icon (e.g. '🎯')",
                },
                "description": {
                    "type": "string",
                    "description": "Short description of the director's role",
                },
                "role_prompt": {
                    "type": "string",
                    "description": "Full system prompt defining the director's behavior, expertise, and goals",
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron expression for autonomous execution. " + _CRON_HELP,
                },
                "tools_allowed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tool names this director can use. Use ['*'] for all tools. Default: ['*']",
                },
                "plugins_allowed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of plugin names this director can use. Use ['*'] for all. Default: ['*']",
                },
                "permission_level": {
                    "type": "string",
                    "enum": ["green", "yellow"],
                    "description": "Max tool permission level. 'green' = read-only, 'yellow' = read+write. Default: 'green'",
                },
                "can_delegate": {
                    "type": "boolean",
                    "description": "If true, this director can create tasks for other directors. Default: false",
                },
                "context_key": {
                    "type": "string",
                    "description": "Key for set_context action (e.g. 'last_analysis_date')",
                },
                "context_value": {
                    "type": "string",
                    "description": "Value for set_context action. Empty string removes the key.",
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_manage_directors(args: dict, cwd: str) -> dict:
    """Handle manage_directors tool calls from Rain."""
    action = args.get("action", "")
    user_id = args.pop("_user_id", "default")

    try:
        if action == "create":
            return _action_create(args, user_id)
        elif action == "list":
            return _action_list(user_id)
        elif action == "show":
            return _action_show(args, user_id)
        elif action == "edit":
            return _action_edit(args, user_id)
        elif action == "delete":
            return _action_delete(args, user_id)
        elif action == "enable":
            return _action_enable(args, user_id)
        elif action == "disable":
            return _action_disable(args, user_id)
        elif action == "run_now":
            return _action_run_now(args, user_id)
        elif action == "set_context":
            return _action_set_context(args, user_id)
        elif action == "templates":
            return _action_templates()
        else:
            return {"content": f"Unknown action: {action}", "is_error": True}
    except Exception as e:
        return {"content": f"Error: {e}", "is_error": True}


def _format_time(ts: float | None) -> str:
    if not ts:
        return "never"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _format_director(d: dict, verbose: bool = False) -> str:
    """Format a director dict as a readable string."""
    status = "ENABLED" if d.get("enabled") else "DISABLED"
    lines = [
        f"  {d.get('emoji', '🤖')} {d['name']} [{d['id']}]",
        f"  Status: {status}",
        f"  Schedule: {d.get('schedule') or 'manual only'}",
        f"  Permission: {d.get('permission_level', 'green')}",
        f"  Can delegate: {'Yes' if d.get('can_delegate') else 'No'}",
        f"  Runs: {d.get('run_count', 0)} | Cost: ${d.get('total_cost', 0):.4f}",
    ]
    if d.get("description"):
        lines.insert(2, f"  Description: {d['description']}")

    lines.append(f"  Next run: {_format_time(d.get('next_run'))}")
    lines.append(f"  Last run: {_format_time(d.get('last_run'))}")

    if verbose:
        tools = d.get("tools_allowed", ["*"])
        plugins = d.get("plugins_allowed", ["*"])
        lines.append(f"  Tools: {', '.join(tools)}")
        lines.append(f"  Plugins: {', '.join(plugins)}")

        context = d.get("context_window", {})
        if context:
            lines.append("  Context:")
            for k, v in context.items():
                val_preview = str(v)[:100]
                lines.append(f"    {k}: {val_preview}")

        if d.get("last_error"):
            err = d["last_error"][:500] + "..." if len(d["last_error"]) > 500 else d["last_error"]
            lines.append(f"  Last error: {err}")
        if d.get("last_result"):
            res = d["last_result"][:500] + "..." if len(d["last_result"]) > 500 else d["last_result"]
            lines.append(f"  Last result: {res}")

    return "\n".join(lines)


def _action_create(args: dict, user_id: str) -> dict:
    director_id = args.get("id", "").strip().lower()
    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}
    if not _ID_PATTERN.match(director_id):
        return {"content": "Error: ID must be lowercase letters, numbers, underscores (max 30 chars, start with letter)", "is_error": True}

    role_prompt = args.get("role_prompt", "").strip()
    if not role_prompt:
        return {"content": "Error: 'role_prompt' is required — describe the director's role, expertise, and goals", "is_error": True}

    validation_error = _validate_role_prompt(role_prompt)
    if validation_error:
        return {"content": f"Error: {validation_error}", "is_error": True}

    name = args.get("name", director_id.replace("_", " ").title())
    schedule = args.get("schedule", "").strip() or None
    permission_level = args.get("permission_level", "green")
    if permission_level not in ("green", "yellow"):
        return {"content": "Error: permission_level must be 'green' or 'yellow'", "is_error": True}

    director = add_director(
        id=director_id,
        name=name,
        role_prompt=role_prompt,
        schedule=schedule,
        description=args.get("description", ""),
        emoji=args.get("emoji", "🤖"),
        tools_allowed=args.get("tools_allowed"),
        plugins_allowed=args.get("plugins_allowed"),
        permission_level=permission_level,
        can_delegate=args.get("can_delegate", False),
        user_id=user_id,
    )

    if director is None:
        return {
            "content": (
                f"Error: Could not create director. "
                f"Either the ID '{director_id}' already exists or the cron expression is invalid. "
                + _CRON_HELP
            ),
            "is_error": True,
        }

    return {
        "content": f"Director created successfully!\n{_format_director(director, verbose=True)}",
        "is_error": False,
    }


def _action_list(user_id: str) -> dict:
    directors = list_directors(user_id=user_id)
    if not directors:
        return {"content": "No directors configured. Use action 'templates' to see available templates, or 'create' to make one.", "is_error": False}

    lines = [f"Autonomous Directors ({len(directors)}):"]
    for d in directors:
        status = "ON" if d.get("enabled") else "OFF"
        schedule = d.get("schedule") or "manual"
        next_str = _format_time(d.get("next_run"))
        runs = d.get("run_count", 0)
        cost = d.get("total_cost", 0)
        delegate = " [DELEGATOR]" if d.get("can_delegate") else ""
        err = " [LAST: ERROR]" if d.get("last_error") else ""
        lines.append(
            f"  [{status}] {d.get('emoji', '🤖')} {d['name']} ({d['id']}) — {schedule} "
            f"— next: {next_str} — runs: {runs} — ${cost:.4f}{delegate}{err}"
        )

    return {"content": "\n".join(lines), "is_error": False}


def _action_show(args: dict, user_id: str) -> dict:
    director_id = args.get("id", "")
    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    director = get_director(director_id, user_id=user_id)
    if not director:
        return {"content": f"Director '{director_id}' not found.", "is_error": True}

    return {"content": _format_director(director, verbose=True), "is_error": False}


def _action_edit(args: dict, user_id: str) -> dict:
    director_id = args.get("id", "")
    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    existing = get_director(director_id, user_id=user_id)
    if not existing:
        return {"content": f"Director '{director_id}' not found.", "is_error": True}

    if "role_prompt" in args and args["role_prompt"]:
        validation_error = _validate_role_prompt(args["role_prompt"])
        if validation_error:
            return {"content": f"Error: {validation_error}", "is_error": True}

    if "permission_level" in args and args["permission_level"] not in ("green", "yellow"):
        return {"content": "Error: permission_level must be 'green' or 'yellow'", "is_error": True}

    kwargs = {}
    for field in ("name", "emoji", "description", "role_prompt", "schedule",
                   "tools_allowed", "plugins_allowed", "permission_level"):
        if field in args and args[field] is not None:
            kwargs[field] = args[field]
    if "can_delegate" in args:
        kwargs["can_delegate"] = args["can_delegate"]

    if not kwargs:
        return {"content": "No fields to update.", "is_error": True}

    director = update_director(director_id, user_id=user_id, **kwargs)
    if director is None:
        return {"content": f"Failed to update director. Check cron expression.", "is_error": True}

    return {"content": f"Director updated:\n{_format_director(director, verbose=True)}", "is_error": False}


def _action_delete(args: dict, user_id: str) -> dict:
    director_id = args.get("id", "")
    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    if delete_director(director_id, user_id=user_id):
        return {"content": f"Director '{director_id}' deleted.", "is_error": False}
    return {"content": f"Director '{director_id}' not found.", "is_error": True}


def _action_enable(args: dict, user_id: str) -> dict:
    director_id = args.get("id", "")
    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    director = enable_director(director_id, user_id=user_id)
    if director is None:
        return {"content": f"Director '{director_id}' not found.", "is_error": True}
    return {
        "content": f"Director '{director_id}' enabled. Next run: {_format_time(director.get('next_run'))}",
        "is_error": False,
    }


def _action_disable(args: dict, user_id: str) -> dict:
    director_id = args.get("id", "")
    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    director = disable_director(director_id, user_id=user_id)
    if director is None:
        return {"content": f"Director '{director_id}' not found.", "is_error": True}
    return {"content": f"Director '{director_id}' disabled.", "is_error": False}


def _action_run_now(args: dict, user_id: str) -> dict:
    """Flag a director for immediate execution by the scheduler loop."""
    director_id = args.get("id", "")
    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    director = get_director(director_id, user_id=user_id)
    if not director:
        return {"content": f"Director '{director_id}' not found.", "is_error": True}
    if not director.get("enabled"):
        return {"content": f"Director '{director_id}' is disabled. Enable it first.", "is_error": True}

    # Set next_run to now so the scheduler picks it up on next cycle (within 30s)
    from .storage import _get_db
    now = time.time()
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE directors SET next_run = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (now, now, director_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "content": f"Director '{director['name']}' queued for immediate execution. It will run within the next 30 seconds.",
        "is_error": False,
    }


def _action_set_context(args: dict, user_id: str) -> dict:
    director_id = args.get("id", "")
    key = args.get("context_key", "").strip()
    value = args.get("context_value", "")

    if not director_id:
        return {"content": "Error: 'id' is required", "is_error": True}
    if not key:
        return {"content": "Error: 'context_key' is required", "is_error": True}

    director = update_context(director_id, user_id=user_id, key=key, value=value)
    if director is None:
        return {"content": f"Director '{director_id}' not found.", "is_error": True}

    action = "set" if value else "removed"
    return {"content": f"Context key '{key}' {action} for director '{director_id}'.", "is_error": False}


def _action_templates() -> dict:
    """Show available built-in director templates."""
    from .builtin import DIRECTOR_TEMPLATES

    lines = ["Available director templates:"]
    for t in DIRECTOR_TEMPLATES:
        lines.append(f"\n  {t['emoji']} **{t['name']}** (id: {t['id']})")
        lines.append(f"    {t['description']}")
        lines.append(f"    Schedule: {t.get('schedule', 'manual')}")
        lines.append(f"    Permission: {t.get('permission_level', 'green')}")
        lines.append(f"    Delegates: {'Yes' if t.get('can_delegate') else 'No'}")

    lines.append("\nTo install a template: use action 'create' with the template's id and customize as needed.")
    return {"content": "\n".join(lines), "is_error": False}
