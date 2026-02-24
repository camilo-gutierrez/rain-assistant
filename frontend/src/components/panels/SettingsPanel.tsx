"use client";

import { useState, useEffect, useCallback } from "react";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useTranslation } from "@/hooks/useTranslation";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { fetchDevices, revokeDevice, renameDevice } from "@/lib/api";
import { getDeviceId } from "@/lib/device";
import { Globe, Palette, Mic, Volume2, ChevronDown, Sun, Moon, Check, Radio, Monitor, Smartphone, Trash2, Pencil } from "lucide-react";
import type { Theme, Language, TTSVoice, VoiceMode, DeviceInfo } from "@/lib/types";

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

/* ──────────────────────── Devices Section ──────────────────────── */

function DevicesSection() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [maxDevices, setMaxDevices] = useState(2);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [confirmRevokeId, setConfirmRevokeId] = useState<string | null>(null);
  const myDeviceId = typeof window !== "undefined" ? getDeviceId() : "";

  const loadDevices = useCallback(async () => {
    try {
      const res = await fetchDevices(authToken);
      setDevices(res.devices);
      setMaxDevices(res.max_devices);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => { loadDevices(); }, [loadDevices]);

  const handleRevoke = async (deviceId: string) => {
    if (confirmRevokeId !== deviceId) {
      setConfirmRevokeId(deviceId);
      return;
    }
    try {
      await revokeDevice(deviceId, authToken);
      setDevices((prev) => prev.filter((d) => d.device_id !== deviceId));
    } catch {
      // ignore
    }
    setConfirmRevokeId(null);
  };

  const handleRename = async (deviceId: string) => {
    const sanitizedName = editName.trim().replace(/[<>&"'`]/g, '').slice(0, 100);
    if (!sanitizedName) return;
    try {
      await renameDevice(deviceId, sanitizedName, authToken);
      setDevices((prev) =>
        prev.map((d) => (d.device_id === deviceId ? { ...d, device_name: sanitizedName } : d))
      );
    } catch {
      // ignore
    }
    setEditingId(null);
    setEditName("");
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    const now = Date.now();
    const diffMin = Math.floor((now - d.getTime()) / 60000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return d.toLocaleDateString();
  };

  if (loading) {
    return (
      <section className="rounded-xl bg-surface2/50 p-4">
        <SectionHeader icon={<Monitor size={18} />} label={t("devices.title")} />
        <p className="text-sm text-text2">{t("devices.loading")}</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl bg-surface2/50 p-4">
      <SectionHeader icon={<Monitor size={18} />} label={t("devices.title")} />
      <p className="text-xs text-text2 mb-3">
        {t("devices.count", { n: devices.length, max: maxDevices })}
      </p>
      {devices.length === 0 ? (
        <p className="text-sm text-text2">{t("devices.noDevices")}</p>
      ) : (
        <div className="space-y-2">
          {devices.map((device) => {
            const isCurrent = device.device_id === myDeviceId || device.is_current;
            const isMobile = /mobile|android|telegram/i.test(device.device_name);
            return (
              <div
                key={device.device_id || device.created_at}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                  isCurrent
                    ? "border-primary/30 bg-primary/5"
                    : "border-overlay bg-surface"
                }`}
              >
                <span className="text-text2 shrink-0">
                  {isMobile ? <Smartphone size={18} /> : <Monitor size={18} />}
                </span>
                <div className="flex-1 min-w-0">
                  {editingId === device.device_id ? (
                    <form
                      className="flex gap-2"
                      onSubmit={(e) => { e.preventDefault(); handleRename(device.device_id); }}
                    >
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        maxLength={100}
                        autoFocus
                        className="flex-1 text-sm bg-surface2 border border-overlay rounded px-2 py-1 text-text focus-ring"
                      />
                      <button
                        type="submit"
                        className="text-xs text-primary font-medium px-2 py-1 rounded hover:bg-primary/10"
                      >
                        OK
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="text-xs text-text2 px-2 py-1 rounded hover:bg-overlay"
                      >
                        &times;
                      </button>
                    </form>
                  ) : (
                    <>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-text truncate">
                          {device.device_name || "Unknown"}
                        </span>
                        {isCurrent && (
                          <span className="text-xs font-semibold uppercase px-1.5 py-0.5 rounded-full bg-primary/15 text-primary">
                            {t("devices.thisDevice")}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-text2 mt-0.5">
                        <span>{device.client_ip}</span>
                        <span>·</span>
                        <span>{formatTime(device.last_activity)}</span>
                      </div>
                    </>
                  )}
                </div>
                {!isCurrent && editingId !== device.device_id && (
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => { setEditingId(device.device_id); setEditName(device.device_name); }}
                      className="p-1.5 rounded-lg text-text2 hover:text-text hover:bg-overlay transition-colors"
                      title={t("devices.rename")}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleRevoke(device.device_id)}
                      className={`p-1.5 rounded-lg transition-colors ${
                        confirmRevokeId === device.device_id
                          ? "text-red bg-red/10"
                          : "text-text2 hover:text-red hover:bg-red/10"
                      }`}
                      title={confirmRevokeId === device.device_id ? t("devices.revokeConfirm") : t("devices.revoke")}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

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
  const voiceMode = useSettingsStore((s) => s.voiceMode);
  const vadSensitivity = useSettingsStore((s) => s.vadSensitivity);
  const silenceTimeout = useSettingsStore((s) => s.silenceTimeout);
  const setVoiceMode = useSettingsStore((s) => s.setVoiceMode);
  const setVadSensitivity = useSettingsStore((s) => s.setVadSensitivity);
  const setSilenceTimeout = useSettingsStore((s) => s.setSilenceTimeout);
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

  const voiceModeOptions = [
    { value: "push-to-talk", label: t("settings.voiceMode.pushToTalk") },
    { value: "vad", label: t("settings.voiceMode.vad") },
    { value: "talk-mode", label: t("settings.voiceMode.talkMode") },
    { value: "wake-word", label: t("settings.voiceMode.wakeWord") },
  ];

  const voiceOptions = [
    { value: "es-MX-DaliaNeural", label: t("settings.ttsVoice.esFemale") },
    { value: "es-MX-JorgeNeural", label: t("settings.ttsVoice.esMale") },
    { value: "en-US-JennyNeural", label: t("settings.ttsVoice.enFemale") },
    { value: "en-US-GuyNeural", label: t("settings.ttsVoice.enMale") },
  ];

  return (
    <div className="p-5 space-y-3 overflow-y-auto">
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

      {/* ── Voice Mode ── */}
      <section className="rounded-xl bg-surface2/50 p-4">
        <SectionHeader icon={<Radio size={18} />} label={t("settings.voiceMode")} />
        <div className="space-y-3">
          <SelectField
            value={voiceMode}
            onChange={(v) => setVoiceMode(v as VoiceMode)}
            options={voiceModeOptions}
          />
          {voiceMode !== "push-to-talk" && (
            <div className="space-y-3 pt-1 animate-fade-in">
              <div>
                <label className="text-xs text-subtext mb-1 block">
                  {t("settings.vadSensitivity")}: {vadSensitivity.toFixed(1)}
                </label>
                <input
                  type="range"
                  min="0.3"
                  max="0.9"
                  step="0.1"
                  value={vadSensitivity}
                  onChange={(e) => setVadSensitivity(parseFloat(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
              <div>
                <label className="text-xs text-subtext mb-1 block">
                  {t("settings.silenceTimeout")}: {silenceTimeout}ms
                </label>
                <input
                  type="range"
                  min="400"
                  max="2000"
                  step="100"
                  value={silenceTimeout}
                  onChange={(e) => setSilenceTimeout(parseInt(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
            </div>
          )}
        </div>
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

      {/* ── Devices ── */}
      <DevicesSection />
    </div>
  );
}
