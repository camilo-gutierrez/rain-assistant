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

  // Determine button state
  let buttonText: string;
  let buttonClass: string;
  let disabled = false;

  if (isProcessing || isTranscribing) {
    buttonText = isTranscribing
      ? t("status.transcribing")
      : t("status.rainWorking");
    buttonClass =
      "bg-surface2 text-subtext cursor-not-allowed relative overflow-hidden";
    disabled = true;
  } else if (isRecording) {
    buttonText = t("chat.recording");
    buttonClass = "text-white animate-neon-pulse-red";
  } else if (!hasCwd) {
    buttonText = t("status.selectProjectFirst");
    buttonClass = "bg-surface2 text-subtext cursor-not-allowed";
    disabled = true;
  } else {
    buttonText = t("chat.holdToSpeak");
    buttonClass = "text-cyan hover:shadow-[0_0_20px_var(--neon-glow)]";
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
      className={`w-full py-3 rounded-lg font-[family-name:var(--font-orbitron)] text-xs font-bold uppercase tracking-wider transition-all select-none touch-none border ${buttonClass} ${
        disabled
          ? ""
          : isRecording
          ? "border-red"
          : "border-cyan/40"
      }`}
      style={
        disabled
          ? undefined
          : isRecording
          ? { background: "linear-gradient(135deg, rgba(255,34,102,0.2), rgba(255,34,102,0.1))" }
          : { background: "linear-gradient(135deg, rgba(0,212,255,0.1), rgba(0,212,255,0.05))" }
      }
    >
      {/* Scan line animation when processing */}
      {(isProcessing || isTranscribing) && (
        <span
          className="absolute inset-0 animate-scan-line pointer-events-none"
          style={{
            background:
              "linear-gradient(90deg, transparent, rgba(0,212,255,0.1), transparent)",
          }}
        />
      )}
      <span className="relative z-10">{buttonText}</span>
    </button>
  );
}
