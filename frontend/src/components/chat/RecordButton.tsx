"use client";

import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";

export default function RecordButton() {
  const { startRecording, stopRecording, isRecording } = useAudioRecorder();
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const statusText = useConnectionStore((s) => s.statusText);
  const { t } = useTranslation();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const isProcessing = activeAgent?.isProcessing || false;
  const hasCwd = !!activeAgent?.cwd;

  const isTranscribing = statusText.toLowerCase().includes("transcrib");

  let buttonText: string;
  let buttonClass: string;
  let disabled = false;

  if (isProcessing || isTranscribing) {
    buttonText = isTranscribing
      ? t("status.transcribing")
      : t("status.rainWorking");
    buttonClass = "bg-surface2 text-subtext cursor-not-allowed";
    disabled = true;
  } else if (isRecording) {
    buttonText = t("chat.recording");
    buttonClass = "bg-red text-white animate-pulse";
  } else if (!hasCwd) {
    buttonText = t("status.selectProjectFirst");
    buttonClass = "bg-surface2 text-subtext cursor-not-allowed";
    disabled = true;
  } else {
    buttonText = t("chat.holdToSpeak");
    buttonClass = "bg-primary/10 text-primary hover:bg-primary/20";
  }

  return (
    <button
      onPointerDown={() => {
        if (!disabled && !isRecording) startRecording();
      }}
      onPointerUp={() => {
        if (isRecording) stopRecording();
      }}
      onPointerLeave={() => {
        if (isRecording) stopRecording();
      }}
      onContextMenu={(e) => e.preventDefault()}
      disabled={disabled}
      className={`w-full py-3 rounded-lg text-sm font-medium transition-all select-none touch-none ${buttonClass}`}
    >
      <span className="flex items-center justify-center gap-2">
        {/* Mic icon */}
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
        {buttonText}
      </span>
    </button>
  );
}
