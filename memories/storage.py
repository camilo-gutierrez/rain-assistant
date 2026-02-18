"""Storage layer for Rain Memories — JSON-based persistent storage."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".rain-assistant"
MEMORIES_FILE = CONFIG_DIR / "memories.json"

VALID_CATEGORIES = {"preference", "fact", "pattern", "project"}


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_memories() -> list[dict]:
    """Load all memories from disk."""
    if not MEMORIES_FILE.exists():
        return []
    try:
        with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_memories(memories: list[dict]) -> None:
    """Write memories list to disk atomically."""
    _ensure_dir()
    tmp = MEMORIES_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(memories, f, indent=2, ensure_ascii=False)
    tmp.replace(MEMORIES_FILE)


def add_memory(content: str, category: str = "fact") -> dict:
    """Add a new memory. Returns the created memory dict."""
    if not content or not content.strip():
        raise ValueError("Memory content cannot be empty")

    if category not in VALID_CATEGORIES:
        category = "fact"

    memory = {
        "id": str(uuid.uuid4())[:8],
        "content": content.strip(),
        "category": category,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    memories = load_memories()

    # Avoid exact duplicates
    for m in memories:
        if m.get("content", "").lower() == memory["content"].lower():
            return m  # Already exists

    memories.append(memory)
    _save_memories(memories)
    return memory


def remove_memory(memory_id: str) -> bool:
    """Remove a memory by ID. Returns True if found and removed."""
    memories = load_memories()
    original_len = len(memories)
    memories = [m for m in memories if m.get("id") != memory_id]

    if len(memories) < original_len:
        _save_memories(memories)
        return True
    return False


def clear_memories() -> int:
    """Remove all memories. Returns count of removed memories."""
    memories = load_memories()
    count = len(memories)
    if count > 0:
        _save_memories([])
    return count


def search_memories(query: str) -> list[dict]:
    """Search memories by content (case-insensitive substring match)."""
    if not query:
        return load_memories()

    query_lower = query.lower()
    return [
        m for m in load_memories()
        if query_lower in m.get("content", "").lower()
        or query_lower in m.get("category", "").lower()
    ]
