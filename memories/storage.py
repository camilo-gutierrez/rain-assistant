"""Storage layer for Rain Memories — JSON-based persistent storage with optional vector embeddings.

Supports per-user isolation: each user_id gets its own memories.json file
under ~/.rain-assistant/users/{user_id}/memories.json.
The default user_id="default" maintains backward compatibility.
"""

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from database import encrypt_field, decrypt_field
from utils.sanitize import sanitize_user_id, secure_chmod

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".rain-assistant"
MEMORIES_FILE = CONFIG_DIR / "memories.json"  # Legacy path (kept for backward compat in tests)

VALID_CATEGORIES = {"preference", "fact", "pattern", "project"}


# ---------------------------------------------------------------------------
# Per-user path helper
# ---------------------------------------------------------------------------

def _user_memories_file(user_id: str = "default") -> Path:
    """Get the memories file path for a specific user."""
    user_id = sanitize_user_id(user_id)
    user_dir = CONFIG_DIR / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    secure_chmod(user_dir, 0o700)
    return user_dir / "memories.json"


# ---------------------------------------------------------------------------
# Embeddings availability (lazy-checked)
# ---------------------------------------------------------------------------

_embeddings_checked = False
_embeddings_available = False


def _check_embeddings() -> bool:
    """Check if the embeddings module is usable (sentence-transformers installed)."""
    global _embeddings_checked, _embeddings_available
    if _embeddings_checked:
        return _embeddings_available
    _embeddings_checked = True
    try:
        from . import embeddings as _emb
        _embeddings_available = _emb.is_available()
    except Exception:
        _embeddings_available = False
    return _embeddings_available


def embeddings_available() -> bool:
    """Return True if semantic embeddings are available for use."""
    return _check_embeddings()


EMBEDDINGS_AVAILABLE: bool = False  # Updated at first check; use embeddings_available() for live check


# ---------------------------------------------------------------------------
# JSON persistence — per-user isolated
# ---------------------------------------------------------------------------

def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_memories(user_id: str = "default") -> list[dict]:
    """Load all memories from disk for a specific user."""
    mem_file = _user_memories_file(user_id)
    if not mem_file.exists():
        return []
    try:
        with open(mem_file, "r", encoding="utf-8") as f:
            raw = f.read()
        decrypted = decrypt_field(raw)  # handles backward compat (returns raw if not encrypted)
        data = json.loads(decrypted)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_memories(memories: list[dict], user_id: str = "default") -> None:
    """Write memories list to disk atomically for a specific user."""
    mem_file = _user_memories_file(user_id)
    mem_file.parent.mkdir(parents=True, exist_ok=True)
    secure_chmod(mem_file.parent, 0o700)
    tmp = mem_file.with_suffix(".tmp")
    json_str = json.dumps(memories, indent=2, ensure_ascii=False)
    encrypted = encrypt_field(json_str)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(encrypted)
    tmp.replace(mem_file)
    secure_chmod(mem_file, 0o600)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def add_memory(content: str, category: str = "fact", user_id: str = "default") -> dict:
    """Add a new memory. Returns the created memory dict.

    If embeddings are available, the embedding is computed and stored in SQLite
    alongside the JSON entry.
    """
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

    memories = load_memories(user_id)

    # Avoid exact duplicates
    for m in memories:
        if m.get("content", "").lower() == memory["content"].lower():
            return m  # Already exists

    memories.append(memory)
    _save_memories(memories, user_id)

    # Store embedding if available
    if embeddings_available():
        try:
            from . import embeddings as _emb
            embedding = _emb.get_embedding(memory["content"])
            if embedding is not None:
                _emb.store_embedding(
                    memory["id"],
                    memory["content"],
                    memory["category"],
                    memory["created_at"],
                    embedding,
                    user_id=user_id,
                )
        except Exception as e:
            logger.warning("Failed to store embedding for memory %s: %s", memory["id"], e)

    return memory


def remove_memory(memory_id: str, user_id: str = "default") -> bool:
    """Remove a memory by ID. Returns True if found and removed."""
    memories = load_memories(user_id)
    original_len = len(memories)
    memories = [m for m in memories if m.get("id") != memory_id]

    if len(memories) < original_len:
        _save_memories(memories, user_id)

        # Also remove from embeddings DB
        if embeddings_available():
            try:
                from . import embeddings as _emb
                _emb.remove_embedding(memory_id, user_id=user_id)
            except Exception as e:
                logger.warning("Failed to remove embedding for memory %s: %s", memory_id, e)

        return True
    return False


