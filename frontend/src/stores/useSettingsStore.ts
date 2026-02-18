import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Theme, Language, TTSVoice, AIProvider } from "@/lib/types";

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

  setTheme: (theme: Theme) => void;
  setLanguage: (lang: Language) => void;
  setVoiceLang: (lang: Language) => void;
  setTtsEnabled: (val: boolean) => void;
  setTtsAutoPlay: (val: boolean) => void;
  setTtsVoice: (voice: TTSVoice) => void;
  setAIProvider: (provider: AIProvider) => void;
  setAIModel: (model: string) => void;
  setActiveEgoId: (id: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: "light" as Theme,
      language: "es" as Language,
      voiceLang: "es" as Language,
      ttsEnabled: false,
      ttsAutoPlay: false,
      ttsVoice: "es-MX-DaliaNeural" as TTSVoice,
      aiProvider: "claude" as AIProvider,
      aiModel: "auto",
      activeEgoId: "rain",

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
    }),
    {
      name: "rain-settings",
      version: 4,
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
        return persisted as SettingsState;
      },
    }
  )
);
