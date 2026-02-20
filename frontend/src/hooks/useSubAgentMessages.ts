import { useAgentStore } from "@/stores/useAgentStore";
import type { WSReceiveMessage } from "@/lib/types";

/**
 * Handles subagent_spawned and subagent_completed WebSocket messages.
 * Returns true if the message was handled, false otherwise.
 */
export function handleSubAgentMessage(msg: WSReceiveMessage, agentId: string): boolean {
  const agentStore = useAgentStore.getState();

  switch (msg.type) {
    case "subagent_spawned": {
      const parentId = msg.parent_agent_id;
      if (!agentStore.agents[parentId]) return true;
      agentStore.addSubAgent(parentId, {
        id: msg.agent_id,
        shortName: msg.short_name,
        parentId,
        task: msg.task,
        status: "running",
      });
      agentStore.appendMessage(parentId, {
        id: crypto.randomUUID(),
        type: "subagent_event",
        subAgentId: msg.agent_id,
        shortName: msg.short_name,
        eventType: "spawned",
        content: msg.task,
        status: "running",
        task: msg.task,
        timestamp: Date.now(),
        animate: true,
      });
      return true;
    }

    case "subagent_completed": {
      const parentId = msg.parent_agent_id;
      if (!agentStore.agents[parentId]) return true;
      const saStatus = msg.status as "completed" | "error" | "cancelled";
      agentStore.updateSubAgentStatus(parentId, msg.agent_id, saStatus);
      const shortName = msg.agent_id.split("::").pop() || "";
      agentStore.appendMessage(parentId, {
        id: crypto.randomUUID(),
        type: "subagent_event",
        subAgentId: msg.agent_id,
        shortName,
        eventType: "completed",
        content: msg.result_preview || `Sub-agent ${saStatus}`,
        status: saStatus,
        timestamp: Date.now(),
        animate: true,
      });
      return true;
    }

    default:
      return false;
  }
}
