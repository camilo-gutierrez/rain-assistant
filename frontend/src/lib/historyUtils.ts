import { useAgentStore } from "@/stores/useAgentStore";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { saveConversation, listConversations } from "@/lib/api";
import type { ConversationFull } from "@/lib/types";

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
