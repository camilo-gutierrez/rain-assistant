"""Agent data routes: messages, conversation history, memories, alter egos, marketplace."""

import json
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import database
import shared_state
from shared_state import (
    MAX_CWD_LENGTH,
    WS_MAX_AGENT_ID_LENGTH,
    _secure_chmod,
    verify_token,
    get_token,
    _get_user_id_from_request,
)

from memories.storage import (
    load_memories, add_memory, remove_memory, clear_memories,
)
from alter_egos.storage import (
    load_all_egos, load_ego, save_ego, delete_ego,
    get_active_ego_id, set_active_ego_id,
)

agents_router = APIRouter(tags=["agents"])


# ---------------------------------------------------------------------------
# REST: Message persistence
# ---------------------------------------------------------------------------


@agents_router.get("/api/messages")
async def get_messages(request: Request, cwd: str = "", agent_id: str = "default"):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not cwd:
        return JSONResponse({"error": "cwd parameter is required"}, status_code=400)
    if len(cwd) > MAX_CWD_LENGTH or len(agent_id) > WS_MAX_AGENT_ID_LENGTH:
        return JSONResponse({"error": "Parameter too long"}, status_code=400)
    uid = _get_user_id_from_request(request)
    messages = database.get_messages(cwd, agent_id=agent_id, user_id=uid)
    return {"messages": messages}


@agents_router.delete("/api/messages")
async def delete_messages(request: Request, cwd: str = "", agent_id: str = ""):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not cwd:
        return JSONResponse({"error": "cwd parameter is required"}, status_code=400)
    if len(cwd) > MAX_CWD_LENGTH or len(agent_id) > WS_MAX_AGENT_ID_LENGTH:
        return JSONResponse({"error": "Parameter too long"}, status_code=400)
    uid = _get_user_id_from_request(request)
    count = database.clear_messages(cwd, agent_id=agent_id or None, user_id=uid)
    return {"deleted": count}


