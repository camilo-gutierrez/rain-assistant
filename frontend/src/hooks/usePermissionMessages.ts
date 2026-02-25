import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import type { WSReceiveMessage, AnyMessage } from "@/lib/types";

/**
 * Handles permission_request WebSocket messages.
 * Returns true if the message was handled, false otherwise.
 */
export function handlePermissionMessage(msg: WSReceiveMessage, agentId: string): boolean {
  if (msg.type !== "permission_request") return false;

  const agentStore = useAgentStore.getState();
  const agent = agentStore.agents[agentId];
  if (!agent) return true;

  // Safety net: if auto-approve is on, auto-respond (shouldn't happen if backend is correct)
  if (agent.autoApprove) {
    useConnectionStore.getState().send({
      type: "permission_response",
      request_id: msg.request_id,
      agent_id: agentId,
      approved: true,
    });
    return true;
  }

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
