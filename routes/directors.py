"""Director routes: CRUD, projects, task queue, inbox, and activity.

IMPORTANT: Static sub-paths (projects, templates, stats, tasks, inbox, activity)
MUST be defined BEFORE the {director_id} wildcard route, otherwise FastAPI will
match e.g. "tasks" as a director_id and return 404.
"""

import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from shared_state import verify_token, get_token, _get_user_id_from_request

from directors.storage import (
    add_director, list_directors, get_director, update_director,
    delete_director, enable_director, disable_director, mark_director_run,
    create_project, list_projects, get_project, update_project,
    delete_project, count_projects, MAX_PROJECTS_PER_USER,
)
from directors.task_queue import (
    list_tasks as list_dir_tasks, get_task as get_dir_task,
    cancel_task, get_task_stats,
)
from directors.inbox import (
    list_inbox, get_inbox_item, update_inbox_status, get_unread_count,
)
from directors.builtin import (
    DIRECTOR_TEMPLATES, TEAM_TEMPLATES,
    get_team_template, get_director_template,
)

directors_router = APIRouter(tags=["directors"])


def _auth(request: Request):
    """Verify token and return user_id or error response."""
    if not verify_token(get_token(request)):
        return None, JSONResponse({"error": "Unauthorized"}, status_code=401)
    return _get_user_id_from_request(request), None


def _compute_setup_status(director: dict) -> dict:
    """Add setup_status, missing_fields, and required_context to a director dict.

    Computed on read — never stored. If the director was created from a template
    that defines ``required_context``, we check which required fields are empty
    in ``context_window`` and flag them.
    """
    template_id = director.get("template_id", "")
    if not template_id:
        director["setup_status"] = "complete"
        director["missing_fields"] = []
        director["required_context"] = []
        return director

    template = get_director_template(template_id)
    if not template or "required_context" not in template:
        director["setup_status"] = "complete"
        director["missing_fields"] = []
        director["required_context"] = []
        return director

    context = director.get("context_window", {})
    if isinstance(context, str):
        try:
            import json as _json
            context = _json.loads(context)
        except (ValueError, TypeError):
            context = {}

    required_fields = template["required_context"]
    missing = []
    for field in required_fields:
        if field.get("required") and not context.get(field["key"]):
            missing.append(field["key"])

    director["setup_status"] = "needs_setup" if missing else "complete"
    director["missing_fields"] = missing
    director["required_context"] = required_fields
    return director


# ---------------------------------------------------------------------------
# Directors: list + create (no path params)
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors")
async def api_list_directors(request: Request, project_id: str = ""):
    uid, err = _auth(request)
    if err:
        return err
    directors = list_directors(
        user_id=uid,
        project_id=project_id or None,
    )
    directors = [_compute_setup_status(d) for d in directors]
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
        project_id=body.get("project_id", "default"),
        template_id=body.get("template_id", ""),
    )
    if director is None:
        return JSONResponse({"error": "Could not create director (duplicate ID or invalid cron)"}, status_code=400)
    return {"director": director}


# ---------------------------------------------------------------------------
# Projects (static sub-paths — MUST come BEFORE {director_id} wildcard)
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors/projects")
async def api_list_projects(request: Request):
    """List all projects for the authenticated user."""
    uid, err = _auth(request)
    if err:
        return err
    projects = list_projects(user_id=uid)
    return {"projects": projects}


@directors_router.post("/api/directors/projects")
async def api_create_project(request: Request):
    """Create a new project, optionally from a team template."""
    uid, err = _auth(request)
    if err:
        return err
    body = await request.json()

    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "'name' is required"}, status_code=400)

    # Enforce limit
    if count_projects(user_id=uid) >= MAX_PROJECTS_PER_USER:
        return JSONResponse(
            {"error": f"Maximum {MAX_PROJECTS_PER_USER} projects reached"},
            status_code=400,
        )

    project = create_project(
        name=name,
        user_id=uid,
        emoji=body.get("emoji", "📁"),
        description=body.get("description", ""),
        color=body.get("color", "#6C7086"),
        team_template=body.get("team_template"),
    )

    if project is None:
        return JSONResponse({"error": "Could not create project"}, status_code=400)

    # Auto-install directors from team template
    installed_directors = []
    team_template_id = body.get("team_template")
    if team_template_id:
        team = get_team_template(team_template_id)
        if team:
            for dir_id in team.get("directors", []):
                tmpl = get_director_template(dir_id)
                if tmpl:
                    director = add_director(
                        id=f"{project['id']}_{tmpl['id']}",
                        name=tmpl["name"],
                        role_prompt=tmpl["role_prompt"],
                        schedule=tmpl.get("schedule"),
                        description=tmpl.get("description", ""),
                        emoji=tmpl.get("emoji", "🤖"),
                        tools_allowed=tmpl.get("tools_allowed"),
                        plugins_allowed=tmpl.get("plugins_allowed"),
                        permission_level=tmpl.get("permission_level", "green"),
                        can_delegate=tmpl.get("can_delegate", False),
                        user_id=uid,
                        project_id=project["id"],
                        template_id=tmpl["id"],
                    )
                    if director:
                        installed_directors.append(director)

    return {"project": project, "installed_directors": installed_directors}


