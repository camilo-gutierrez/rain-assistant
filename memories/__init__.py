"""Rain Memories — persistent user preferences and facts."""

from .storage import (
    load_memories,
    add_memory,
    remove_memory,
    clear_memories,
    search_memories,
    reindex_memories,
    embeddings_available,
    migrate_shared_to_user_isolated,
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
    "migrate_shared_to_user_isolated",
    "MANAGE_MEMORIES_DEFINITION",
    "handle_manage_memories",
]
