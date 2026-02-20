"""Storage layer for Rain Memories — JSON-based persistent storage with optional vector embeddings."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".rain-assistant"
MEMORIES_FILE = CONFIG_DIR / "memories.json"

VALID_CATEGORIES = {"preference", "fact", "pattern", "project"}


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
# JSON persistence (unchanged from original)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def add_memory(content: str, category: str = "fact") -> dict:
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

    memories = load_memories()

    # Avoid exact duplicates
    for m in memories:
        if m.get("content", "").lower() == memory["content"].lower():
            return m  # Already exists

    memories.append(memory)
    _save_memories(memories)

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
                )
        except Exception as e:
            logger.warning("Failed to store embedding for memory %s: %s", memory["id"], e)

    return memory


def remove_memory(memory_id: str) -> bool:
    """Remove a memory by ID. Returns True if found and removed."""
    memories = load_memories()
    original_len = len(memories)
    memories = [m for m in memories if m.get("id") != memory_id]

    if len(memories) < original_len:
        _save_memories(memories)

        # Also remove from embeddings DB
        if embeddings_available():
            try:
                from . import embeddings as _emb
                _emb.remove_embedding(memory_id)
            except Exception as e:
                logger.warning("Failed to remove embedding for memory %s: %s", memory_id, e)

        return True
    return False


def clear_memories() -> int:
    """Remove all memories. Returns count of removed memories."""
    memories = load_memories()
    count = len(memories)
    if count > 0:
        _save_memories([])

        # Also clear embeddings DB
        if embeddings_available():
            try:
                from . import embeddings as _emb
                _emb.clear_embeddings()
            except Exception as e:
                logger.warning("Failed to clear embeddings: %s", e)

    return count


# ---------------------------------------------------------------------------
# Search (semantic with fallback to substring)
# ---------------------------------------------------------------------------

def search_memories(query: str, top_k: int = 10) -> list[dict]:
    """Search memories by relevance.

    If embeddings are available, performs semantic search using cosine similarity.
    Otherwise, falls back to case-insensitive substring matching.

    Args:
        query: Search query string.
        top_k: Maximum number of results for semantic search.

    Returns:
        List of matching memory dicts. Semantic results include a '_score' key.
    """
    if not query:
        return load_memories()

    memories = load_memories()

    # Try semantic search first
    if embeddings_available():
        try:
            from . import embeddings as _emb
            results = _emb.semantic_search(query, memories, top_k=top_k)
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

def reindex_memories() -> dict:
    """Rebuild embeddings for all existing memories.

    Useful after installing sentence-transformers for the first time, or
    if the embeddings database gets corrupted/deleted.

    Returns:
        Dict with 'total', 'indexed', and 'errors' counts.
    """
    memories = load_memories()
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
