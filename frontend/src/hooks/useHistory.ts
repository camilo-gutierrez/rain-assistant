import { useCallback } from "react";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useToastStore } from "@/stores/useToastStore";
import {
  listConversations,
  saveConversation,
  loadConversation,
  deleteConversation,
} from "@/lib/api";
import { translate } from "@/lib/translations";
import type { ConversationFull } from "@/lib/types";

export function useHistory() {
  const authToken = useConnectionStore((s) => s.authToken);

  const refreshList = useCallback(async () => {
    const store = useHistoryStore.getState();
    store.setLoading(true);
    try {
      const data = await listConversations(authToken);
      store.setConversations(data.conversations);
    } catch (err) {
      console.error("Failed to list conversations:", err);
    } finally {
      store.setLoading(false);
    }
  }, [authToken]);

  const save = useCallback(
    async (agentId?: string) => {
      const agentStore = useAgentStore.getState();
      const historyStore = useHistoryStore.getState();
      const aid = agentId || agentStore.activeAgentId;
      if (!aid) return;
      const agent = agentStore.agents[aid];
      if (!agent || agent.messages.length === 0) return;

      historyStore.setSaving(true);

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
        historyStore.activeConversationId || `conv_${now}_${aid}`;

      const folderName = agent.cwd
        ? agent.cwd
            .replace(/\\/g, "/")
            .split("/")
            .filter(Boolean)
            .pop() || "project"
        : "project";

      const existing = historyStore.conversations.find(
        (c) => c.id === convId
      );

      const conversation: ConversationFull = {
        version: 1,
        id: convId,
        createdAt: existing?.createdAt || now,
        updatedAt: now,
        agentId: aid,
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
        await refreshList();

        const lang = useSettingsStore.getState().language;
        useToastStore.getState().addToast({
          type: "success",
          message: translate(lang, "toast.saveSuccess"),
        });
      } catch (err) {
        console.error("Failed to save conversation:", err);
        const lang = useSettingsStore.getState().language;
        useToastStore.getState().addToast({
          type: "error",
          message: translate(lang, "toast.saveFailed"),
        });
      } finally {
        historyStore.setSaving(false);
      }
    },
    [authToken, refreshList]
  );

  const load = useCallback(
    async (conversationId: string) => {
      const agentStore = useAgentStore.getState();
      const historyStore = useHistoryStore.getState();
      const connectionStore = useConnectionStore.getState();
      const aid = agentStore.activeAgentId;
      if (!aid) return;

      historyStore.setLoading(true);
      try {
        const conv = await loadConversation(conversationId, authToken);

        // Set messages in the agent store
        agentStore.setMessages(aid, conv.messages);
        agentStore.setHistoryLoaded(aid, true);

        // Set session_id for resumption
        if (conv.sessionId) {
          agentStore.setAgentSessionId(aid, conv.sessionId);
        }

        // Re-init agent on server with the conversation's cwd + session
        if (conv.cwd) {
          agentStore.setAgentCwd(aid, conv.cwd);
          connectionStore.send({
            type: "set_cwd",
            path: conv.cwd,
            agent_id: aid,
            session_id: conv.sessionId || undefined,
          });
        }

        historyStore.setActiveConversationId(conversationId);
      } catch (err) {
        console.error("Failed to load conversation:", err);
      } finally {
        historyStore.setLoading(false);
      }
    },
    [authToken]
  );

  const remove = useCallback(
    async (conversationId: string) => {
      const historyStore = useHistoryStore.getState();
      try {
        await deleteConversation(conversationId, authToken);
        if (historyStore.activeConversationId === conversationId) {
          historyStore.setActiveConversationId(null);
        }
        await refreshList();

        const lang = useSettingsStore.getState().language;
        useToastStore.getState().addToast({
          type: "success",
          message: translate(lang, "toast.deletedConversation"),
        });
      } catch (err) {
        console.error("Failed to delete conversation:", err);
        const lang = useSettingsStore.getState().language;
        useToastStore.getState().addToast({
          type: "error",
          message: translate(lang, "toast.saveFailed"),
        });
      }
    },
    [authToken, refreshList]
  );

  return { refreshList, save, load, remove };
}
