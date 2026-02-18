"use client";

import { FolderOpen, Save, Trash2, RotateCcw } from "lucide-react";
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
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-text truncate">
            <FolderOpen size={14} className="shrink-0 text-subtext" />
            {folderName}
          </span>
        )}

        <div className="flex-1" />

        <button
          onClick={() => save()}
          disabled={isSaving || !activeAgent?.messages.length}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-green transition-colors disabled:opacity-30"
        >
          <Save size={13} />
          {isSaving ? t("history.saving") : t("history.saveBtn")}
        </button>

        <button
          onClick={handleChange}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-primary transition-colors"
        >
          <RotateCcw size={13} />
          {t("chat.changeBtn")}
        </button>

        <button
          onClick={handleClear}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-red transition-colors"
        >
          <Trash2 size={13} />
          {t("chat.clearBtn")}
        </button>
      </div>

      {/* Computer Use toolbar (only visible when in computer_use mode) */}
      <ComputerUseToolbar />

      {/* Messages */}
      <ChatMessages />

      {/* Unified input area */}
      <div className="shrink-0 bg-surface border-t border-overlay">
        <div className="max-w-3xl mx-auto px-4">
          {/* InterruptButton floats above textarea when visible */}
          <InterruptButton />

          {/* Textarea row */}
          <div className="pt-3">
            <ChatInput />
          </div>

          {/* Bottom bar: RecordButton | hint | send area */}
          <div className="flex items-center justify-between py-2">
            <RecordButton />
            <span className="hidden sm:inline text-[11px] text-subtext select-none">
              {t("chat.shiftEnterHint")}
            </span>
            {/* Send button is part of ChatInput, right side is balanced by this spacer on small screens */}
            <div className="w-11 sm:hidden" />
          </div>
        </div>
      </div>
    </div>
  );
}
