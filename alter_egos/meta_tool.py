"""manage_alter_egos meta-tool — allows Rain to manage its own personalities."""

from .storage import (
    load_all_egos,
    load_ego,
    save_ego,
    delete_ego,
    get_active_ego_id,
    set_active_ego_id,
)

# Flag for signaling that an ego change needs agent re-init
_ego_change_pending = False
_pending_ego_id: str | None = None


def is_ego_change_pending() -> bool:
    return _ego_change_pending


def get_pending_ego_id() -> str | None:
    return _pending_ego_id


def clear_ego_change_flag() -> None:
    global _ego_change_pending, _pending_ego_id
    _ego_change_pending = False
    _pending_ego_id = None


def _mark_ego_change(ego_id: str) -> None:
    global _ego_change_pending, _pending_ego_id
    _ego_change_pending = True
    _pending_ego_id = ego_id


MANAGE_ALTER_EGOS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_alter_egos",
        "description": (
            "Manage Rain's alter egos (switchable personalities). Each ego has a unique "
            "system prompt that changes Rain's behavior and style. Use 'activate' to switch "
            "personality. Built-in egos: rain (default), professor (pedagogical), speed "
            "(ultra-concise), security (vulnerability-focused), rubber_duck (Socratic). "
            "Users can create custom egos with their own system prompts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "show", "create", "edit", "delete", "activate"],
                    "description": "Action to perform",
                },
                "id": {
                    "type": "string",
                    "description": "Ego ID (required for show/edit/delete/activate)",
                },
                "name": {
                    "type": "string",
                    "description": "Display name (for create/edit)",
                },
                "emoji": {
                    "type": "string",
                    "description": "Emoji icon (for create/edit)",
                },
                "description": {
                    "type": "string",
                    "description": "Short description (for create/edit)",
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Full system prompt (for create/edit)",
                },
                "color": {
                    "type": "string",
                    "description": "Hex color code (for create/edit, e.g. '#3b82f6')",
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_manage_alter_egos(args: dict, cwd: str) -> dict:
    """Handle manage_alter_egos tool calls from Rain."""
    action = args.get("action", "")

    try:
        if action == "list":
            return _action_list()
        elif action == "show":
            return _action_show(args)
        elif action == "create":
            return _action_create(args)
        elif action == "edit":
            return _action_edit(args)
        elif action == "delete":
            return _action_delete(args)
        elif action == "activate":
            return _action_activate(args)
        else:
            return {"content": f"Unknown action: {action}", "is_error": True}
    except Exception as e:
        return {"content": f"Error: {e}", "is_error": True}


def _action_list() -> dict:
    egos = load_all_egos()
    active_id = get_active_ego_id()

    if not egos:
        return {"content": "No alter egos found.", "is_error": False}

    lines = [f"Available alter egos ({len(egos)}):"]
    for ego in egos:
        active_marker = " << ACTIVE" if ego["id"] == active_id else ""
        builtin = " (built-in)" if ego.get("is_builtin") else " (custom)"
        lines.append(
            f"  {ego.get('emoji', '🤖')} {ego['name']} [{ego['id']}]{builtin}{active_marker}"
        )
        if ego.get("description"):
            lines.append(f"      {ego['description']}")

    return {"content": "\n".join(lines), "is_error": False}


def _action_show(args: dict) -> dict:
    ego_id = args.get("id", "")
    if not ego_id:
        return {"content": "Error: 'id' is required", "is_error": True}

    ego = load_ego(ego_id)
    if not ego:
        return {"content": f"Ego '{ego_id}' not found.", "is_error": True}

    lines = [
        f"{ego.get('emoji', '🤖')} **{ego['name']}** [{ego['id']}]",
        f"Description: {ego.get('description', 'N/A')}",
        f"Color: {ego.get('color', '#6b7280')}",
        f"Built-in: {'Yes' if ego.get('is_builtin') else 'No'}",
        f"Active: {'Yes' if ego['id'] == get_active_ego_id() else 'No'}",
        f"\nSystem Prompt:\n```\n{ego['system_prompt']}\n```",
    ]

    return {"content": "\n".join(lines), "is_error": False}


def _action_create(args: dict) -> dict:
    ego_id = args.get("id", "")
    if not ego_id:
        return {"content": "Error: 'id' is required for create action", "is_error": True}

    system_prompt = args.get("system_prompt", "")
    if not system_prompt:
        return {"content": "Error: 'system_prompt' is required for create action", "is_error": True}

    name = args.get("name", ego_id.replace("_", " ").title())

    # Check if already exists
    if load_ego(ego_id):
        return {"content": f"Error: Ego '{ego_id}' already exists. Use 'edit' to modify it.", "is_error": True}

    ego_dict = {
        "id": ego_id,
        "name": name,
        "emoji": args.get("emoji", "\U0001f916"),
        "description": args.get("description", ""),
        "system_prompt": system_prompt,
        "color": args.get("color", "#6b7280"),
        "is_builtin": False,
    }

    path = save_ego(ego_dict)
    return {
        "content": f"Alter ego '{name}' created successfully at {path}.",
        "is_error": False,
    }


def _action_edit(args: dict) -> dict:
    ego_id = args.get("id", "")
    if not ego_id:
        return {"content": "Error: 'id' is required for edit action", "is_error": True}

    existing = load_ego(ego_id)
    if not existing:
        return {"content": f"Ego '{ego_id}' not found.", "is_error": True}

    # Update only provided fields
    updatable = ["name", "emoji", "description", "system_prompt", "color"]
    changed = []
    for field in updatable:
        if field in args and args[field]:
            existing[field] = args[field]
            changed.append(field)

    if not changed:
        return {"content": "No fields to update. Provide at least one of: name, emoji, description, system_prompt, color", "is_error": True}

    save_ego(existing)

    # If editing the active ego, flag for re-init
    if ego_id == get_active_ego_id() and "system_prompt" in changed:
        _mark_ego_change(ego_id)

    return {
        "content": f"Ego '{ego_id}' updated (fields: {', '.join(changed)}).",
        "is_error": False,
    }


def _action_delete(args: dict) -> dict:
    ego_id = args.get("id", "")
    if not ego_id:
        return {"content": "Error: 'id' is required for delete action", "is_error": True}

    if delete_ego(ego_id):
        return {"content": f"Ego '{ego_id}' deleted.", "is_error": False}
    return {"content": f"Ego '{ego_id}' not found.", "is_error": True}


def _action_activate(args: dict) -> dict:
    ego_id = args.get("id", "")
    if not ego_id:
        return {"content": "Error: 'id' is required for activate action", "is_error": True}

    ego = load_ego(ego_id)
    if not ego:
        return {"content": f"Ego '{ego_id}' not found.", "is_error": True}

    current = get_active_ego_id()
    if current == ego_id:
        return {
            "content": f"{ego.get('emoji', '🤖')} Ego '{ego['name']}' is already active.",
            "is_error": False,
        }

    set_active_ego_id(ego_id)
    _mark_ego_change(ego_id)

    return {
        "content": (
            f"{ego.get('emoji', '🤖')} Switched to '{ego['name']}' ego. "
            f"The personality change will take effect on the next message or conversation."
        ),
        "is_error": False,
    }
