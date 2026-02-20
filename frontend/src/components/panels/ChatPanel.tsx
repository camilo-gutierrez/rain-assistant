"use client";

import { useState } from "react";
import { FolderOpen, Save, Trash2, RotateCcw } from "lucide-react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { useHistory } from "@/hooks/useHistory";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useVoiceMode, useVoiceModeStore } from "@/hooks/useVoiceMode";
import { clearMessages as apiClearMessages } from "@/lib/api";
import ChatMessages from "@/components/chat/ChatMessages";
import ChatInput from "@/components/chat/ChatInput";
import RecordButton from "@/components/chat/RecordButton";
import InterruptButton from "@/components/chat/InterruptButton";
import ComputerUseToolbar from "@/components/computer-use/ComputerUseToolbar";
import VoiceModeIndicator from "@/components/chat/VoiceModeIndicator";
import LiveTranscription from "@/components/chat/LiveTranscription";
import TalkModeOverlay from "@/components/chat/TalkModeOverlay";

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
  const voiceMode = useSettingsStore((s) => s.voiceMode);
  const voiceState = useVoiceModeStore((s) => s.voiceState);
  const { activate, deactivate } = useVoiceMode();
  const [talkModeActive, setTalkModeActive] = useState(false);

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

  const handleTalkModeToggle = () => {
    if (!activeAgentId) return;
    if (talkModeActive) {
      deactivate(activeAgentId);
      setTalkModeActive(false);
    } else {
      activate(activeAgentId);
      setTalkModeActive(true);
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
      <div className="flex items-center gap-1 sm:gap-2 px-3 sm:px-4 py-2 bg-surface border-b border-overlay">
        {folderName && (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-text truncate min-w-0">
            <FolderOpen size={14} className="shrink-0 text-subtext" />
            <span className="truncate">{folderName}</span>
          </span>
        )}

        <div className="flex-1" />

        <button
          onClick={() => save()}
          disabled={isSaving || !activeAgent?.messages.length}
          className="inline-flex items-center justify-center gap-1.5 min-w-[36px] min-h-[36px] px-2 sm:px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-green transition-colors disabled:opacity-30 shrink-0"
          title={isSaving ? t("history.saving") : t("history.saveBtn")}
        >
          <Save size={14} />
          <span className="hidden sm:inline">{isSaving ? t("history.saving") : t("history.saveBtn")}</span>
        </button>

        <button
          onClick={handleChange}
          className="inline-flex items-center justify-center gap-1.5 min-w-[36px] min-h-[36px] px-2 sm:px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-primary transition-colors shrink-0"
          title={t("chat.changeBtn")}
        >
          <RotateCcw size={14} />
          <span className="hidden sm:inline">{t("chat.changeBtn")}</span>
        </button>

        <button
          onClick={handleClear}
          className="inline-flex items-center justify-center gap-1.5 min-w-[36px] min-h-[36px] px-2 sm:px-3 py-1.5 text-xs rounded-md text-text2 hover:bg-surface2 hover:text-red transition-colors shrink-0"
          title={t("chat.clearBtn")}
        >
          <Trash2 size={14} />
          <span className="hidden sm:inline">{t("chat.clearBtn")}</span>
        </button>
      </div>

      {/* Computer Use toolbar (only visible when in computer_use mode) */}
      <ComputerUseToolbar />

      {/* Messages */}
      <ChatMessages />

      {/* Live transcription preview (above input when recording) */}
      <LiveTranscription />

      {/* Unified input area */}
      <div className="shrink-0 bg-surface border-t border-overlay">
        <div className="max-w-3xl mx-auto px-4">
          {/* Voice mode indicator (above input when active) */}
          {voiceState !== "idle" && (
            <div className="flex justify-center pt-2">
              <VoiceModeIndicator />
            </div>
          )}

          {/* InterruptButton floats above textarea when visible */}
          <InterruptButton />

          {/* Textarea row */}
          <div className="pt-3">
            <ChatInput />
          </div>

          {/* Bottom bar: RecordButton | Talk Mode | hint | send area */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2">
              <RecordButton />
              {voiceMode !== "push-to-talk" && (
                <button
                  onClick={handleTalkModeToggle}
                  disabled={!activeAgent?.cwd}
                  className={`min-w-[36px] min-h-[36px] px-3 py-1.5 text-xs rounded-full font-medium transition-all ${
                    talkModeActive
                      ? "bg-green/20 text-green border border-green/40"
                      : "bg-surface2 text-text2 hover:bg-surface2/80"
                  } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  {talkModeActive ? t("voice.endConversation") : t("voice.startTalkMode")}
                </button>
              )}
            </div>
            <span className="hidden sm:inline text-[11px] text-subtext select-none">
              {t("chat.shiftEnterHint")}
            </span>
            {/* Send button is part of ChatInput, right side is balanced by this spacer on small screens */}
            <div className="w-11 sm:hidden" />
          </div>
        </div>
      </div>

      {/* Talk Mode overlay (fullscreen when active) */}
      {talkModeActive && voiceMode === "talk-mode" && (
        <TalkModeOverlay onEnd={handleTalkModeToggle} />
      )}
    </div>
  );
}
