"use client";

import { Mic, Radio, Ear, Brain, Volume2 } from "lucide-react";
import { useVoiceModeStore } from "@/hooks/useVoiceMode";
import { useTranslation } from "@/hooks/useTranslation";

const STATE_CONFIG = {
  idle: { icon: null, label: "", color: "" },
  wake_listening: { icon: Radio, label: "voice.wakeListening", color: "text-blue" },
  listening: { icon: Ear, label: "voice.listening", color: "text-green" },
  recording: { icon: Mic, label: "voice.recording", color: "text-red" },
  transcribing: { icon: Mic, label: "voice.transcribing", color: "text-yellow" },
  processing: { icon: Brain, label: "voice.processing", color: "text-purple" },
  speaking: { icon: Volume2, label: "voice.speaking", color: "text-primary" },
} as const;

export default function VoiceModeIndicator() {
  const voiceState = useVoiceModeStore((s) => s.voiceState);
  const partialTranscription = useVoiceModeStore((s) => s.partialTranscription);
  const { t } = useTranslation();

  if (voiceState === "idle") return null;

  const cfg = STATE_CONFIG[voiceState];
  const Icon = cfg.icon;
  if (!Icon) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface2/80 backdrop-blur-sm border border-overlay text-xs font-medium animate-fade-in">
      {/* Pulsing dot for active states */}
      {(voiceState === "recording" || voiceState === "listening" || voiceState === "wake_listening") && (
        <span className={`w-2 h-2 rounded-full ${voiceState === "recording" ? "bg-red" : "bg-green"} animate-pulse`} />
      )}

      <Icon size={14} className={cfg.color} />

      <span className={cfg.color}>
        {partialTranscription || t(cfg.label)}
      </span>

      {/* Audio wave animation during recording */}
      {voiceState === "recording" && (
        <div className="flex items-center gap-0.5 ml-1">
          {[1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className="w-0.5 bg-red rounded-full animate-voice-wave"
              style={{
                height: `${8 + Math.random() * 8}px`,
                animationDelay: `${i * 0.1}s`,
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
