"use client";

import { useVoiceModeStore } from "@/hooks/useVoiceMode";

/**
 * LiveTranscription — Shows partial transcription text in real-time
 * as the user speaks. Appears above the chat input.
 */
export default function LiveTranscription() {
  const partial = useVoiceModeStore((s) => s.partialTranscription);
  const voiceState = useVoiceModeStore((s) => s.voiceState);

  if (!partial && voiceState !== "recording" && voiceState !== "transcribing") {
    return null;
  }

  return (
    <div className="px-4 py-2 text-sm text-subtext italic border-b border-overlay/50 bg-surface/50 animate-fade-in">
      {partial ? (
        <span>
          &ldquo;{partial}
          <span className="animate-pulse">|</span>&rdquo;
        </span>
      ) : voiceState === "transcribing" ? (
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-yellow animate-pulse" />
          Transcribing...
        </span>
      ) : null}
    </div>
  );
}
