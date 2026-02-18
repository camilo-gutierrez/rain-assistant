"""Rain Alter Egos — switchable personalities with different system prompts."""

from .storage import (
    load_all_egos,
    load_ego,
    save_ego,
    delete_ego,
    get_active_ego_id,
    set_active_ego_id,
    ensure_builtin_egos,
)
from .meta_tool import (
    MANAGE_ALTER_EGOS_DEFINITION,
    handle_manage_alter_egos,
)

__all__ = [
    "load_all_egos",
    "load_ego",
    "save_ego",
    "delete_ego",
    "get_active_ego_id",
    "set_active_ego_id",
    "ensure_builtin_egos",
    "MANAGE_ALTER_EGOS_DEFINITION",
    "handle_manage_alter_egos",
]
