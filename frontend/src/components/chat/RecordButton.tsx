"use client";

import { Mic, MicOff, Radio } from "lucide-react";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useVoiceModeStore } from "@/hooks/useVoiceMode";
import { useTranslation } from "@/hooks/useTranslation";

export default function RecordButton() {
  const { startRecording, stopRecording, isRecording } = useAudioRecorder();
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const statusText = useConnectionStore((s) => s.statusText);
  const voiceMode = useSettingsStore((s) => s.voiceMode);
  const voiceState = useVoiceModeStore((s) => s.voiceState);
  const { t } = useTranslation();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const isProcessing = activeAgent?.isProcessing || false;
  const hasCwd = !!activeAgent?.cwd;
  const isTranscribing = statusText.toLowerCase().includes("transcrib");
  const isVoiceActive = voiceState !== "idle";
  const isVADRecording = isVoiceActive && voiceState === "recording";

  let buttonClass: string;
  let ariaLabel: string;
  let disabled = false;
  let icon = <Mic size={20} />;

  if (isProcessing || isTranscribing) {
    buttonClass = "bg-surface2 text-subtext cursor-not-allowed";
    ariaLabel = isTranscribing ? t("status.transcribing") : t("status.rainWorking");
    disabled = true;
  } else if (isRecording || isVADRecording) {
    buttonClass = "bg-red/20 text-red border border-red/40";
    ariaLabel = t("chat.recording");
    icon = <MicOff size={20} />;
  } else if (isVoiceActive) {
    buttonClass = "bg-green/20 text-green border border-green/40";
    ariaLabel = t("voice.listening");
    icon = <Radio size={20} />;
  } else if (!hasCwd) {
    buttonClass = "bg-surface2 text-subtext cursor-not-allowed";
    ariaLabel = t("status.selectProjectFirst");
    disabled = true;
  } else {
    buttonClass = "bg-primary/10 text-primary hover:bg-primary/20";
    ariaLabel = voiceMode === "push-to-talk" ? t("chat.holdToSpeak") : t("voice.listening");
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
      {(isRecording || isVADRecording) && (
        <span className="absolute inset-0 rounded-full animate-pulse-ring" />
      )}
      {/* Gentle pulse when voice mode is active but not recording */}
      {isVoiceActive && !isVADRecording && !isRecording && (
        <span className="absolute inset-0 rounded-full animate-ping-slow opacity-30 bg-green/20" />
      )}
      <button
        onPointerDown={() => {
          if (!disabled && !isRecording && voiceMode === "push-to-talk") void startRecording();
        }}
        onPointerUp={() => {
          if (isRecording && voiceMode === "push-to-talk") stopRecording();
        }}
        onPointerLeave={() => {
          if (isRecording && voiceMode === "push-to-talk") stopRecording();
        }}
        onClick={() => {
          if (voiceMode !== "push-to-talk" && !disabled) {
            if (isRecording) {
              stopRecording();
            } else {
              void startRecording();
            }
          }
        }}
        onKeyDown={handleKeyDown}
        onContextMenu={(e) => e.preventDefault()}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-pressed={isRecording || isVADRecording}
        tabIndex={0}
        className={`relative min-w-[44px] min-h-[44px] w-11 h-11 flex items-center justify-center rounded-full text-sm font-medium transition-all select-none touch-none focus-ring ${buttonClass}`}
      >
        {icon}
      </button>
    </div>
  );
}
