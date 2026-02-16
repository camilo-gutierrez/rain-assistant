"use client";

import { useRef, useCallback } from "react";
import { create } from "zustand";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { synthesize } from "@/lib/api";
import type { TTSPlaybackState } from "@/lib/types";

// ---------------------------------------------------------------------------
// TTS playback store (lightweight, not persisted)
// ---------------------------------------------------------------------------

interface TTSState {
  playbackState: TTSPlaybackState;
  playingMessageId: string | null;
  setPlaybackState: (state: TTSPlaybackState) => void;
  setPlayingMessageId: (id: string | null) => void;
}

export const useTTSStore = create<TTSState>()((set) => ({
  playbackState: "idle",
  playingMessageId: null,
  setPlaybackState: (playbackState) => set({ playbackState }),
  setPlayingMessageId: (playingMessageId) => set({ playingMessageId }),
}));

// ---------------------------------------------------------------------------
// TTS playback hook
// ---------------------------------------------------------------------------

export function useTTS() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
    useTTSStore.getState().setPlaybackState("idle");
    useTTSStore.getState().setPlayingMessageId(null);
  }, []);

  const play = useCallback(
    async (text: string, messageId: string) => {
      const { ttsEnabled, ttsVoice } = useSettingsStore.getState();
      if (!ttsEnabled) return;

      const ttsStore = useTTSStore.getState();

      // Toggle: if already playing this message, stop it
      if (
        ttsStore.playingMessageId === messageId &&
        ttsStore.playbackState === "playing"
      ) {
        stop();
        return;
      }

      // Stop any current playback first
      stop();

      ttsStore.setPlaybackState("loading");
      ttsStore.setPlayingMessageId(messageId);

      try {
        const authToken = useConnectionStore.getState().authToken;
        const blob = await synthesize(text, ttsVoice, "+0%", authToken);

        if (!blob) {
          // Nothing to synthesize (e.g. code-heavy response)
          ttsStore.setPlaybackState("idle");
          ttsStore.setPlayingMessageId(null);
          return;
        }

        const url = URL.createObjectURL(blob);
        blobUrlRef.current = url;

        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onplay = () => {
          useTTSStore.getState().setPlaybackState("playing");
        };

        audio.onended = () => {
          stop();
        };

        audio.onerror = () => {
          console.error("TTS audio playback error");
          stop();
        };

        await audio.play();
      } catch (err) {
        console.error("TTS synthesis failed:", err);
        stop();
      }
    },
    [stop]
  );

  return { play, stop };
}
