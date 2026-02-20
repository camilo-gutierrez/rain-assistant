"use client";

import { PhoneOff, Mic, Brain, Volume2, Ear } from "lucide-react";
import { useVoiceModeStore } from "@/hooks/useVoiceMode";
import { useTranslation } from "@/hooks/useTranslation";

interface TalkModeOverlayProps {
  onEnd: () => void;
}

const RING_COLORS: Record<string, string> = {
  listening: "border-green shadow-green/20",
  recording: "border-red shadow-red/30",
  transcribing: "border-yellow shadow-yellow/20",
  processing: "border-purple shadow-purple/20",
  speaking: "border-primary shadow-primary/20",
};

const STATE_ICONS: Record<string, typeof Mic> = {
  listening: Ear,
  recording: Mic,
  transcribing: Mic,
  processing: Brain,
  speaking: Volume2,
};

const STATE_LABELS: Record<string, string> = {
  listening: "voice.listening",
  recording: "voice.recording",
  transcribing: "voice.transcribing",
  processing: "voice.processing",
  speaking: "voice.speaking",
};

export default function TalkModeOverlay({ onEnd }: TalkModeOverlayProps) {
  const voiceState = useVoiceModeStore((s) => s.voiceState);
  const partialTranscription = useVoiceModeStore((s) => s.partialTranscription);
  const lastTranscription = useVoiceModeStore((s) => s.lastTranscription);
  const { t } = useTranslation();

  const ringColor = RING_COLORS[voiceState] || "border-overlay";
  const Icon = STATE_ICONS[voiceState] || Ear;
  const label = STATE_LABELS[voiceState] || "voice.listening";
  const isActive = voiceState === "recording" || voiceState === "speaking";

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-bg/95 backdrop-blur-md animate-fade-in">
      {/* Central orb */}
      <div className="relative mb-8">
        {/* Outer pulsing ring */}
        <div
          className={`absolute inset-0 rounded-full border-2 ${ringColor} transition-all duration-500 ${
            isActive ? "animate-ping-slow scale-150 opacity-30" : "scale-100 opacity-0"
          }`}
          style={{ width: 160, height: 160, margin: -20 }}
        />

        {/* Middle ring */}
        <div
          className={`w-[120px] h-[120px] rounded-full border-4 ${ringColor} shadow-lg flex items-center justify-center transition-all duration-300`}
        >
          <Icon
            size={48}
            className={`transition-all duration-300 ${
              voiceState === "recording"
                ? "text-red animate-pulse"
                : voiceState === "speaking"
                ? "text-primary animate-pulse"
                : "text-text"
            }`}
          />
        </div>
      </div>

      {/* State label */}
      <p className="text-lg font-medium text-text mb-2 transition-all duration-300">
        {t(label)}
      </p>

      {/* Live transcription preview */}
      {(partialTranscription || (voiceState === "processing" && lastTranscription)) && (
        <p className="text-sm text-subtext max-w-md text-center px-4 mb-4 italic animate-fade-in">
          &ldquo;{partialTranscription || lastTranscription}&rdquo;
        </p>
      )}

      {/* Audio wave visualization during recording */}
      {voiceState === "recording" && (
        <div className="flex items-end gap-1 h-8 mb-6">
          {Array.from({ length: 12 }).map((_, i) => (
            <span
              key={i}
              className="w-1 bg-red/70 rounded-full animate-voice-wave"
              style={{
                animationDelay: `${i * 0.08}s`,
                height: `${12 + Math.random() * 20}px`,
              }}
            />
          ))}
        </div>
      )}

      {/* End button */}
      <button
        onClick={onEnd}
        className="mt-4 flex items-center gap-2 px-6 py-3 rounded-full bg-red/10 text-red hover:bg-red/20 border border-red/30 transition-all font-medium"
      >
        <PhoneOff size={20} />
        {t("voice.endConversation")}
      </button>
    </div>
  );
}
