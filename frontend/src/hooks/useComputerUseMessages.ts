import { useAgentStore } from "@/stores/useAgentStore";
import type { WSReceiveMessage, ComputerScreenshotMessage, ComputerActionMessage } from "@/lib/types";

/**
 * Handles computer_screenshot, computer_action, and mode_changed WebSocket messages.
 * Returns true if the message was handled, false otherwise.
 */
export function handleComputerUseMessage(msg: WSReceiveMessage, agentId: string): boolean {
  const agentStore = useAgentStore.getState();

  switch (msg.type) {
    case "mode_changed": {
      if (!agentStore.agents[agentId]) return true;
      agentStore.setAgentMode(agentId, msg.mode);
      if (msg.display_info) {
        agentStore.setDisplayInfo(agentId, msg.display_info);
      }
      return true;
    }

    case "computer_screenshot": {
      if (!agentStore.agents[agentId]) return true;
      agentStore.updateLastScreenshot(agentId, msg.image);
      const screenshotMsg: ComputerScreenshotMessage = {
        id: crypto.randomUUID(),
        type: "computer_screenshot",
        image: msg.image,
        action: msg.action,
        description: msg.description,
        iteration: msg.iteration || 0,
        timestamp: Date.now(),
        animate: true,
      };
      agentStore.appendMessage(agentId, screenshotMsg);
      agentStore.incrementUnread(agentId);
      return true;
    }

    case "computer_action": {
      if (!agentStore.agents[agentId]) return true;
      const actionMsg: ComputerActionMessage = {
        id: crypto.randomUUID(),
        type: "computer_action",
        tool: msg.tool,
        action: msg.action,
        input: msg.input,
        description: msg.description,
        iteration: msg.iteration || 0,
        timestamp: Date.now(),
        animate: true,
      };
      agentStore.appendMessage(agentId, actionMsg);
      agentStore.incrementComputerIteration(agentId);
      return true;
    }

    default:
      return false;
  }
}
