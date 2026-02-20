"""manage_subagents meta-tool — spawn and manage sub-agents via chat."""

import json

from .manager import SubAgentManager

MANAGE_SUBAGENTS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_subagents",
        "description": (
            "Spawn and manage sub-agents to delegate tasks in parallel. "
            "Sub-agents are independent AI agents that execute a specific task "
            "and return results. Use 'spawn' to create a blocking sub-agent "
            "(waits for result), 'spawn_async' to create a non-blocking one, "
            "'list' to see active sub-agents, 'status' to check one, "
            "'get_result' to retrieve a completed result, 'message' to send "
            "a follow-up, and 'cancel' to stop a running sub-agent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "spawn",
                        "spawn_async",
                        "message",
                        "status",
                        "cancel",
                        "list",
                        "get_result",
                    ],
                    "description": "Action to perform",
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Short name for the sub-agent (lowercase, hyphens, underscores). "
                        "Required for spawn/spawn_async. Example: 'researcher', 'code-reviewer'"
                    ),
                },
                "task": {
                    "type": "string",
                    "description": (
                        "The prompt/task to delegate to the sub-agent. "
                        "Required for spawn/spawn_async."
                    ),
                },
                "agent_id": {
                    "type": "string",
                    "description": (
                        "Full sub-agent ID (e.g., 'default::researcher'). "
                        "Required for message/status/cancel/get_result."
                    ),
                },
                "text": {
                    "type": "string",
                    "description": "Follow-up message text. Required for 'message' action.",
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        "Max seconds to wait for completion (default: 600). "
                        "Only for spawn/spawn_async."
                    ),
                },
            },
            "required": ["action"],
        },
    },
}


def create_subagent_handler(
    manager: SubAgentManager, caller_agent_id: str
):
    """Factory: return handler bound to the caller's agent_id.

    This handler is injected into the ToolExecutor for a specific agent,
    so all spawn operations are scoped to that parent.
    """

    async def handle_manage_subagents(args: dict, cwd: str) -> dict:
        action = args.get("action", "")

        try:
            if action == "spawn":
                name = args.get("name", "")
                task = args.get("task", "")
                timeout = args.get("timeout", 600)
                if not name or not task:
                    return {
                        "content": "Error: 'name' and 'task' are required for spawn.",
                        "is_error": True,
                    }
                result = await manager.spawn(
                    caller_agent_id,
                    name,
                    task,
                    blocking=True,
                    timeout=timeout,
                )
                return {"content": result, "is_error": False}

            elif action == "spawn_async":
                name = args.get("name", "")
                task = args.get("task", "")
                timeout = args.get("timeout", 600)
                if not name or not task:
                    return {
                        "content": "Error: 'name' and 'task' are required for spawn_async.",
                        "is_error": True,
                    }
                sub_id = await manager.spawn(
                    caller_agent_id,
                    name,
                    task,
                    blocking=False,
                    timeout=timeout,
                )
                return {
                    "content": f"Sub-agent spawned asynchronously. ID: {sub_id}\n"
                    f"Use get_result with this ID to check when it's done.",
                    "is_error": False,
                }

            elif action == "message":
                agent_id = args.get("agent_id", "")
                text = args.get("text", "")
                if not agent_id or not text:
                    return {
                        "content": "Error: 'agent_id' and 'text' are required for message.",
                        "is_error": True,
                    }
                result = await manager.send_message(agent_id, text)
                return {"content": result, "is_error": False}

            elif action == "status":
                agent_id = args.get("agent_id", "")
                if not agent_id:
                    return {
                        "content": "Error: 'agent_id' is required for status.",
                        "is_error": True,
                    }
                info = manager.get_status(agent_id)
                if not info:
                    return {
                        "content": f"Sub-agent '{agent_id}' not found.",
                        "is_error": True,
                    }
                return {
                    "content": json.dumps(info, indent=2, default=str),
                    "is_error": False,
                }

            elif action == "cancel":
                agent_id = args.get("agent_id", "")
                if not agent_id:
                    return {
                        "content": "Error: 'agent_id' is required for cancel.",
                        "is_error": True,
                    }
                result = await manager.cancel(agent_id)
                return {"content": result, "is_error": False}

            elif action == "list":
                subagents = manager.list_subagents(caller_agent_id)
                if not subagents:
                    return {
                        "content": "No sub-agents found for this agent.",
                        "is_error": False,
                    }
                lines = []
                for sa in subagents:
                    status_icon = {
                        "running": "[*]",
                        "completed": "[+]",
                        "error": "[!]",
                        "cancelled": "[-]",
                        "pending": "[ ]",
                    }.get(sa["status"], "[?]")
                    lines.append(
                        f"{status_icon} {sa['short_name']} ({sa['status']}) — {sa['task']}"
                    )
                return {"content": "\n".join(lines), "is_error": False}

            elif action == "get_result":
                agent_id = args.get("agent_id", "")
                if not agent_id:
                    return {
                        "content": "Error: 'agent_id' is required for get_result.",
                        "is_error": True,
                    }
                info = manager.get_status(agent_id)
                if not info:
                    return {
                        "content": f"Sub-agent '{agent_id}' not found.",
                        "is_error": True,
                    }
                if info["status"] == "running":
                    return {
                        "content": f"Sub-agent '{agent_id}' is still running. Try again later.",
                        "is_error": False,
                    }
                result = manager.get_result(agent_id)
                if result is None:
                    return {
                        "content": f"Sub-agent '{agent_id}' has no result (status: {info['status']}).",
                        "is_error": False,
                    }
                return {"content": result, "is_error": False}

            else:
                return {
                    "content": f"Unknown action: {action}. "
                    "Use: spawn, spawn_async, message, status, cancel, list, get_result",
                    "is_error": True,
                }

        except ValueError as e:
            return {"content": f"Error: {e}", "is_error": True}
        except Exception as e:
            return {"content": f"Sub-agent error: {e}", "is_error": True}

    return handle_manage_subagents
