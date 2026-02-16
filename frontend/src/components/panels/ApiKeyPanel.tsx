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

  // One-time migration: move API key from localStorage to sessionStorage
  useEffect(() => {
    const legacyKey = localStorage.getItem(STORAGE_KEY);
    if (legacyKey) {
      sessionStorage.setItem(STORAGE_KEY, legacyKey);
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      setSavedKey(stored);
      setApiKey(stored);
    }
  }, []);

  const handleConnect = () => {
    const key = apiKey.trim();
    if (!key) return;
    sessionStorage.setItem(STORAGE_KEY, key);
    send({ type: "set_api_key", key });
    setUsingApiKey(true);
    setActivePanel("fileBrowser");
  };

  const handleSkip = () => {
    setActivePanel("fileBrowser");
  };

  const handleClearKey = () => {
    sessionStorage.removeItem(STORAGE_KEY);
    setSavedKey(null);
    setApiKey("");
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-[420px] flex flex-col items-center gap-6 p-8 bg-surface rounded-xl shadow-lg">
        <h2 className="text-2xl font-bold text-text">
          {t("apiKey.title")}
        </h2>

        <p className="text-sm text-text2 text-center">
          {t("apiKey.instruction")}{" "}
          <a
            href="https://console.anthropic.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            console.anthropic.com
          </a>
        </p>

        <div className="w-full relative">
          <input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-ant-..."
            className="w-full bg-surface2 border border-overlay rounded-lg px-4 py-3 pr-16 text-text font-[family-name:var(--font-jetbrains)] text-sm placeholder:text-subtext focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-xs text-text2 hover:text-primary transition-colors"
          >
            {showKey ? t("apiKey.hide") : t("apiKey.show")}
          </button>
        </div>

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

        <button
          onClick={handleConnect}
          disabled={!apiKey.trim()}
          className="w-full py-3 rounded-lg text-sm font-semibold bg-primary text-on-primary transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-dark shadow-sm"
        >
          {t("apiKey.connect")}
        </button>

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