@directors_router.get("/api/directors/projects/{project_id}")
async def api_get_project(request: Request, project_id: str):
    uid, err = _auth(request)
    if err:
        return err
    project = get_project(project_id, user_id=uid)
    if not project:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"project": project}


@directors_router.patch("/api/directors/projects/{project_id}")
async def api_update_project(request: Request, project_id: str):
    uid, err = _auth(request)
    if err:
        return err
    body = await request.json()
    project = update_project(project_id, user_id=uid, **body)
    if project is None:
        return JSONResponse({"error": "Not found or invalid update"}, status_code=404)
    return {"project": project}


@directors_router.delete("/api/directors/projects/{project_id}")
async def api_delete_project(request: Request, project_id: str):
    uid, err = _auth(request)
    if err:
        return err
    if project_id == "default":
        return JSONResponse({"error": "Cannot delete the default project"}, status_code=400)
    if delete_project(project_id, user_id=uid):
        return {"deleted": True}
    return JSONResponse({"error": "Not found"}, status_code=404)


# ---------------------------------------------------------------------------
# Templates (static sub-paths)
# ---------------------------------------------------------------------------

@directors_router.get("/api/directors/templates")
async def api_list_templates(request: Request):
    uid, err = _auth(request)
    if err:
        return err
    standalone = [t for t in DIRECTOR_TEMPLATES if not t.get("team_only")]
    return {"templates": standalone}


@directors_router.get("/api/directors/team-templates")
async def api_list_team_templates(request: Request):
    uid, err = _auth(request)
    if err:
        return err
    enriched = []
    for team in TEAM_TEMPLATES:
        t = dict(team)
        t["director_details"] = [
            get_director_template(d_id)
            for d_id in team.get("directors", [])
            if get_director_template(d_id)
        ]
        enriched.append(t)
    return {"team_templates": enriched}


@directors_router.get("/api/directors/stats")
async def api_director_stats(request: Request, project_id: str = ""):
    uid, err = _auth(request)
    if err:
        return err
    stats = get_task_stats(user_id=uid, project_id=project_id or None)
    unread = get_unread_count(user_id=uid, project_id=project_id or None)
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
    project_id: str = "",
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
        project_id=project_id or None,
    )
    stats = get_task_stats(user_id=uid, project_id=project_id or None)
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
    project_id: str = "",
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
        project_id=project_id or None,
    )
    unread = get_unread_count(user_id=uid, project_id=project_id or None)
    return {"items": items, "unread_count": unread}


@directors_router.get("/api/directors/inbox/unread")
async def api_inbox_unread(request: Request, project_id: str = ""):
    uid, err = _auth(request)
    if err:
        return err
    count = get_unread_count(user_id=uid, project_id=project_id or None)
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
async def api_activity(request: Request, limit: int = 20, project_id: str = ""):
    uid, err = _auth(request)
    if err:
        return err

    _project_id = project_id or None

    # Combine recent director runs and inbox items into a timeline
    directors = list_directors(user_id=uid, project_id=_project_id)
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

    inbox_items = list_inbox(user_id=uid, limit=limit, project_id=_project_id)
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

    tasks = list_dir_tasks(user_id=uid, limit=limit, project_id=_project_id)
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
    director = _compute_setup_status(director)
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


