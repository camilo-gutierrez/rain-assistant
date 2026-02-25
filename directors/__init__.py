"""Rain Autonomous Directors — persistent AI agents that run on schedules."""

from .storage import (
    add_director,
    list_directors,
    get_director,
    update_director,
    delete_director,
    enable_director,
    disable_director,
    get_pending_directors,
    mark_director_run,
    update_context,
    migrate_directors,
)
from .meta_tool import (
    MANAGE_DIRECTORS_DEFINITION,
    handle_manage_directors,
)
from .task_queue import (
    create_task,
    list_tasks,
    get_task,
    claim_task,
    complete_task,
    fail_task,
    cancel_task,
    get_ready_tasks,
    get_task_stats,
)
from .inbox import (
    add_inbox_item,
    list_inbox,
    get_inbox_item,
    update_inbox_status,
    get_unread_count,
    archive_old_items,
)

__all__ = [
    # Storage
    "add_director",
    "list_directors",
    "get_director",
    "update_director",
    "delete_director",
    "enable_director",
    "disable_director",
    "get_pending_directors",
    "mark_director_run",
    "update_context",
    "migrate_directors",
    # Meta-tool
    "MANAGE_DIRECTORS_DEFINITION",
    "handle_manage_directors",
    # Task queue
    "create_task",
    "list_tasks",
    "get_task",
    "claim_task",
    "complete_task",
    "fail_task",
    "cancel_task",
    "get_ready_tasks",
    "get_task_stats",
    # Inbox
    "add_inbox_item",
    "list_inbox",
    "get_inbox_item",
    "update_inbox_status",
    "get_unread_count",
    "archive_old_items",
]
