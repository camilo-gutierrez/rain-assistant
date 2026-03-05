"use client";

import React from "react";
import { PhoneOff, Mic, MicOff, Brain, Volume2, Ear } from "lucide-react";
import { useVoiceModeStore } from "@/hooks/useVoiceMode";
import { useTranslation } from "@/hooks/useTranslation";

interface TalkModeOverlayProps {
  onEnd: () => void;
  onToggleMute: () => void;
}

const RING_COLORS: Record<string, string> = {
  listening: "border-green shadow-green/20",
  recording: "border-red shadow-red/30",
  transcribing: "border-yellow shadow-yellow/20",
  processing: "border-mauve shadow-mauve/20",
  speaking: "border-primary shadow-primary/20",
};

const DOT_COLORS: Record<string, string> = {
  listening: "bg-green",
  recording: "bg-red",
  transcribing: "bg-yellow",
  processing: "bg-mauve",
  speaking: "bg-primary",
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

function formatCallDuration(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const s = (totalSeconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// ── Audio Visualizer (responsive to audioLevel) ──

const AudioVisualizerBars = React.memo(function AudioVisualizerBars({
  audioLevel,
  barCount,
}: {
  audioLevel: number;
  barCount: number;
}) {
  return (
    <div className="flex items-center gap-0.5 h-10 mb-4">
      {Array.from({ length: barCount }).map((_, i) => {
        const phase = (i / barCount) * Math.PI;
        const waveHeight = Math.sin(phase);
        const h = 6 + 34 * waveHeight * (0.3 + audioLevel * 0.7);
        return (
          <span
            key={i}
            className="w-0.5 rounded-full bg-red/70 transition-[height] duration-75"
            style={{ height: `${Math.max(4, Math.min(40, h))}px` }}
          />
        );
      })}
    </div>
  );
});

// ── Speaking Wave (CSS animation during TTS) ──

const SpeakingWaveBars = React.memo(function SpeakingWaveBars({
  barCount,
}: {
  barCount: number;
}) {
  return (
    <div className="flex items-center gap-0.5 h-10 mb-4">
      {Array.from({ length: barCount }).map((_, i) => (
        <span
          key={i}
          className="w-0.5 bg-primary/50 rounded-full animate-voice-wave"
          style={{
            animationDelay: `${i * 0.06}s`,
            height: `${8 + 24 * Math.sin(((i * 0.18) % 1) * Math.PI)}px`,
          }}
        />
      ))}
    </div>
  );
});

// ── Main Overlay ──

export default function TalkModeOverlay({ onEnd, onToggleMute }: TalkModeOverlayProps) {
  const voiceState = useVoiceModeStore((s) => s.voiceState);
  const partialTranscription = useVoiceModeStore((s) => s.partialTranscription);
  const lastTranscription = useVoiceModeStore((s) => s.lastTranscription);
  const isMuted = useVoiceModeStore((s) => s.isMuted);
  const callDurationSeconds = useVoiceModeStore((s) => s.callDurationSeconds);
  const audioLevel = useVoiceModeStore((s) => s.audioLevel);
  const { t } = useTranslation();

  const ringColor = RING_COLORS[voiceState] || "border-overlay";
  const dotColor = DOT_COLORS[voiceState] || "bg-subtext";
  const Icon = STATE_ICONS[voiceState] || Ear;
  const label = STATE_LABELS[voiceState] || "voice.listening";
  const isActive = voiceState === "recording" || voiceState === "speaking";

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center bg-bg/95 backdrop-blur-md animate-fade-in">
      {/* Top bar: status dot + state label + duration timer */}
      <div className="flex items-center gap-2 w-full px-6 py-4">
        <span className={`w-2.5 h-2.5 rounded-full ${dotColor} shadow-lg`} />
        <span className="text-sm text-subtext flex-1 transition-all duration-300">
          {t(label)}
        </span>
        <span className="text-base font-mono text-text tabular-nums">
          {formatCallDuration(callDurationSeconds)}
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Central orb */}
      <div className="relative mb-8">
        {/* Outer glow ring 2 */}
        <div
          className={`absolute rounded-full border ${ringColor} transition-all duration-300`}
          style={{
            width: 180,
            height: 180,
            top: -30,
            left: -30,
            opacity: 0.08 + audioLevel * 0.06,
            transform: `scale(${1 + audioLevel * 0.15})`,
          }}
        />
        {/* Outer glow ring 1 */}
        <div
          className={`absolute rounded-full border-2 ${ringColor} transition-all duration-300`}
          style={{
            width: 160,
            height: 160,
            top: -20,
            left: -20,
            opacity: isActive ? 0.15 + audioLevel * 0.15 : 0,
            transform: isActive ? `scale(${1 + audioLevel * 0.25})` : "scale(1)",
          }}
        />
        {/* Main orb */}
        <div
          className={`w-[120px] h-[120px] rounded-full border-4 ${ringColor} shadow-lg flex items-center justify-center transition-all duration-150`}
          style={{ transform: `scale(${1 + audioLevel * 0.15})` }}
        >
          <Icon
            size={48}
            className={`transition-all duration-300 ${
              voiceState === "recording"
                ? "text-red"
                : voiceState === "speaking"
                ? "text-primary"
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

      {/* Audio visualizer: responsive to audioLevel (recording state) */}
      {voiceState === "recording" && (
        <AudioVisualizerBars audioLevel={audioLevel} barCount={20} />
      )}

      {/* Speaking wave: CSS animation during TTS */}
      {voiceState === "speaking" && (
        <SpeakingWaveBars barCount={16} />
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom controls: mute | end call */}
      <div className="flex items-center justify-center gap-12 mb-12">
        {/* Mute button */}
        <button
          onClick={onToggleMute}
          className="flex flex-col items-center gap-1 focus-ring rounded-full"
        >
          <span
            className={`w-14 h-14 flex items-center justify-center rounded-full transition-colors ${
              isMuted ? "bg-red/20 text-red" : "bg-surface2 text-subtext"
            }`}
          >
            {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
          </span>
          <span className="text-xs text-subtext">
            {t(isMuted ? "voice.unmute" : "voice.mute")}
          </span>
        </button>

        {/* End call (large red circle) */}
        <button
          onClick={onEnd}
          className="flex flex-col items-center gap-1 focus-ring rounded-full"
        >
          <span className="w-18 h-18 flex items-center justify-center rounded-full bg-red text-on-primary shadow-lg">
            <PhoneOff size={28} />
          </span>
          <span className="text-xs text-red">{t("voice.endConversation")}</span>
        </button>
      </div>
    </div>
  );
}
