"use client";

import { useState, useRef, useEffect } from "react";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useMetricsStore } from "@/stores/useMetricsStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import {
  PROVIDER_INFO,
  PROVIDER_MODELS,
  formatModelName,
  type AIProvider,
} from "@/lib/types";
import { ChevronDown, Check } from "lucide-react";

const PROVIDERS: AIProvider[] = ["claude", "openai", "gemini"];

const PROVIDER_COLORS: Record<AIProvider, string> = {
  claude: "bg-[#d97706]",   // amber/orange for Anthropic
  openai: "bg-[#10a37f]",   // OpenAI green
  gemini: "bg-[#4285f4]",   // Google blue
};

function hasStoredKey(provider: AIProvider): boolean {
  if (typeof window === "undefined") return false;
  return !!sessionStorage.getItem(`rain-api-key-${provider}`);
}

function getDisplayModel(
  serverModel: string | null,
  configuredModel: string,
  provider: AIProvider
): string {
  // Prefer the actual model from the server when available
  if (serverModel) return formatModelName(serverModel);
  // Fall back to the configured model's display name
  const modelDef = PROVIDER_MODELS[provider].find((m) => m.id === configuredModel);
  return modelDef?.name ?? configuredModel;
}

export default function ModelSwitcher() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [popoverProvider, setPopoverProvider] = useState<AIProvider | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Stores
  const aiProvider = useSettingsStore((s) => s.aiProvider);
  const aiModel = useSettingsStore((s) => s.aiModel);
  const setAIProvider = useSettingsStore((s) => s.setAIProvider);
  const setAIModel = useSettingsStore((s) => s.setAIModel);

  const send = useConnectionStore((s) => s.send);
  const setUsingApiKey = useConnectionStore((s) => s.setUsingApiKey);
  const setCurrentProvider = useConnectionStore((s) => s.setCurrentProvider);
  const usingApiKey = useConnectionStore((s) => s.usingApiKey);

  const currentModel = useMetricsStore((s) => s.currentModel);

  const setActivePanel = useUIStore((s) => s.setActivePanel);

  // When popover opens, default to current provider
  const activePopoverProvider = popoverProvider ?? aiProvider;

  // Click outside to close
  useEffect(() => {
    if (!isOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  const displayModel = getDisplayModel(currentModel, aiModel, aiProvider);
  const providerName = PROVIDER_INFO[aiProvider].name;

  function handleModelSelect(provider: AIProvider, modelId: string) {
    setAIProvider(provider);
    setAIModel(modelId);

    const storedKey = sessionStorage.getItem(`rain-api-key-${provider}`);
    if (storedKey) {
      send({ type: "set_api_key", key: storedKey, provider, model: modelId });
      setUsingApiKey(true);
      setCurrentProvider(provider);
    } else {
      // No key for this provider — open config panel
      setActivePanel("apiKey");
    }

    setIsOpen(false);
  }

  function handleToggle() {
    if (!isOpen) setPopoverProvider(null);
    setIsOpen(!isOpen);
  }

  const popoverModels = PROVIDER_MODELS[activePopoverProvider];

  return (
    <div className="relative" ref={popoverRef}>
      {/* Badge */}
      <button
        onClick={handleToggle}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface2 hover:bg-overlay/60 transition-colors cursor-pointer shrink-0 focus-ring"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        {/* Provider dot */}
        <span className={`w-2 h-2 rounded-full shrink-0 ${PROVIDER_COLORS[aiProvider]}`} />

        {/* Provider + Model name */}
        <span className="hidden sm:inline text-xs font-medium text-text truncate max-w-[140px]">
          {providerName}
        </span>
        <span className="hidden sm:inline text-xs text-text2">·</span>
        <span className="text-xs font-medium text-text truncate max-w-[120px]">
          {displayModel}
        </span>

        {/* Key indicator */}
        {usingApiKey && (
          <span className="hidden md:inline text-[9px] px-1 py-0.5 rounded bg-green/15 text-green font-medium">
            API
          </span>
        )}

        {/* Chevron */}
        <ChevronDown
          size={12}
          className={`text-text2 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Popover */}
      {isOpen && (
        <div className="absolute top-full mt-1.5 right-0 w-72 max-w-[calc(100vw-2rem)] bg-surface border border-overlay rounded-xl shadow-xl z-30 overflow-hidden">
          {/* Provider tabs */}
          <div className="flex gap-0.5 p-1.5 bg-surface2/50">
            {PROVIDERS.map((p) => (
              <button
                key={p}
                onClick={() => setPopoverProvider(p)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-medium transition-all ${
                  activePopoverProvider === p
                    ? "bg-primary text-on-primary shadow-sm"
                    : "text-text2 hover:text-text hover:bg-overlay/50"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${PROVIDER_COLORS[p]}`} />
                {PROVIDER_INFO[p].name}
                {hasStoredKey(p) && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green shrink-0" />
                )}
              </button>
            ))}
          </div>

          {/* Model list */}
          <div className="py-1 max-h-52 overflow-y-auto" role="listbox" aria-label="Models">
            {popoverModels.map((model) => {
              const isActive = aiProvider === activePopoverProvider && aiModel === model.id;
              return (
                <button
                  key={model.id}
                  onClick={() => handleModelSelect(activePopoverProvider, model.id)}
                  role="option"
                  aria-selected={isActive}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-text hover:bg-surface2"
                  }`}
                >
                  {/* Checkmark */}
                  <span className="w-4 text-center">
                    {isActive && <Check size={14} strokeWidth={2.5} />}
                  </span>
                  <span>{model.name}</span>
                </button>
              );
            })}
          </div>

          {/* Footer */}
          <div className="border-t border-overlay px-3 py-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs">
              {hasStoredKey(activePopoverProvider) ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-green" />
                  <span className="text-text2">{t("modelSwitcher.keyConfigured")}</span>
                </>
              ) : (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-subtext" />
                  <span className="text-text2">{t("modelSwitcher.noKey")}</span>
                  <button
                    onClick={() => {
                      setAIProvider(activePopoverProvider);
                      setActivePanel("apiKey");
                      setIsOpen(false);
                    }}
                    className="text-primary hover:underline ml-1"
                  >
                    {t("modelSwitcher.configure")}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Note */}
          <div className="border-t border-overlay/50 px-3 py-1.5">
            <span className="text-[10px] text-subtext">
              {t("modelSwitcher.appliesNext")}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
