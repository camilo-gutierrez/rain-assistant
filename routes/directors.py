"""Director routes: CRUD, task queue, inbox, and activity.

IMPORTANT: Static sub-paths (templates, stats, tasks, inbox, activity) MUST be
defined BEFORE the {director_id} wildcard route, otherwise FastAPI will match
e.g. "tasks" as a director_id and return 404.
"""

import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from shared_state import verify_token, get_token, _get_user_id_from_request

from directors.storage import (
    add_director, list_directors, get_director, update_director,
    delete_director, enable_director, disable_director, mark_director_run,
)
from directors.task_queue import (
    list_tasks as list_dir_tasks, get_task as get_dir_task,
    cancel_task, get_task_stats,
)
from directors.inbox import (
    list_inbox, get_inbox_item, update_inbox_status, get_unread_count,
)
from directors.builtin import DIRECTOR_TEMPLATES

directors_router = APIRouter(tags=["directors"])


def _auth(request: Request):
    """Verify token and return user_id or error response."""
    if not verify_token(get_token(request)):
        return None, JSONResponse({"error": "Unauthorized"}, status_code=401)
    return _get_user_id_from_request(request), None


# ---------------------------------------------------------------------------
# Directors: list + create (no path params)
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors")
async def api_list_directors(request: Request):
    uid, err = _auth(request)
    if err:
        return err
    directors = list_directors(user_id=uid)
    return {"directors": directors}


@directors_router.post("/api/directors")
async def api_create_director(request: Request):
    uid, err = _auth(request)
    if err:
        return err
    body = await request.json()

    required = ("id", "name", "role_prompt")
    for field in required:
        if not body.get(field):
            return JSONResponse({"error": f"'{field}' is required"}, status_code=400)

    director = add_director(
        id=body["id"],
        name=body["name"],
        role_prompt=body["role_prompt"],
        schedule=body.get("schedule"),
        description=body.get("description", ""),
        emoji=body.get("emoji", "🤖"),
        tools_allowed=body.get("tools_allowed"),
        plugins_allowed=body.get("plugins_allowed"),
        permission_level=body.get("permission_level", "green"),
        can_delegate=body.get("can_delegate", False),
        user_id=uid,
    )
    if director is None:
        return JSONResponse({"error": "Could not create director (duplicate ID or invalid cron)"}, status_code=400)
    return {"director": director}


# ---------------------------------------------------------------------------
# Static sub-paths — MUST come BEFORE {director_id} wildcard
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors/templates")
async def api_list_templates(request: Request):
    uid, err = _auth(request)
    if err:
        return err
    return {"templates": DIRECTOR_TEMPLATES}


@directors_router.get("/api/directors/stats")
async def api_director_stats(request: Request):
    uid, err = _auth(request)
    if err:
        return err
    stats = get_task_stats(user_id=uid)
    unread = get_unread_count(user_id=uid)
    return {"task_stats": stats, "inbox_unread": unread}


# ---------------------------------------------------------------------------
# Task Queue (static sub-paths)
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors/tasks")
async def api_list_tasks(
    request: Request,
    status: str = "",
    assignee_id: str = "",
    creator_id: str = "",
    limit: int = 50,
):
    uid, err = _auth(request)
    if err:
        return err
    tasks = list_dir_tasks(
        user_id=uid,
        status=status or None,
        assignee_id=assignee_id or None,
        creator_id=creator_id or None,
        limit=min(limit, 100),
    )
    stats = get_task_stats(user_id=uid)
    return {"tasks": tasks, "stats": stats}


@directors_router.get("/api/directors/tasks/{task_id}")
async def api_get_task(request: Request, task_id: str):
    uid, err = _auth(request)
    if err:
        return err
    task = get_dir_task(task_id, user_id=uid)
    if not task:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"task": task}


@directors_router.post("/api/directors/tasks/{task_id}/cancel")
async def api_cancel_task(request: Request, task_id: str):
    uid, err = _auth(request)
    if err:
        return err
    if cancel_task(task_id, user_id=uid):
        return {"cancelled": True}
    return JSONResponse({"error": "Not found or not cancellable"}, status_code=404)


# ---------------------------------------------------------------------------
# Inbox (static sub-paths)
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors/inbox")
async def api_list_inbox(
    request: Request,
    status: str = "",
    director_id: str = "",
    content_type: str = "",
    limit: int = 50,
    offset: int = 0,
):
    uid, err = _auth(request)
    if err:
        return err
    items = list_inbox(
        user_id=uid,
        status=status or None,
        director_id=director_id or None,
        content_type=content_type or None,
        limit=min(limit, 100),
        offset=offset,
    )
    unread = get_unread_count(user_id=uid)
    return {"items": items, "unread_count": unread}


