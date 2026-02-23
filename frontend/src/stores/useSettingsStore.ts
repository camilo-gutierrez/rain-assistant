import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Theme, Language, TTSVoice, AIProvider, VoiceMode } from "@/lib/types";

interface SettingsState {
  theme: Theme;
  language: Language;
  voiceLang: Language;
  // TTS
  ttsEnabled: boolean;
  ttsAutoPlay: boolean;
  ttsVoice: TTSVoice;
  // AI Provider
  aiProvider: AIProvider;
  aiModel: string;
  // Alter Ego
  activeEgoId: string;
  // Voice
  voiceMode: VoiceMode;
  vadSensitivity: number;
  silenceTimeout: number;
  // API keys — memory-only, never persisted (security: not in storage)
  providerKeys: Record<string, string>;

  setTheme: (theme: Theme) => void;
  setLanguage: (lang: Language) => void;
  setVoiceLang: (lang: Language) => void;
  setTtsEnabled: (val: boolean) => void;
  setTtsAutoPlay: (val: boolean) => void;
  setTtsVoice: (voice: TTSVoice) => void;
  setAIProvider: (provider: AIProvider) => void;
  setAIModel: (model: string) => void;
  setActiveEgoId: (id: string) => void;
  setVoiceMode: (mode: VoiceMode) => void;
  setVadSensitivity: (val: number) => void;
  setSilenceTimeout: (val: number) => void;
  setProviderKey: (provider: AIProvider, key: string) => void;
  clearProviderKey: (provider: AIProvider) => void;
  getProviderKey: (provider: AIProvider) => string | null;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      theme: "light" as Theme,
      language: "es" as Language,
      voiceLang: "es" as Language,
      ttsEnabled: false,
      ttsAutoPlay: false,
      ttsVoice: "es-MX-DaliaNeural" as TTSVoice,
      aiProvider: "claude" as AIProvider,
      aiModel: "auto",
      activeEgoId: "rain",
      voiceMode: "push-to-talk" as VoiceMode,
      vadSensitivity: 0.5,
      silenceTimeout: 800,
      providerKeys: {} as Record<string, string>,

      setTheme: (theme) => {
        if (typeof document !== "undefined") {
          document.documentElement.setAttribute("data-theme", theme);
        }
        set({ theme });
      },

      setLanguage: (language) => {
        if (typeof document !== "undefined") {
          document.documentElement.setAttribute("lang", language);
        }
        set({ language });
      },

      setVoiceLang: (voiceLang) => set({ voiceLang }),
      setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
      setTtsAutoPlay: (ttsAutoPlay) => set({ ttsAutoPlay }),
      setTtsVoice: (ttsVoice) => set({ ttsVoice }),
      setAIProvider: (aiProvider) => set({ aiProvider }),
      setAIModel: (aiModel) => set({ aiModel }),
      setActiveEgoId: (activeEgoId) => set({ activeEgoId }),
      setVoiceMode: (voiceMode) => set({ voiceMode }),
      setVadSensitivity: (vadSensitivity) => set({ vadSensitivity }),
      setSilenceTimeout: (silenceTimeout) => set({ silenceTimeout }),
      setProviderKey: (provider, key) =>
        set({ providerKeys: { ...get().providerKeys, [provider]: key } }),
      clearProviderKey: (provider) => {
        const { [provider]: _, ...rest } = get().providerKeys;
        set({ providerKeys: rest });
      },
      getProviderKey: (provider) => get().providerKeys[provider] || null,
    }),
    {
      name: "rain-settings",
      version: 5,
      partialize: (state) => {
        // Exclude providerKeys from persistence — they must stay memory-only
        const { providerKeys: _, ...rest } = state;
        return rest;
      },
      migrate: (persisted, version) => {
        const state = persisted as Record<string, unknown>;
        if (version < 2) {
          if (state.theme === "ocean") state.theme = "dark";
        }
        if (version < 3) {
          state.aiProvider = state.aiProvider ?? "claude";
          state.aiModel = state.aiModel ?? "auto";
        }
        if (version < 4) {
          state.activeEgoId = state.activeEgoId ?? "rain";
        }
        if (version < 5) {
          state.voiceMode = state.voiceMode ?? "push-to-talk";
          state.vadSensitivity = state.vadSensitivity ?? 0.5;
          state.silenceTimeout = state.silenceTimeout ?? 800;
        }
        return persisted as SettingsState;
      },
    }
  )
);
