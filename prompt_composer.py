"""
Prompt Composer — builds the final system prompt from alter ego + memories.

This is the single source of truth for Rain's system prompt. Both server.py
and telegram_bot.py call compose_system_prompt() instead of using a hardcoded
constant.
"""

from alter_egos.storage import load_ego, get_active_ego_id, ensure_builtin_egos
from memories.storage import load_memories as _load_memories

# Fallback system prompt (used only if all else fails)
_FALLBACK_PROMPT = (
    "Your name is Rain. You are a friendly, tech-savvy coding assistant. "
    "When greeting the user for the first time in a conversation, introduce yourself as Rain. "
    "Use a warm and casual tone -- like a knowledgeable friend who's an expert developer. "
    "You can be a little playful, but always stay helpful and focused. "
    "Use the name 'Rain' naturally when referring to yourself. "
    "Respond in the same language the user writes in."
)


def compose_system_prompt(
    ego_id: str | None = None,
    memories: list[dict] | None = None,
) -> str:
    """
    Build the final system prompt.

    Args:
        ego_id: Alter ego ID to use. If None, uses the globally active ego.
        memories: List of memory dicts. If None, loads from disk.

    Returns:
        Complete system prompt string = ego.system_prompt + formatted memories.
    """
    # Ensure built-in egos exist
    ensure_builtin_egos()

    # Resolve ego
    resolved_ego_id = ego_id or get_active_ego_id()
    ego = load_ego(resolved_ego_id)

    if ego and ego.get("system_prompt"):
        prompt = ego["system_prompt"]
    else:
        prompt = _FALLBACK_PROMPT

    # Resolve memories
    if memories is None:
        memories = _load_memories()

    if memories:
        prompt += "\n\n## User Memories & Preferences\n"
        prompt += "The following are things you should remember about this user:\n"
        for m in memories:
            category = m.get("category", "fact")
            content = m.get("content", "")
            if content:
                prompt += f"- [{category}] {content}\n"

    return prompt
