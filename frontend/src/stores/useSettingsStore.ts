import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Theme, Language, TTSVoice } from "@/lib/types";

interface SettingsState {
  theme: Theme;
  language: Language;
  voiceLang: Language;
  // TTS
  ttsEnabled: boolean;
  ttsAutoPlay: boolean;
  ttsVoice: TTSVoice;

  setTheme: (theme: Theme) => void;
  setLanguage: (lang: Language) => void;
  setVoiceLang: (lang: Language) => void;
  setTtsEnabled: (val: boolean) => void;
  setTtsAutoPlay: (val: boolean) => void;
  setTtsVoice: (voice: TTSVoice) => void;
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
    }),
    {
      name: "rain-settings",
      version: 2,
      migrate: (persisted, version) => {
        if (version < 2) {
          const state = persisted as Record<string, unknown>;
          if (state.theme === "ocean") state.theme = "dark";
        }
        return persisted as SettingsState;
      },
    }
  )
);
