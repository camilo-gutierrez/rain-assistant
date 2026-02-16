"use client";

import { useState, useEffect } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";

const STORAGE_KEY = "rain-api-key";

export default function ApiKeyPanel() {
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [savedKey, setSavedKey] = useState<string | null>(null);

  const send = useConnectionStore((s) => s.send);
  const setUsingApiKey = useConnectionStore((s) => s.setUsingApiKey);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const { t } = useTranslation();

  // Load saved key on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setSavedKey(stored);
      setApiKey(stored);
    }
  }, []);

  const handleConnect = () => {
    const key = apiKey.trim();
    if (!key) return;

    // Save the key for future sessions
    localStorage.setItem(STORAGE_KEY, key);

    // Send key to server via WS
    send({ type: "set_api_key", key });
    setUsingApiKey(true);
    setActivePanel("fileBrowser");
  };

  const handleSkip = () => {
    setActivePanel("fileBrowser");
  };

  const handleClearKey = () => {
    localStorage.removeItem(STORAGE_KEY);
    setSavedKey(null);
    setApiKey("");
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-[420px] flex flex-col items-center gap-6 p-8 bg-surface rounded-2xl border border-overlay">
        {/* Title */}
        <h2
          className="font-[family-name:var(--font-orbitron)] text-2xl font-bold bg-clip-text text-transparent"
          style={{
            backgroundImage: "linear-gradient(135deg, var(--cyan), var(--magenta))",
          }}
        >
          {t("apiKey.title")}
        </h2>

        {/* Instruction */}
        <p className="text-sm text-text2 text-center">
          {t("apiKey.instruction")}{" "}
          <a
            href="https://console.anthropic.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-cyan hover:underline"
          >
            console.anthropic.com
          </a>
        </p>

        {/* API key input with show/hide */}
        <div className="w-full relative">
          <input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-ant-..."
            className="w-full bg-surface2 border border-overlay rounded-lg px-4 py-3 pr-16 text-text font-[family-name:var(--font-jetbrains)] text-sm placeholder:text-subtext focus:outline-none focus:border-cyan focus:shadow-[0_0_12px_var(--neon-glow)] transition-all"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-xs text-text2 hover:text-cyan transition-colors"
          >
            {showKey ? t("apiKey.hide") : t("apiKey.show")}
          </button>
        </div>

        {/* Saved key info */}
        {savedKey && (
          <div className="flex items-center gap-2 text-xs text-text2">
            <span>{t("apiKey.savedInfo")}</span>
            <button
              onClick={handleClearKey}
              className="text-red hover:underline"
            >
              {t("apiKey.clear")}
            </button>
          </div>
        )}

        {/* Connect button */}
        <button
          onClick={handleConnect}
          disabled={!apiKey.trim()}
          className="w-full py-3 rounded-lg font-[family-name:var(--font-orbitron)] text-sm font-bold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-[0_0_20px_var(--neon-glow)]"
          style={{
            background: "linear-gradient(135deg, var(--cyan), var(--mauve))",
          }}
        >
          {t("apiKey.connect")}
        </button>

        {/* Skip button */}
        <button
          onClick={handleSkip}
          className="text-sm text-subtext hover:text-text2 transition-colors"
        >
          {t("apiKey.skip")}
        </button>
      </div>
    </div>
  );
}
