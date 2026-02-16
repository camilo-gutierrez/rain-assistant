"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { useHistory } from "@/hooks/useHistory";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { clearMessages as apiClearMessages } from "@/lib/api";
import ChatMessages from "@/components/chat/ChatMessages";
import ChatInput from "@/components/chat/ChatInput";
import RecordButton from "@/components/chat/RecordButton";
import InterruptButton from "@/components/chat/InterruptButton";
import ComputerUseToolbar from "@/components/computer-use/ComputerUseToolbar";

export default function ChatPanel() {
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const clearMessagesStore = useAgentStore((s) => s.clearMessages);
  const authToken = useConnectionStore((s) => s.authToken);
  const setAgentPanel = useAgentStore((s) => s.setAgentPanel);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const { t } = useTranslation();
  const { save } = useHistory();
  const isSaving = useHistoryStore((s) => s.isSaving);

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const cwd = activeAgent?.cwd;

  const folderName = cwd
    ? cwd.replace(/\\/g, "/").split("/").filter(Boolean).pop() || cwd
    : null;

  const handleChange = () => {
    if (activeAgentId) setAgentPanel(activeAgentId, "fileBrowser");
    setActivePanel("fileBrowser");
  };

  const handleClear = async () => {
    if (!activeAgentId || !cwd) return;
    try {
      await apiClearMessages(cwd, activeAgentId, authToken);
      clearMessagesStore(activeAgentId);
    } catch (err) {
      console.error("Clear messages error:", err);
    }
  };

  if (!activeAgent) {
    return (
      <div className="flex-1 flex items-center justify-center text-text2">
        {t("chat.selectDirFirst")}
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Chat header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-surface border-b border-overlay">
        {folderName && (
          <span className="text-sm font-medium text-text truncate">
            {folderName}
          </span>
        )}

        <div className="flex-1" />

        <button
          onClick={() => save()}
          disabled={isSaving || !activeAgent?.messages.length}
          className="px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-green transition-colors disabled:opacity-30"
        >
          {isSaving ? t("history.saving") : t("history.saveBtn")}
        </button>

        <button
          onClick={handleChange}
          className="px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-primary transition-colors"
        >
          {t("chat.changeBtn")}
        </button>

        <button
          onClick={handleClear}
          className="px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-red transition-colors"
        >
          {t("chat.clearBtn")}
        </button>
      </div>

      {/* Computer Use toolbar (only visible when in computer_use mode) */}
      <ComputerUseToolbar />

      {/* Messages */}
      <ChatMessages />

      {/* Input controls */}
      <div className="shrink-0">
        <InterruptButton />
        <ChatInput />
        <div className="px-4 py-2 bg-surface border-t border-overlay">
          <RecordButton />
        </div>
      </div>
    </div>
  );
}
