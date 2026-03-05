"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import type { WSReceiveMessage, A2UISurface, A2UIComponent } from "@/lib/types";

/**
 * Handle A2UI (Agent-to-UI) surface messages.
 * - a2ui_surface: append a new surface message to the agent
 * - a2ui_update: merge updates into an existing surface's components
 */
export function handleA2UIMessage(
  msg: WSReceiveMessage,
  agentId: string,
): boolean {
  if (msg.type === "a2ui_surface") {
    const agentStore = useAgentStore.getState();
    agentStore.appendMessage(agentId, {
      id: `a2ui-${msg.surface.id}-${Date.now()}`,
      type: "a2ui_surface",
      surface: msg.surface as A2UISurface,
      timestamp: Date.now(),
      animate: true,
    });
    return true;
  }

  if (msg.type === "a2ui_update") {
    const agentStore = useAgentStore.getState();
    const agent = agentStore.agents[agentId];
    if (!agent) return true;

    // Find the surface message and apply updates
    const surfaceId = (msg as { surface_id: string }).surface_id;
    const updates = (msg as { updates: Array<{ id: string } & Partial<A2UIComponent>> }).updates;

    const updatedMessages = agent.messages.map((m) => {
      if (m.type !== "a2ui_surface") return m;
      if (m.surface.id !== surfaceId) return m;

      const newComponents = { ...m.surface.components };
      for (const update of updates) {
        if (newComponents[update.id]) {
          newComponents[update.id] = { ...newComponents[update.id], ...update };
        }
      }

      return {
        ...m,
        surface: { ...m.surface, components: newComponents },
      };
    });

    // Replace messages in store
    agentStore.setMessages(agentId, updatedMessages);
    return true;
  }

  return false;
}
