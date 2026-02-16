"use client";

import { useEffect } from "react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useTranslation } from "@/hooks/useTranslation";
import { clearMessages as apiClearMessages } from "@/lib/api";
import ChatMessages from "@/components/chat/ChatMessages";
import ChatInput from "@/components/chat/ChatInput";
import RecordButton from "@/components/chat/RecordButton";
import InterruptButton from "@/components/chat/InterruptButton";

export default function ChatPanel() {
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const clearMessagesStore = useAgentStore((s) => s.clearMessages);
  const authToken = useConnectionStore((s) => s.authToken);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const { t } = useTranslation();
  const { initAudio } = useAudioRecorder();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const cwd = activeAgent?.cwd;

  // Initialize audio on first render
  useEffect(() => {
    initAudio();
  }, [initAudio]);

  const folderName = cwd
    ? cwd.replace(/\\/g, "/").split("/").filter(Boolean).pop() || cwd
    : null;

  const handleChange = () => {
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
      <div className="flex items-center gap-2 px-4 py-2 bg-surface border-b border-overlay">
        {/* Project name */}
        {folderName && (
          <span className="text-cyan font-[family-name:var(--font-jetbrains)] text-sm font-bold truncate">
            {folderName}
          </span>
        )}

        <div className="flex-1" />

        {/* Change button */}
        <button
          onClick={handleChange}
          className="px-3 py-1 text-xs rounded border border-overlay text-text2 hover:text-cyan hover:border-cyan transition-colors font-[family-name:var(--font-jetbrains)]"
        >
          {t("chat.changeBtn")}
        </button>

        {/* Clear button */}
        <button
          onClick={handleClear}
          className="px-3 py-1 text-xs rounded border border-overlay text-text2 hover:text-red hover:border-red transition-colors font-[family-name:var(--font-jetbrains)]"
        >
          {t("chat.clearBtn")}
        </button>
      </div>

      {/* Messages area */}
      <ChatMessages />

      {/* Input + Controls */}
      <div className="shrink-0">
        <ChatInput />
        <div className="flex gap-2 px-4 py-2 bg-surface border-t border-overlay">
          <div className="flex-1">
            <RecordButton />
          </div>
          <InterruptButton />
        </div>
      </div>
    </div>
  );
}
