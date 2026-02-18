"use client";

import { Mic, MicOff } from "lucide-react";
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

  let buttonClass: string;
  let ariaLabel: string;
  let disabled = false;

  if (isProcessing || isTranscribing) {
    buttonClass = "bg-surface2 text-subtext cursor-not-allowed";
    ariaLabel = isTranscribing
      ? t("status.transcribing")
      : t("status.rainWorking");
    disabled = true;
  } else if (isRecording) {
    buttonClass = "bg-red/20 text-red border-red/40";
    ariaLabel = t("chat.recording");
  } else if (!hasCwd) {
    buttonClass = "bg-surface2 text-subtext cursor-not-allowed";
    ariaLabel = t("status.selectProjectFirst");
    disabled = true;
  } else {
    buttonClass = "bg-primary/10 text-primary hover:bg-primary/20";
    ariaLabel = t("chat.holdToSpeak");
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      if (disabled) return;
      if (isRecording) {
        stopRecording();
      } else {
        void startRecording();
      }
    }
  };

  return (
    <div className="relative inline-flex items-center justify-center">
      {/* Pulsing ring behind button when recording */}
      {isRecording && (
        <span className="absolute inset-0 rounded-full animate-pulse-ring" />
      )}
      <button
        onPointerDown={() => {
          if (!disabled && !isRecording) void startRecording();
        }}
        onPointerUp={() => {
          if (isRecording) stopRecording();
        }}
        onPointerLeave={() => {
          if (isRecording) stopRecording();
        }}
        onKeyDown={handleKeyDown}
        onContextMenu={(e) => e.preventDefault()}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-pressed={isRecording}
        tabIndex={0}
        className={`relative min-w-[44px] min-h-[44px] w-11 h-11 flex items-center justify-center rounded-full text-sm font-medium transition-all select-none touch-none focus-ring ${buttonClass}`}
      >
        {isRecording ? <MicOff size={20} /> : <Mic size={20} />}
      </button>
    </div>
  );
}
