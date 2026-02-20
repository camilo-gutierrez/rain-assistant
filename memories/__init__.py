"""Rain Memories — persistent user preferences and facts."""

from .storage import (
    load_memories,
    add_memory,
    remove_memory,
    clear_memories,
    search_memories,
    reindex_memories,
    embeddings_available,
)
from .meta_tool import (
    MANAGE_MEMORIES_DEFINITION,
    handle_manage_memories,
)

__all__ = [
    "load_memories",
    "add_memory",
    "remove_memory",
    "clear_memories",
    "search_memories",
    "reindex_memories",
    "embeddings_available",
    "MANAGE_MEMORIES_DEFINITION",
    "handle_manage_memories",
]
