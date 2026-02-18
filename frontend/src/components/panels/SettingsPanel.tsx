"use client";

import { useSettingsStore } from "@/stores/useSettingsStore";
import { useTranslation } from "@/hooks/useTranslation";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { Globe, Palette, Mic, Volume2, ChevronDown, Sun, Moon, Check } from "lucide-react";
import type { Theme, Language, TTSVoice } from "@/lib/types";

/* ──────────────────────── Sub-components ──────────────────────── */

function SectionHeader({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2.5 mb-3">
      <span className="text-primary">{icon}</span>
      <h3 className="text-sm font-semibold text-text tracking-wide uppercase">{label}</h3>
    </div>
  );
}

function Toggle({ enabled, onChange }: { enabled: boolean; onChange: () => void }) {
  return (
    <button
      role="switch"
      aria-checked={enabled}
      onClick={onChange}
      className={`relative w-11 h-6 rounded-full transition-colors duration-200 focus-ring ${
        enabled ? "bg-primary" : "bg-overlay"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-200 ${
          enabled ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function ToggleRow({ label, enabled, onChange }: { label: string; enabled: boolean; onChange: () => void }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-text">{label}</span>
      <Toggle enabled={enabled} onChange={onChange} />
    </div>
  );
}

function SelectField({ value, onChange, options, label }: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  label?: string;
}) {
  return (
    <div>
      {label && (
        <label className="block text-xs font-medium text-text2 mb-1.5">{label}</label>
      )}
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none bg-surface2 border border-overlay rounded-lg px-3.5 py-2.5 pr-9 text-sm text-text focus-ring transition-colors cursor-pointer"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-text2 pointer-events-none" />
      </div>
    </div>
  );
}

/* ──────────────────────── Theme data ──────────────────────── */

interface ThemeOption {
  id: Theme;
  labelKey: string;
  icon: React.ReactNode;
  bg: string;
  surface: string;
  accent: string;
  text: string;
}

const themes: ThemeOption[] = [
  {
    id: "light",
    labelKey: "settings.theme.light",
    icon: <Sun size={20} />,
    bg: "#f5f5f5",
    surface: "#ffffff",
    accent: "#1976d2",
    text: "#212121",
  },
  {
    id: "dark",
    labelKey: "settings.theme.dark",
    icon: <Moon size={20} />,
    bg: "#121212",
    surface: "#1e1e1e",
    accent: "#90caf9",
    text: "#e0e0e0",
  },
];

/* ──────────────────────── Main Component ──────────────────────── */

export default function SettingsPanel() {
  const theme = useSettingsStore((s) => s.theme);
  const language = useSettingsStore((s) => s.language);
  const voiceLang = useSettingsStore((s) => s.voiceLang);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const setLanguage = useSettingsStore((s) => s.setLanguage);
  const setVoiceLang = useSettingsStore((s) => s.setVoiceLang);
  const ttsEnabled = useSettingsStore((s) => s.ttsEnabled);
  const ttsAutoPlay = useSettingsStore((s) => s.ttsAutoPlay);
  const ttsVoice = useSettingsStore((s) => s.ttsVoice);
  const setTtsEnabled = useSettingsStore((s) => s.setTtsEnabled);
  const setTtsAutoPlay = useSettingsStore((s) => s.setTtsAutoPlay);
  const setTtsVoice = useSettingsStore((s) => s.setTtsVoice);
  const send = useConnectionStore((s) => s.send);
  const { t } = useTranslation();

  const handleVoiceLangChange = (lang: string) => {
    setVoiceLang(lang as Language);
    send({ type: "set_transcription_lang", lang });
  };

  const langOptions = [
    { value: "en", label: "English" },
    { value: "es", label: "Espa\u00f1ol" },
  ];

  const voiceOptions = [
    { value: "es-MX-DaliaNeural", label: t("settings.ttsVoice.esFemale") },
    { value: "es-MX-JorgeNeural", label: t("settings.ttsVoice.esMale") },
    { value: "en-US-JennyNeural", label: t("settings.ttsVoice.enFemale") },
    { value: "en-US-GuyNeural", label: t("settings.ttsVoice.enMale") },
  ];

  return (
    <div className="p-5 space-y-1 overflow-y-auto">
      {/* ── Language ── */}
      <section className="rounded-xl bg-surface2/50 p-4">
        <SectionHeader icon={<Globe size={18} />} label={t("settings.language")} />
        <SelectField
          value={language}
          onChange={(v) => setLanguage(v as Language)}
          options={langOptions}
        />
      </section>

      {/* ── Theme ── */}
      <section className="rounded-xl bg-surface2/50 p-4">
        <SectionHeader icon={<Palette size={18} />} label={t("settings.theme")} />
        <div className="grid grid-cols-2 gap-3">
          {themes.map((opt) => {
            const isActive = theme === opt.id;
            return (
              <button
                key={opt.id}
                onClick={() => setTheme(opt.id)}
                className={`group relative flex flex-col items-center gap-2.5 p-4 rounded-xl border-2 transition-all duration-200 focus-ring ${
                  isActive
                    ? "border-primary bg-primary/5 shadow-[0_0_0_1px_rgba(var(--primary-rgb),0.15)]"
                    : "border-transparent bg-surface hover:border-overlay hover:shadow-sm"
                }`}
              >
                {/* Mini UI preview */}
                <div
                  className="w-full aspect-[4/3] rounded-lg overflow-hidden border border-black/10"
                  style={{ background: opt.bg }}
                >
                  {/* Title bar */}
                  <div
                    className="h-2.5 w-full flex items-center gap-1 px-1.5"
                    style={{ background: opt.surface }}
                  >
                    <span className="w-1 h-1 rounded-full" style={{ background: opt.accent }} />
                    <span className="w-1 h-1 rounded-full opacity-40" style={{ background: opt.text }} />
                    <span className="w-1 h-1 rounded-full opacity-40" style={{ background: opt.text }} />
                  </div>
                  {/* Content lines */}
                  <div className="p-1.5 space-y-1">
                    <div className="h-1 w-3/4 rounded-full" style={{ background: opt.accent, opacity: 0.7 }} />
                    <div className="h-1 w-full rounded-full" style={{ background: opt.text, opacity: 0.15 }} />
                    <div className="h-1 w-5/6 rounded-full" style={{ background: opt.text, opacity: 0.15 }} />
                    <div className="h-1 w-2/3 rounded-full" style={{ background: opt.text, opacity: 0.15 }} />
                  </div>
                </div>

                {/* Label + icon */}
                <div className="flex items-center gap-1.5">
                  <span className={`transition-colors ${isActive ? "text-primary" : "text-text2 group-hover:text-text"}`}>
                    {opt.icon}
                  </span>
                  <span className={`text-sm font-medium transition-colors ${isActive ? "text-primary" : "text-text2 group-hover:text-text"}`}>
                    {t(opt.labelKey)}
                  </span>
                </div>

                {/* Active indicator */}
                {isActive && (
                  <span className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                    <Check size={12} className="text-on-primary" strokeWidth={3} />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {/* ── Voice Recognition ── */}
      <section className="rounded-xl bg-surface2/50 p-4">
        <SectionHeader icon={<Mic size={18} />} label={t("settings.voiceLang")} />
        <SelectField
          value={voiceLang}
          onChange={handleVoiceLangChange}
          options={langOptions}
        />
      </section>

      {/* ── Text-to-Speech ── */}
      <section className="rounded-xl bg-surface2/50 p-4">
        <SectionHeader icon={<Volume2 size={18} />} label={t("settings.tts")} />
        <div className="space-y-1">
          <ToggleRow
            label={t("settings.ttsEnabled")}
            enabled={ttsEnabled}
            onChange={() => setTtsEnabled(!ttsEnabled)}
          />

          {ttsEnabled && (
            <div className="space-y-3 pt-1 animate-fade-in">
              <ToggleRow
                label={t("settings.ttsAutoPlay")}
                enabled={ttsAutoPlay}
                onChange={() => setTtsAutoPlay(!ttsAutoPlay)}
              />
              <div className="pt-1">
                <SelectField
                  value={ttsVoice}
                  onChange={(v) => setTtsVoice(v as TTSVoice)}
                  options={voiceOptions}
                  label={t("settings.ttsVoice")}
                />
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
