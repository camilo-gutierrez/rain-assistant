import { useAgentStore } from "@/stores/useAgentStore";
import type { WSReceiveMessage, AnyMessage } from "@/lib/types";

/**
 * Handles permission_request WebSocket messages.
 * Returns true if the message was handled, false otherwise.
 */
export function handlePermissionMessage(msg: WSReceiveMessage, agentId: string): boolean {
  if (msg.type !== "permission_request") return false;

  const agentStore = useAgentStore.getState();
  if (!agentStore.agents[agentId]) return true;

  agentStore.finalizeStreaming(agentId);
  const permMsg: AnyMessage = {
    id: crypto.randomUUID(),
    type: "permission_request",
    requestId: msg.request_id,
    tool: msg.tool,
    input: msg.input,
    level: msg.level,
    reason: msg.reason,
    status: "pending",
    timestamp: Date.now(),
    animate: true,
  };
  agentStore.appendMessage(agentId, permMsg);
  agentStore.incrementUnread(agentId);
  return true;
}
