"use client";

import { useSettingsStore } from "@/stores/useSettingsStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { useConnectionStore } from "@/stores/useConnectionStore";
import type { Theme, Language } from "@/lib/types";

interface ThemeOption {
  id: Theme;
  labelKey: string;
  preview: string;
}

const themes: ThemeOption[] = [
  { id: "dark", labelKey: "settings.theme.dark", preview: "#0a0a14" },
  { id: "light", labelKey: "settings.theme.light", preview: "#e8eaf0" },
  { id: "ocean", labelKey: "settings.theme.ocean", preview: "#0a1628" },
];

export default function SettingsPanel() {
  const theme = useSettingsStore((s) => s.theme);
  const language = useSettingsStore((s) => s.language);
  const voiceLang = useSettingsStore((s) => s.voiceLang);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const setLanguage = useSettingsStore((s) => s.setLanguage);
  const setVoiceLang = useSettingsStore((s) => s.setVoiceLang);
  const toggleSettings = useUIStore((s) => s.toggleSettings);
  const send = useConnectionStore((s) => s.send);
  const { t } = useTranslation();

  const handleVoiceLangChange = (lang: Language) => {
    setVoiceLang(lang);
    send({ type: "set_transcription_lang", lang });
  };

  return (
    <div className="flex-1 flex flex-col overflow-y-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2
          className="font-[family-name:var(--font-orbitron)] text-lg font-bold bg-clip-text text-transparent"
          style={{
            backgroundImage: "linear-gradient(135deg, var(--cyan), var(--magenta))",
          }}
        >
          {t("settings.title")}
        </h2>
        <button
          onClick={toggleSettings}
          className="px-3 py-1 text-xs rounded border border-overlay text-text2 hover:text-cyan hover:border-cyan transition-colors font-[family-name:var(--font-jetbrains)]"
        >
          {t("settings.close")}
        </button>
      </div>

      <div className="max-w-md space-y-8">
        {/* Language selector */}
        <div>
          <label className="block text-sm text-text2 font-[family-name:var(--font-orbitron)] mb-2">
            {t("settings.language")}
          </label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as Language)}
            className="w-full bg-surface2 border border-overlay rounded-lg px-4 py-2.5 text-sm text-text focus:outline-none focus:border-cyan transition-colors cursor-pointer"
          >
            <option value="en">English</option>
            <option value="es">Espa&#241;ol</option>
          </select>
        </div>

        {/* Theme selector */}
        <div>
          <label className="block text-sm text-text2 font-[family-name:var(--font-orbitron)] mb-3">
            {t("settings.theme")}
          </label>
          <div className="flex gap-3">
            {themes.map((opt) => {
              const isActive = theme === opt.id;
              return (
                <button
                  key={opt.id}
                  onClick={() => setTheme(opt.id)}
                  className={`flex-1 flex flex-col items-center gap-2 p-3 rounded-xl border-2 transition-all ${
                    isActive
                      ? "border-cyan shadow-[0_0_16px_var(--neon-glow)]"
                      : "border-overlay hover:border-overlay/80"
                  }`}
                >
                  {/* Preview circle */}
                  <div
                    className={`w-10 h-10 rounded-full border-2 ${
                      isActive ? "border-cyan" : "border-overlay"
                    }`}
                    style={{ background: opt.preview }}
                  />
                  <span
                    className={`text-xs font-[family-name:var(--font-jetbrains)] ${
                      isActive ? "text-cyan" : "text-text2"
                    }`}
                  >
                    {t(opt.labelKey)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Voice language selector */}
        <div>
          <label className="block text-sm text-text2 font-[family-name:var(--font-orbitron)] mb-2">
            {t("settings.voiceLang")}
          </label>
          <select
            value={voiceLang}
            onChange={(e) => handleVoiceLangChange(e.target.value as Language)}
            className="w-full bg-surface2 border border-overlay rounded-lg px-4 py-2.5 text-sm text-text focus:outline-none focus:border-cyan transition-colors cursor-pointer"
          >
            <option value="en">English</option>
            <option value="es">Espa&#241;ol</option>
          </select>
        </div>
      </div>
    </div>
  );
}
