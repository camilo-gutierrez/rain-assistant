"""manage_memories meta-tool — allows Rain to remember user preferences and facts."""

from .storage import (
    load_memories,
    add_memory,
    remove_memory,
    clear_memories,
    search_memories,
)

MANAGE_MEMORIES_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_memories",
        "description": (
            "Remember and manage facts, preferences, and patterns about the user. "
            "Use this tool when the user says things like 'remember that...', "
            "'I prefer...', 'I always use...', or when you detect an important "
            "preference worth remembering. Memories persist across sessions and "
            "help Rain provide more personalized assistance. "
            "Categories: 'preference' (coding style, tools), 'fact' (about the user), "
            "'pattern' (recurring behaviors), 'project' (project-specific info)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "clear", "search"],
                    "description": "Action to perform",
                },
                "content": {
                    "type": "string",
                    "description": "Memory content text (required for 'add')",
                },
                "category": {
                    "type": "string",
                    "enum": ["preference", "fact", "pattern", "project"],
                    "description": "Memory category (for 'add', default: 'fact')",
                },
                "id": {
                    "type": "string",
                    "description": "Memory ID (required for 'remove')",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for 'search')",
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_manage_memories(args: dict, cwd: str) -> dict:
    """Handle manage_memories tool calls from Rain.

    The caller may inject ``_user_id`` into *args* for per-user isolation.
    If absent, falls back to ``"default"`` for backward compatibility.
    """
    action = args.get("action", "")
    user_id = args.pop("_user_id", "default")

    try:
        if action == "add":
            return _action_add(args, user_id)
        elif action == "list":
            return _action_list(user_id)
        elif action == "remove":
            return _action_remove(args, user_id)
        elif action == "clear":
            return _action_clear(user_id)
        elif action == "search":
            return _action_search(args, user_id)
        else:
            return {"content": f"Unknown action: {action}", "is_error": True}
    except Exception as e:
        return {"content": f"Error: {e}", "is_error": True}


def _action_add(args: dict, user_id: str = "default") -> dict:
    content = args.get("content", "").strip()
    if not content:
        return {"content": "Error: 'content' is required for add action", "is_error": True}

    category = args.get("category", "fact")
    memory = add_memory(content, category, user_id=user_id)
    return {
        "content": (
            f"Memory saved [{memory['category']}]: \"{memory['content']}\" "
            f"(id: {memory['id']})"
        ),
        "is_error": False,
    }


def _action_list(user_id: str = "default") -> dict:
    memories = load_memories(user_id=user_id)
    if not memories:
        return {"content": "No memories stored yet.", "is_error": False}

    # Group by category
    by_cat: dict[str, list[dict]] = {}
    for m in memories:
        cat = m.get("category", "fact")
        by_cat.setdefault(cat, []).append(m)

    lines = [f"Stored memories ({len(memories)} total):"]
    for cat, mems in sorted(by_cat.items()):
        lines.append(f"\n  [{cat}]")
        for m in mems:
            lines.append(f"    - {m['content']}  (id: {m['id']})")

    return {"content": "\n".join(lines), "is_error": False}


def _action_remove(args: dict, user_id: str = "default") -> dict:
    memory_id = args.get("id", "")
    if not memory_id:
        return {"content": "Error: 'id' is required for remove action", "is_error": True}

    if remove_memory(memory_id, user_id=user_id):
        return {"content": f"Memory '{memory_id}' removed.", "is_error": False}
    return {"content": f"Memory '{memory_id}' not found.", "is_error": True}


def _action_clear(user_id: str = "default") -> dict:
    count = clear_memories(user_id=user_id)
    if count == 0:
        return {"content": "No memories to clear.", "is_error": False}
    return {"content": f"Cleared {count} memories.", "is_error": False}


def _action_search(args: dict, user_id: str = "default") -> dict:
    query = args.get("query", "")
    if not query:
        return {"content": "Error: 'query' is required for search action", "is_error": True}

    results = search_memories(query, user_id=user_id)
    if not results:
        return {"content": f"No memories matching '{query}'.", "is_error": False}

    lines = [f"Found {len(results)} memories matching '{query}':"]
    for m in results:
        lines.append(f"  - [{m.get('category', 'fact')}] {m['content']}  (id: {m['id']})")

    return {"content": "\n".join(lines), "is_error": False}
