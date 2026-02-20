"use client";

/**
 * useVoiceMode — Central voice orchestration hook.
 *
 * Manages voice modes (push-to-talk, VAD, talk-mode, wake-word),
 * captures PCM audio from the microphone, streams chunks to the
 * backend via WebSocket, and reacts to VAD / wake-word / transcription
 * events coming back from the server.
 *
 * Usage: call once in page.tsx (or ChatPanel) alongside useWebSocket.
 */

import { useEffect, useRef, useCallback } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { create } from "zustand";
import type { VoiceState, VoiceMode } from "@/lib/types";

// ---------------------------------------------------------------------------
// Voice state store (global, consumed by VoiceModeIndicator & TalkModeOverlay)
// ---------------------------------------------------------------------------

interface VoiceModeState {
  voiceState: VoiceState;
  partialTranscription: string;
  lastTranscription: string;
  wakeWordConfidence: number;
  setVoiceState: (s: VoiceState) => void;
  setPartialTranscription: (t: string) => void;
  setLastTranscription: (t: string) => void;
  setWakeWordConfidence: (c: number) => void;
  reset: () => void;
}

export const useVoiceModeStore = create<VoiceModeState>()((set) => ({
  voiceState: "idle",
  partialTranscription: "",
  lastTranscription: "",
  wakeWordConfidence: 0,
  setVoiceState: (voiceState) => set({ voiceState }),
  setPartialTranscription: (partialTranscription) => set({ partialTranscription }),
  setLastTranscription: (lastTranscription) => set({ lastTranscription }),
  setWakeWordConfidence: (wakeWordConfidence) => set({ wakeWordConfidence }),
  reset: () =>
    set({
      voiceState: "idle",
      partialTranscription: "",
      lastTranscription: "",
      wakeWordConfidence: 0,
    }),
}));

// ---------------------------------------------------------------------------
// Audio capture constants
// ---------------------------------------------------------------------------

