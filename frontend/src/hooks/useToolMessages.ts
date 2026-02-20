import { useAgentStore } from "@/stores/useAgentStore";
import type { WSReceiveMessage, AnyMessage } from "@/lib/types";

/**
 * Handles tool_use and tool_result WebSocket messages.
 * Returns true if the message was handled, false otherwise.
 */
export function handleToolMessage(msg: WSReceiveMessage, agentId: string): boolean {
  const agentStore = useAgentStore.getState();

  switch (msg.type) {
    case "tool_use": {
      if (!agentStore.agents[agentId]) return true;
      agentStore.finalizeStreaming(agentId);
      const toolMsg: AnyMessage = {
        id: crypto.randomUUID(),
        type: "tool_use",
        tool: msg.tool,
        input: msg.input,
        toolUseId: msg.id,
        timestamp: Date.now(),
        animate: true,
      };
      agentStore.appendMessage(agentId, toolMsg);
      agentStore.incrementUnread(agentId);
      return true;
    }

    case "tool_result": {
      if (!agentStore.agents[agentId]) return true;
      const resultMsg: AnyMessage = {
        id: crypto.randomUUID(),
        type: "tool_result",
        content: msg.content,
        isError: msg.is_error,
        toolUseId: msg.tool_use_id,
        timestamp: Date.now(),
        animate: true,
      };
      agentStore.appendMessage(agentId, resultMsg);
      agentStore.incrementUnread(agentId);
      return true;
    }

    default:
      return false;
  }
}