@directors_router.post("/api/directors/projects/{project_id}/run")
async def api_run_project(request: Request, project_id: str):
    """Run all enabled directors in a project sequentially.

    Directors are executed one after another so that earlier directors
    can delegate tasks and produce inbox items that later ones consume.
    Execution happens in a background task; the endpoint returns immediately.
    """
    uid, err = _auth(request)
    if err:
        return err
    project = get_project(project_id, user_id=uid)
    if not project:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    directors = list_directors(user_id=uid, enabled_only=True, project_id=project_id)
    if not directors:
        return JSONResponse(
            {"error": "No enabled directors in this project"}, status_code=400,
        )

    async def _run_team():
        import shared_state as _ss
        from directors.executor import execute_director

        await _ss.notify_user(uid, {
            "type": "director_event",
            "event": "team_run_start",
            "project_id": project_id,
            "project_name": project.get("name", ""),
            "director_count": len(directors),
        })

        results = []
        try:
            for director in directors:
                did = director["id"]
                try:
                    result_text, error_text, cost = await asyncio.wait_for(
                        execute_director(
                            director, trigger="manual",
                            user_id=uid, project_id=project_id,
                        ),
                        timeout=300,
                    )
                    mark_director_run(did, result=result_text, error=error_text, cost=cost)
                    results.append({
                        "director_id": did, "success": not bool(error_text),
                    })
                    await _ss.notify_user(uid, {
                        "type": "director_event",
                        "event": "run_complete",
                        "director_id": did,
                        "director_name": director.get("name", ""),
                        "project_id": project_id,
                        "success": not bool(error_text),
                    })
                except asyncio.CancelledError:
                    raise
                except asyncio.TimeoutError:
                    mark_director_run(did, error="Execution timed out after 300s")
                    results.append({"director_id": did, "success": False})
                except Exception as e:
                    mark_director_run(did, error=str(e))
                    results.append({"director_id": did, "success": False})

            # Process any delegated tasks that were created during the run
            try:
                from directors.task_queue import get_ready_tasks, claim_task, complete_task, fail_task
                ready_tasks = get_ready_tasks(user_id=uid)
                for dtask in ready_tasks:
                    assignee_id = dtask.get("assignee_id")
                    if not assignee_id:
                        continue
                    assignee = get_director(assignee_id, user_id=uid)
                    if not assignee or not assignee.get("enabled"):
                        continue
                    claimed = claim_task(dtask["id"], assignee_id, uid)
                    if not claimed:
                        continue
                    try:
                        rt, et, c = await asyncio.wait_for(
                            execute_director(
                                assignee, trigger="task", task=dtask,
                                user_id=uid, project_id=project_id,
                            ),
                            timeout=300,
                        )
                        if et:
                            fail_task(dtask["id"], et, uid)
                        else:
                            complete_task(dtask["id"], {"result": rt, "cost": c}, uid)
                        await _ss.notify_user(uid, {
                            "type": "director_event",
                            "event": "task_complete",
                            "director_id": assignee_id,
                            "director_name": assignee.get("name", ""),
                            "project_id": project_id,
                            "task_id": dtask["id"],
                            "success": not bool(et),
                        })
                    except asyncio.CancelledError:
                        raise
                    except (asyncio.TimeoutError, Exception):
                        fail_task(dtask["id"], "Task execution failed", uid)
            except asyncio.CancelledError:
                raise
            except ImportError:
                pass

            await _ss.notify_user(uid, {
                "type": "director_event",
                "event": "team_run_complete",
                "project_id": project_id,
                "project_name": project.get("name", ""),
                "results": results,
            })

        except asyncio.CancelledError:
            # Team was force-stopped by user
            try:
                await _ss.notify_user(uid, {
                    "type": "director_event",
                    "event": "team_run_stopped",
                    "project_id": project_id,
                    "project_name": project.get("name", ""),
                    "results": results,
                })
            except Exception:
                pass
        finally:
            _ss.unregister_team_task(uid, project_id)

    import shared_state as _ss_reg
    task = asyncio.create_task(_run_team())
    _ss_reg.register_team_task(uid, project_id, task)

    return {
        "queued": True,
        "directors": [{"id": d["id"], "name": d["name"]} for d in directors],
        "message": f"Running {len(directors)} directors sequentially",
    }


@directors_router.post("/api/directors/projects/{project_id}/stop")
async def api_stop_project(request: Request, project_id: str):
    """Force stop a running team execution."""
    uid, err = _auth(request)
    if err:
        return err

    import shared_state as _ss
    if _ss.cancel_team_task(uid, project_id):
        return {"stopped": True}
    return JSONResponse(
        {"error": "No running team found for this project"},
        status_code=404,
    )