@agents_router.get("/api/metrics")
async def get_metrics(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    metrics = database.get_metrics_data()
    return metrics


# ---------------------------------------------------------------------------
# Conversation History (JSON file-based, max 5)
# ---------------------------------------------------------------------------


@agents_router.get("/api/history")
async def list_conversations(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    shared_state.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _secure_chmod(shared_state.HISTORY_DIR, 0o700)
    conversations = []
    for f in sorted(shared_state.HISTORY_DIR.glob(shared_state.HISTORY_GLOB), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            conversations.append({
                "id": data["id"],
                "createdAt": data["createdAt"],
                "updatedAt": data["updatedAt"],
                "label": data.get("label", ""),
                "cwd": data.get("cwd", ""),
                "messageCount": data.get("messageCount", 0),
                "preview": data.get("preview", ""),
                "totalCost": data.get("totalCost", 0),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return {"conversations": conversations}


@agents_router.post("/api/history")
async def save_conversation(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    shared_state.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _secure_chmod(shared_state.HISTORY_DIR, 0o700)
    # Enforce max request body size (512 KB)
    raw_body = await request.body()
    if len(raw_body) > 512 * 1024:
        return JSONResponse({"error": "Request body too large"}, status_code=413)

    try:
        body = json.loads(raw_body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    conv_id = str(body.get("id", f"conv_{int(time.time() * 1000)}"))[:64]
    body["id"] = conv_id

    # Find existing file for this id, or create new filename
    target = None
    for f in shared_state.HISTORY_DIR.glob(shared_state.HISTORY_GLOB):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == conv_id:
                target = f
                break
        except (json.JSONDecodeError, OSError):
            continue

    if not target:
        safe_agent = str(body.get("agentId", "default")).replace("/", "_").replace("\\", "_")[:64]
        target = shared_state.HISTORY_DIR / f"{int(time.time() * 1000)}_{safe_agent}.json"

    target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    _secure_chmod(target, 0o600)

    # Enforce max conversations -- delete oldest beyond limit
    deleted = []
    files = sorted(shared_state.HISTORY_DIR.glob(shared_state.HISTORY_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[shared_state.MAX_CONVERSATIONS:]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            deleted.append(data.get("id", f.stem))
        except Exception:
            deleted.append(f.stem)
        f.unlink()

    return {"saved": True, "id": conv_id, "deleted": deleted}


@agents_router.get("/api/history/{conversation_id}")
async def load_conversation(request: Request, conversation_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    shared_state.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _secure_chmod(shared_state.HISTORY_DIR, 0o700)
    for f in shared_state.HISTORY_DIR.glob(shared_state.HISTORY_GLOB):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == conversation_id:
                return data
        except (json.JSONDecodeError, OSError):
            continue
    return JSONResponse({"error": "Not found"}, status_code=404)


@agents_router.delete("/api/history/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    shared_state.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _secure_chmod(shared_state.HISTORY_DIR, 0o700)
    for f in shared_state.HISTORY_DIR.glob(shared_state.HISTORY_GLOB):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == conversation_id:
                f.unlink()
                return {"deleted": True}
        except (json.JSONDecodeError, OSError):
            continue
    return JSONResponse({"error": "Not found"}, status_code=404)


# ---------------------------------------------------------------------------
# REST API: Memories
# ---------------------------------------------------------------------------


@agents_router.get("/api/memories")
async def api_get_memories(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    uid = _get_user_id_from_request(request)
    return {"memories": load_memories(user_id=uid)}


@agents_router.post("/api/memories")
async def api_add_memory(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    content = body.get("content", "").strip()
    category = body.get("category", "fact")
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)
    uid = _get_user_id_from_request(request)
    memory = add_memory(content, category, user_id=uid)
    return {"memory": memory}


@agents_router.delete("/api/memories/{memory_id}")
async def api_delete_memory(request: Request, memory_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not memory_id or len(memory_id) > 128 or not all(c.isalnum() or c in "-_" for c in memory_id):
        return JSONResponse({"error": "Invalid memory ID"}, status_code=400)
    uid = _get_user_id_from_request(request)
    if remove_memory(memory_id, user_id=uid):
        return {"deleted": True}
    return JSONResponse({"error": "Not found"}, status_code=404)


@agents_router.delete("/api/memories")
async def api_clear_memories(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    uid = _get_user_id_from_request(request)
    count = clear_memories(user_id=uid)
    return {"cleared": count}


# ---------------------------------------------------------------------------
# REST API: Alter Egos
# ---------------------------------------------------------------------------


@agents_router.get("/api/alter-egos")
async def api_get_alter_egos(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    uid = _get_user_id_from_request(request)
    return {"egos": load_all_egos(user_id=uid), "active_ego_id": get_active_ego_id(user_id=uid)}


@agents_router.post("/api/alter-egos")
async def api_save_alter_ego(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    uid = _get_user_id_from_request(request)
    body = await request.json()
    try:
        path = save_ego(body, user_id=uid)
        return {"saved": True, "path": str(path)}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@agents_router.delete("/api/alter-egos/{ego_id}")
async def api_delete_alter_ego(request: Request, ego_id: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    uid = _get_user_id_from_request(request)
    try:
        if delete_ego(ego_id, user_id=uid):
            return {"deleted": True}
        return JSONResponse({"error": "Not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ---------------------------------------------------------------------------
# REST API: Skills Marketplace
# ---------------------------------------------------------------------------

from marketplace import MarketplaceRegistry

_marketplace: MarketplaceRegistry | None = None


def _get_marketplace() -> MarketplaceRegistry:
    global _marketplace
    if _marketplace is None:
        _marketplace = MarketplaceRegistry()
    return _marketplace


@agents_router.get("/api/marketplace/skills")
async def api_marketplace_search(request: Request, q: str = "", category: str = "",
                                  tag: str = "", page: int = 1):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    return mp.search_skills(query=q, category=category, tag=tag, page=page)


@agents_router.get("/api/marketplace/skills/{skill_name}")
async def api_marketplace_skill_info(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    info = mp.get_skill_info(skill_name)
    if not info:
        return JSONResponse({"error": "Skill not found"}, status_code=404)
    installed_version = mp.get_installed_version(skill_name)
    return {"skill": info.__dict__, "installed_version": installed_version}


@agents_router.get("/api/marketplace/categories")
async def api_marketplace_categories(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    return {"categories": [c.__dict__ for c in mp.get_categories()]}


@agents_router.post("/api/marketplace/install/{skill_name}")
async def api_marketplace_install(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    result = await mp.install_skill(skill_name)
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


@agents_router.delete("/api/marketplace/install/{skill_name}")
async def api_marketplace_uninstall(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    result = await mp.uninstall_skill(skill_name)
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


@agents_router.get("/api/marketplace/installed")
async def api_marketplace_installed(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    return {"skills": [s.__dict__ for s in mp.list_installed()]}


@agents_router.get("/api/marketplace/updates")
async def api_marketplace_check_updates(request: Request):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    return {"updates": mp.check_updates()}


@agents_router.post("/api/marketplace/update/{skill_name}")
async def api_marketplace_update(request: Request, skill_name: str):
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    mp = _get_marketplace()
    await mp.refresh_index()
    result = await mp.update_skill(skill_name)
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result