const SAMPLE_RATE = 16000;
const CHUNK_DURATION_MS = 96; // ~3 VAD frames (32ms each) per WebSocket message
const CHUNK_SAMPLES = Math.floor(SAMPLE_RATE * (CHUNK_DURATION_MS / 1000)); // 1536

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useVoiceMode() {
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const activeRef = useRef(false);

  const send = useConnectionStore((s) => s.send);
  const voiceMode = useSettingsStore((s) => s.voiceMode);
  const vadSensitivity = useSettingsStore((s) => s.vadSensitivity);
  const silenceTimeout = useSettingsStore((s) => s.silenceTimeout);

  // ── Start capturing audio and streaming chunks to backend ──

  const startCapture = useCallback(async (agentId: string) => {
    if (activeRef.current) return;
    activeRef.current = true;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: SAMPLE_RATE,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);

      // Use ScriptProcessorNode (widely supported) for PCM capture
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      workletNodeRef.current = processor;

      // Accumulation buffer for consistent chunk sizes
      let accumulator = new Float32Array(0);

      processor.onaudioprocess = (e) => {
        if (!activeRef.current) return;

        const input = e.inputBuffer.getChannelData(0);

        // Append to accumulator
        const combined = new Float32Array(accumulator.length + input.length);
        combined.set(accumulator);
        combined.set(input, accumulator.length);
        accumulator = combined;

        // Send complete chunks
        while (accumulator.length >= CHUNK_SAMPLES) {
          const chunk = accumulator.slice(0, CHUNK_SAMPLES);
          accumulator = accumulator.slice(CHUNK_SAMPLES);

          // Convert float32 → int16 PCM → base64
          const pcm16 = new Int16Array(chunk.length);
          for (let i = 0; i < chunk.length; i++) {
            const s = Math.max(-1, Math.min(1, chunk[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }

          const bytes = new Uint8Array(pcm16.buffer);
          const base64 = btoa(String.fromCharCode(...bytes));

          send({ type: "audio_chunk", data: base64, agent_id: agentId });
        }
      };

      source.connect(processor);
      processor.connect(ctx.destination); // required for onaudioprocess to fire

    } catch (err) {
      console.error("useVoiceMode: mic access failed", err);
      activeRef.current = false;
    }
  }, [send]);

  // ── Stop capturing ──

  const stopCapture = useCallback(() => {
    activeRef.current = false;

    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    useVoiceModeStore.getState().reset();
  }, []);

  // ── Activate voice mode for current agent ──

  const activate = useCallback(
    (agentId: string) => {
      send({
        type: "voice_mode_set",
        mode: voiceMode,
        agent_id: agentId,
        vad_threshold: vadSensitivity,
        silence_timeout: silenceTimeout,
      });

      if (voiceMode === "talk-mode") {
        send({ type: "talk_mode_start", agent_id: agentId });
      }

      startCapture(agentId);

      const initialState: VoiceState =
        voiceMode === "wake-word" ? "wake_listening" : "listening";
      useVoiceModeStore.getState().setVoiceState(initialState);
    },
    [voiceMode, vadSensitivity, silenceTimeout, send, startCapture]
  );

  // ── Deactivate ──

  const deactivate = useCallback(
    (agentId: string) => {
      send({ type: "voice_mode_set", mode: "push-to-talk", agent_id: agentId });
      send({ type: "talk_mode_stop", agent_id: agentId });
      stopCapture();
    },
    [send, stopCapture]
  );

  // ── Interrupt (user speaks during TTS) ──

  const interrupt = useCallback(
    (agentId: string) => {
      send({ type: "talk_interruption", agent_id: agentId });
    },
    [send]
  );

  // ── Handle voice-related WS messages ──

  useEffect(() => {
    const ws = useConnectionStore.getState().ws;
    if (!ws) return;

    const handleMessage = (e: MessageEvent) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }

      const store = useVoiceModeStore.getState();
      const agentStore = useAgentStore.getState();

      switch (msg.type) {
        case "vad_event":
          if (msg.event === "speech_start") {
            store.setVoiceState("recording");
          } else if (msg.event === "speech_end") {
            store.setVoiceState("transcribing");
          } else if (msg.event === "no_speech") {
            store.setVoiceState("listening");
          }
          break;

        case "wake_word_detected":
          store.setWakeWordConfidence(msg.confidence);
          store.setVoiceState("listening");
          break;

        case "talk_state_changed":
          store.setVoiceState(msg.state);
          break;

        case "voice_transcription":
          if (msg.is_final && msg.text) {
            store.setLastTranscription(msg.text);
            store.setPartialTranscription("");
            // Auto-send as user message
            const activeAgentId = msg.agent_id || agentStore.activeAgentId;
            if (activeAgentId) {
              agentStore.appendMessage(activeAgentId, {
                id: `voice-${Date.now()}`,
                type: "user",
                text: msg.text,
                timestamp: Date.now(),
                animate: false,
              });
              useConnectionStore.getState().send({
                type: "send_message",
                text: msg.text,
                agent_id: activeAgentId,
              });
              agentStore.setAgentStatus(activeAgentId, "working");
              store.setVoiceState("processing");
            }
          }
          break;

        case "partial_transcription":
          store.setPartialTranscription(msg.text);
          if (msg.is_final) {
            store.setLastTranscription(msg.text);
            store.setPartialTranscription("");
          }
          break;

        case "voice_mode_changed":
          // Server confirmed mode change
          break;
      }
    };

    ws.addEventListener("message", handleMessage);
    return () => ws.removeEventListener("message", handleMessage);
  }, []);

  // ── Cleanup on unmount ──
  useEffect(() => {
    return () => {
      stopCapture();
    };
  }, [stopCapture]);

  return {
    activate,
    deactivate,
    stopCapture,
    interrupt,
    isActive: activeRef.current,
  };
}