@directors_router.get("/api/directors/inbox/unread")
async def api_inbox_unread(request: Request):
    uid, err = _auth(request)
    if err:
        return err
    count = get_unread_count(user_id=uid)
    return {"count": count}


@directors_router.get("/api/directors/inbox/{item_id}")
async def api_get_inbox_item(request: Request, item_id: str):
    uid, err = _auth(request)
    if err:
        return err
    item = get_inbox_item(item_id, user_id=uid)
    if not item:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"item": item}


@directors_router.patch("/api/directors/inbox/{item_id}")
async def api_update_inbox_item(request: Request, item_id: str):
    uid, err = _auth(request)
    if err:
        return err
    body = await request.json()
    status = body.get("status")
    comment = body.get("user_comment")

    if not status:
        return JSONResponse({"error": "'status' is required"}, status_code=400)

    item = update_inbox_status(item_id, status=status, user_comment=comment, user_id=uid)
    if item is None:
        return JSONResponse({"error": "Not found or invalid status"}, status_code=404)
    return {"item": item}


# ---------------------------------------------------------------------------
# Activity timeline (static sub-path)
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors/activity")
async def api_activity(request: Request, limit: int = 20):
    uid, err = _auth(request)
    if err:
        return err

    # Combine recent director runs and inbox items into a timeline
    directors = list_directors(user_id=uid)
    recent_runs = []
    for d in directors:
        if d.get("last_run"):
            recent_runs.append({
                "type": "director_run",
                "director_id": d["id"],
                "director_name": d["name"],
                "emoji": d.get("emoji", "🤖"),
                "timestamp": d["last_run"],
                "success": not bool(d.get("last_error")),
                "preview": (d.get("last_result") or d.get("last_error") or "")[:200],
            })

    inbox_items = list_inbox(user_id=uid, limit=limit)
    recent_inbox = [
        {
            "type": "inbox_item",
            "director_id": item["director_id"],
            "director_name": item["director_name"],
            "title": item["title"],
            "content_type": item["content_type"],
            "status": item["status"],
            "timestamp": item["created_at"],
        }
        for item in inbox_items
    ]

    tasks = list_dir_tasks(user_id=uid, limit=limit)
    recent_tasks = [
        {
            "type": "task",
            "task_id": t["id"],
            "title": t["title"],
            "creator_id": t["creator_id"],
            "assignee_id": t.get("assignee_id"),
            "status": t["status"],
            "timestamp": t["created_at"],
        }
        for t in tasks
    ]

    # Merge and sort by timestamp
    activity = recent_runs + recent_inbox + recent_tasks
    activity.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    return {"activity": activity[:limit]}


# ---------------------------------------------------------------------------
# Directors: wildcard {director_id} routes — MUST be LAST
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors/{director_id}")
async def api_get_director(request: Request, director_id: str):
    uid, err = _auth(request)
    if err:
        return err
    director = get_director(director_id, user_id=uid)
    if not director:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"director": director}


@directors_router.patch("/api/directors/{director_id}")
async def api_update_director(request: Request, director_id: str):
    uid, err = _auth(request)
    if err:
        return err
    body = await request.json()

    director = update_director(director_id, user_id=uid, **body)
    if director is None:
        return JSONResponse({"error": "Not found or invalid update"}, status_code=404)
    return {"director": director}


@directors_router.delete("/api/directors/{director_id}")
async def api_delete_director(request: Request, director_id: str):
    uid, err = _auth(request)
    if err:
        return err
    if delete_director(director_id, user_id=uid):
        return {"deleted": True}
    return JSONResponse({"error": "Not found"}, status_code=404)


@directors_router.post("/api/directors/{director_id}/enable")
async def api_enable_director(request: Request, director_id: str):
    uid, err = _auth(request)
    if err:
        return err
    director = enable_director(director_id, user_id=uid)
    if director is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"director": director}


@directors_router.post("/api/directors/{director_id}/disable")
async def api_disable_director(request: Request, director_id: str):
    uid, err = _auth(request)
    if err:
        return err
    director = disable_director(director_id, user_id=uid)
    if director is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"director": director}


@directors_router.post("/api/directors/{director_id}/run")
async def api_run_director(request: Request, director_id: str):
    uid, err = _auth(request)
    if err:
        return err
    director = get_director(director_id, user_id=uid)
    if not director:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if not director.get("enabled"):
        return JSONResponse({"error": "Director is disabled"}, status_code=400)

    # Set next_run to now for scheduler pickup
    from directors.storage import _get_db
    now = time.time()
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE directors SET next_run = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (now, now, director_id, uid),
        )
        conn.commit()
    finally:
        conn.close()

    return {"queued": True, "message": "Director will run within 30 seconds"}
