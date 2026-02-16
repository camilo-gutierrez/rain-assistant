import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Theme, Language } from "@/lib/types";

interface SettingsState {
  theme: Theme;
  language: Language;
  voiceLang: Language;
  setTheme: (theme: Theme) => void;
  setLanguage: (lang: Language) => void;
  setVoiceLang: (lang: Language) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: "dark" as Theme,
      language: "es" as Language,
      voiceLang: "es" as Language,

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
    }),
    {
      name: "rain-settings",
    }
  )
);