def clear_memories(user_id: str = "default") -> int:
    """Remove all memories. Returns count of removed memories."""
    memories = load_memories(user_id)
    count = len(memories)
    if count > 0:
        _save_memories([], user_id)

        # Also clear embeddings DB
        if embeddings_available():
            try:
                from . import embeddings as _emb
                _emb.clear_embeddings(user_id=user_id)
            except Exception as e:
                logger.warning("Failed to clear embeddings: %s", e)

    return count


# ---------------------------------------------------------------------------
# Search (semantic with fallback to substring)
# ---------------------------------------------------------------------------

def search_memories(query: str, user_id: str = "default", top_k: int = 10) -> list[dict]:
    """Search memories by relevance.

    If embeddings are available, performs semantic search using cosine similarity.
    Otherwise, falls back to case-insensitive substring matching.

    Args:
        query: Search query string.
        user_id: User whose memories to search.
        top_k: Maximum number of results for semantic search.

    Returns:
        List of matching memory dicts. Semantic results include a '_score' key.
    """
    if not query:
        return load_memories(user_id)

    memories = load_memories(user_id)

    # Try semantic search first
    if embeddings_available():
        try:
            from . import embeddings as _emb
            results = _emb.semantic_search(query, memories, top_k=top_k, user_id=user_id)
            if results:
                return results
            # If semantic search returns nothing (e.g., no embeddings stored yet),
            # fall through to substring search
        except Exception as e:
            logger.warning("Semantic search failed, falling back to substring: %s", e)

    # Fallback: substring search
    query_lower = query.lower()
    return [
        m for m in memories
        if query_lower in m.get("content", "").lower()
        or query_lower in m.get("category", "").lower()
    ]


# ---------------------------------------------------------------------------
# Reindex: rebuild embeddings for all existing memories
# ---------------------------------------------------------------------------

def reindex_memories(user_id: str = "default") -> dict:
    """Rebuild embeddings for all existing memories.

    Useful after installing sentence-transformers for the first time, or
    if the embeddings database gets corrupted/deleted.

    Returns:
        Dict with 'total', 'indexed', and 'errors' counts.
    """
    memories = load_memories(user_id)
    result = {"total": len(memories), "indexed": 0, "errors": 0}

    if not memories:
        return result

    if not embeddings_available():
        logger.error(
            "Cannot reindex: sentence-transformers is not available. "
            "Install with: pip install rain-assistant[memory]"
        )
        result["errors"] = len(memories)
        return result

    from . import embeddings as _emb

    for mem in memories:
        try:
            embedding = _emb.get_embedding(mem.get("content", ""))
            if embedding is not None:
                _emb.store_embedding(
                    mem.get("id", ""),
                    mem.get("content", ""),
                    mem.get("category", "fact"),
                    mem.get("created_at", ""),
                    embedding,
                    user_id=user_id,
                )
                result["indexed"] += 1
            else:
                result["errors"] += 1
        except Exception as e:
            logger.warning("Failed to index memory %s: %s", mem.get("id", "?"), e)
            result["errors"] += 1

    logger.info(
        "Reindex complete: %d/%d indexed, %d errors",
        result["indexed"], result["total"], result["errors"],
    )
    return result


# ---------------------------------------------------------------------------
# Migration: legacy shared memories.json -> per-user isolation
# ---------------------------------------------------------------------------

def migrate_shared_to_user_isolated() -> dict:
    """Move legacy shared memories.json to user-isolated structure.

    Copies ~/.rain-assistant/memories.json -> ~/.rain-assistant/users/default/memories.json
    if the legacy file exists and the destination does not.

    Returns:
        Dict with 'status' key: 'migrated', 'skipped', or 'error'.
    """
    legacy_file = CONFIG_DIR / "memories.json"
    if not legacy_file.exists():
        return {"status": "skipped"}

    try:
        user_dir = CONFIG_DIR / "users" / "default"
        user_dir.mkdir(parents=True, exist_ok=True)
        secure_chmod(user_dir, 0o700)
        new_file = user_dir / "memories.json"

        if not new_file.exists():
            shutil.copy2(str(legacy_file), str(new_file))
            secure_chmod(new_file, 0o600)

        return {"status": "migrated"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
