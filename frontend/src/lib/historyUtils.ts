import { useAgentStore } from "@/stores/useAgentStore";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { saveConversation, listConversations, loadMessages } from "@/lib/api";
import type { AnyMessage, ConversationFull } from "@/lib/types";

export async function autoSaveConversation(
  agentId: string,
  authToken: string | null
) {
  const agentStore = useAgentStore.getState();
  const historyStore = useHistoryStore.getState();
  const agent = agentStore.agents[agentId];
  if (!agent || agent.messages.length === 0) return;

  const firstUserMsg = agent.messages.find((m) => m.type === "user");
  const preview =
    firstUserMsg && "text" in firstUserMsg
      ? firstUserMsg.text.slice(0, 100)
      : "";

  let totalCost = 0;
  for (const m of agent.messages) {
    if (m.type === "system" && "text" in m) {
      const costMatch = m.text.match(/\$(\d+\.\d+)/);
      if (costMatch) totalCost += parseFloat(costMatch[1]);
    }
  }

  const now = Date.now();
  const convId =
    historyStore.activeConversationId || `conv_${now}_${agentId}`;

  const folderName = agent.cwd
    ? agent.cwd
        .replace(/\\/g, "/")
        .split("/")
        .filter(Boolean)
        .pop() || "project"
    : "project";

  const existing = historyStore.conversations.find((c) => c.id === convId);

  const conversation: ConversationFull = {
    version: 1,
    id: convId,
    createdAt: existing?.createdAt || now,
    updatedAt: now,
    agentId,
    cwd: agent.cwd || "",
    sessionId: agent.sessionId,
    label: folderName,
    messageCount: agent.messages.length,
    preview,
    totalCost,
    messages: agent.messages.map((m) => ({ ...m, animate: false })),
  };

  try {
    const result = await saveConversation(conversation, authToken);
    historyStore.setActiveConversationId(result.id);
    const data = await listConversations(authToken);
    historyStore.setConversations(data.conversations);
  } catch (err) {
    console.error("[auto-save] Failed:", err);
  }
}

/**
 * Loads message history from the server for a specific agent.
 * Converts raw API messages into the AnyMessage[] format used in the agent store.
 */
export async function loadHistoryForAgent(
  cwd: string,
  agentId: string,
  authToken: string | null
) {
  try {
    const data = await loadMessages(cwd, agentId, authToken);
    const agentState = useAgentStore.getState();
    // Mark history as loaded even if empty, to prevent future reloads
    agentState.setHistoryLoaded(agentId, true);
    if (!data.messages || data.messages.length === 0) return;

    const messages: AnyMessage[] = [];
    for (const msg of data.messages) {
      switch (msg.type) {
        case "text":
          messages.push({
            id: crypto.randomUUID(),
            type: "user",
            text: (msg.content as { text: string }).text,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "assistant_text":
          messages.push({
            id: crypto.randomUUID(),
            type: "assistant",
            text: (msg.content as { text: string }).text,
            isStreaming: false,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "tool_use":
          messages.push({
            id: crypto.randomUUID(),
            type: "tool_use",
            tool: (msg.content as { tool: string }).tool,
            input: (msg.content as { input: Record<string, unknown> }).input || {},
            toolUseId: (msg.content as { id: string }).id,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "tool_result":
          messages.push({
            id: crypto.randomUUID(),
            type: "tool_result",
            content: (msg.content as { content: string }).content,
            isError: (msg.content as { is_error: boolean }).is_error,
            toolUseId: (msg.content as { tool_use_id: string }).tool_use_id,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "result": {
          const r = msg.content as {
            cost?: number;
            duration_ms?: number;
            num_turns?: number;
            session_id?: string;
          };
          if (r.cost != null || r.duration_ms != null) {
            let info = "";
            if (r.duration_ms) info += (r.duration_ms / 1000).toFixed(1) + "s";
            if (r.num_turns) info += " | " + r.num_turns + " turns";
            if (r.cost) info += " | $" + r.cost.toFixed(4);
            if (info) {
              messages.push({
                id: crypto.randomUUID(),
                type: "system",
                text: info,
                timestamp: msg.timestamp,
                animate: false,
              });
            }
          }
          break;
        }
        case "error":
          messages.push({
            id: crypto.randomUUID(),
            type: "system",
            text: "Error: " + (msg.content as { text: string }).text,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
      }
    }

    // Safety: if user sent messages while history was loading, don't overwrite them
    const currentAgent = useAgentStore.getState().agents[agentId];
    if (!currentAgent || currentAgent.messages.length > 0) return;

    useAgentStore.getState().setMessages(agentId, messages);

    // Extract session_id from the last result message for conversation resumption
    for (let i = data.messages.length - 1; i >= 0; i--) {
      const m = data.messages[i];
      if (m.type === "result") {
        const sid = (m.content as { session_id?: string }).session_id;
        if (sid) {
          useAgentStore.getState().setAgentSessionId(agentId, sid);
        }
        break;
      }
    }
  } catch (err) {
    console.warn("Failed to load history:", err);
  }
}
