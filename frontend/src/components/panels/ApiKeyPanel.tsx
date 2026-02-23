"use client";

import { useState, useEffect } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useUIStore } from "@/stores/useUIStore";
import { useToastStore } from "@/stores/useToastStore";
import { useTranslation } from "@/hooks/useTranslation";
import {
  PROVIDER_INFO,
  PROVIDER_MODELS,
  type AIProvider,
} from "@/lib/types";
import { Eye, EyeOff, Key } from "lucide-react";

const PROVIDERS: AIProvider[] = ["claude", "openai", "gemini", "ollama"];

export default function ApiKeyPanel() {
  const { t } = useTranslation();

  const send = useConnectionStore((s) => s.send);
  const setUsingApiKey = useConnectionStore((s) => s.setUsingApiKey);
  const setCurrentProvider = useConnectionStore((s) => s.setCurrentProvider);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const addToast = useToastStore((s) => s.addToast);

  const aiProvider = useSettingsStore((s) => s.aiProvider);
  const aiModel = useSettingsStore((s) => s.aiModel);
  const setAIProvider = useSettingsStore((s) => s.setAIProvider);
  const setAIModel = useSettingsStore((s) => s.setAIModel);
  const providerKeys = useSettingsStore((s) => s.providerKeys);
  const setProviderKey = useSettingsStore((s) => s.setProviderKey);
  const clearProviderKey = useSettingsStore((s) => s.clearProviderKey);

  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [savedKey, setSavedKey] = useState<string | null>(null);

  const info = PROVIDER_INFO[aiProvider];
  const models = PROVIDER_MODELS[aiProvider];

  // Load saved key when provider changes
  useEffect(() => {
    const stored = providerKeys[aiProvider] || null;
    if (stored) {
      setSavedKey(stored);
      setApiKey(stored);
    } else {
      setSavedKey(null);
      setApiKey("");
    }
    setShowKey(false);
  }, [aiProvider, providerKeys]);

  // Ensure model is valid for current provider
  useEffect(() => {
    const validIds = models.map((m) => m.id);
    if (!validIds.includes(aiModel)) {
      setAIModel(models[0].id);
    }
  }, [aiProvider, aiModel, models, setAIModel]);

  const handleProviderChange = (provider: AIProvider) => {
    setAIProvider(provider);
    const firstModel = PROVIDER_MODELS[provider][0].id;
    setAIModel(firstModel);
  };

  const isOllama = aiProvider === "ollama";

  const handleConnect = () => {
    const key = apiKey.trim();
    // For Ollama, empty key is valid (defaults to localhost:11434)
    if (!key && !isOllama) return;
    const effectiveKey = key || (isOllama ? "http://localhost:11434" : "");
    if (!effectiveKey) return;
    setProviderKey(aiProvider, effectiveKey);
    send({ type: "set_api_key", key: effectiveKey, provider: aiProvider, model: aiModel });
    setUsingApiKey(true);
    setCurrentProvider(aiProvider);
    addToast({ type: "success", message: t("toast.connectSuccess") });
    setActivePanel("fileBrowser");
  };

  const handleSkip = () => {
    setActivePanel("fileBrowser");
  };

  const handleClearKey = () => {
    clearProviderKey(aiProvider);
    setSavedKey(null);
    setApiKey("");
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-[460px] flex flex-col items-center gap-5 p-8 bg-surface rounded-xl shadow-lg">
        <h2 className="text-2xl font-bold text-text flex items-center gap-2.5">
          <Key className="w-6 h-6 text-primary" />
          {t("apiKey.title")}
        </h2>

        {/* Provider selector */}
        <div className="w-full flex gap-1 p-1 bg-surface2 rounded-lg">
          {PROVIDERS.map((p) => (
            <button
              key={p}
              onClick={() => handleProviderChange(p)}
              className={`flex-1 min-h-[44px] py-2 px-3 rounded-md text-sm font-medium transition-all focus-ring ${
                aiProvider === p
                  ? "bg-primary text-on-primary shadow-sm"
                  : "text-text2 hover:text-text hover:bg-overlay/50"
              }`}
            >
              {PROVIDER_INFO[p].name}
            </button>
          ))}
        </div>

        {/* Model selector */}
        {models.length > 1 && (
          <div className="w-full">
            <label className="block text-xs text-text2 mb-1.5">
              {t("provider.model")}
            </label>
            <select
              value={aiModel}
              onChange={(e) => setAIModel(e.target.value)}
              className="w-full bg-surface2 border border-overlay rounded-lg px-4 py-2.5 text-text text-sm focus-ring transition-all"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Instruction */}
        <p className="text-sm text-text2 text-center">
          {t("apiKey.instructionGeneric", { provider: info.name })}{" "}
          <a
            href={info.consoleUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline focus-ring rounded"
          >
            {info.consoleName}
          </a>
        </p>

        {/* API key input */}
        <div className="w-full relative">
          <input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={info.keyPlaceholder}
            onKeyDown={(e) => e.key === "Enter" && handleConnect()}
            className="w-full bg-surface2 border border-overlay rounded-lg px-4 py-3 pr-12 text-text font-[family-name:var(--font-jetbrains)] text-sm placeholder:text-subtext focus-ring transition-all"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-text2 hover:text-primary transition-colors focus-ring rounded-md"
          >
            {showKey ? (
              <EyeOff className="w-[18px] h-[18px]" />
            ) : (
              <Eye className="w-[18px] h-[18px]" />
            )}
          </button>
        </div>

        {savedKey && (
          <div className="flex items-center gap-2 text-xs text-text2">
            <span>{t("apiKey.savedInfo")}</span>
            <button
              onClick={handleClearKey}
              className="text-red hover:underline focus-ring rounded"
            >
              {t("apiKey.clear")}
            </button>
          </div>
        )}

        <button
          onClick={handleConnect}
          disabled={!apiKey.trim() && !isOllama}
          className="w-full min-h-[44px] py-3 rounded-lg text-sm font-semibold bg-primary text-on-primary transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-dark shadow-sm focus-ring"
        >
          {t("apiKey.connect")}
        </button>

        <button
          onClick={handleSkip}
          className="text-sm text-subtext hover:text-text2 transition-colors focus-ring rounded-md px-3 py-1.5"
        >
          {t("apiKey.skip")}
        </button>
      </div>
    </div>
  );
}
