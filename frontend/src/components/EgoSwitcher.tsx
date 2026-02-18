"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import { fetchAlterEgos } from "@/lib/api";
import type { AlterEgo } from "@/lib/types";
import { ChevronDown, Check } from "lucide-react";

export default function EgoSwitcher() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [egos, setEgos] = useState<AlterEgo[]>([]);
  const [loading, setLoading] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  const activeEgoId = useSettingsStore((s) => s.activeEgoId);
  const setActiveEgoId = useSettingsStore((s) => s.setActiveEgoId);
  const send = useConnectionStore((s) => s.send);
  const connectionStatus = useConnectionStore((s) => s.connectionStatus);
  const authToken = useConnectionStore((s) => s.authToken);

  const activeEgo = egos.find((e) => e.id === activeEgoId);

  // Fetch egos when popover opens
  const loadEgos = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await fetchAlterEgos(authToken);
      setEgos(data.egos);
      // Sync active ego from server if different
      if (data.active_ego_id && data.active_ego_id !== activeEgoId) {
        setActiveEgoId(data.active_ego_id);
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }, [authToken, activeEgoId, setActiveEgoId]);

  // Load egos on first connect
  useEffect(() => {
    if (connectionStatus === "connected") {
      loadEgos();
    }
  }, [connectionStatus, loadEgos]);

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

  function handleToggle() {
    if (!isOpen) loadEgos();
    setIsOpen(!isOpen);
  }

  function handleSelect(ego: AlterEgo) {
    if (ego.id === activeEgoId) {
      setIsOpen(false);
      return;
    }
    setActiveEgoId(ego.id);
    send({ type: "set_alter_ego", ego_id: ego.id });
    setIsOpen(false);
  }

  const displayEmoji = activeEgo?.emoji || "🌧️";
  const displayName = activeEgo?.name || "Rain";

  return (
    <div className="relative" ref={popoverRef}>
      {/* Badge */}
      <button
        onClick={handleToggle}
        className="flex items-center gap-1.5 shrink-0 focus-ring rounded-lg px-1 py-0.5 hover:bg-surface2 transition-colors"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span className="text-sm">{displayEmoji}</span>
        <h1 className="text-sm font-semibold text-text truncate max-w-[140px]">
          {displayName}
        </h1>
        <ChevronDown
          size={12}
          className={`text-text2 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Popover */}
      {isOpen && (
        <div className="absolute top-full mt-1.5 left-0 w-72 max-w-[calc(100vw-2rem)] bg-surface border border-overlay rounded-xl shadow-xl z-30 overflow-hidden">
          {/* Header */}
          <div className="px-3 py-2 border-b border-overlay bg-surface2/50">
            <span className="text-xs font-medium text-text2">
              {t("alterEgo.title")}
            </span>
          </div>

          {/* Ego list */}
          <div className="py-1 max-h-64 overflow-y-auto" role="listbox" aria-label="Alter Egos">
            {loading && egos.length === 0 ? (
              <div className="px-3 py-4 text-center text-sm text-text2">...</div>
            ) : (
              egos.map((ego) => {
                const isActive = ego.id === activeEgoId;
                return (
                  <button
                    key={ego.id}
                    onClick={() => handleSelect(ego)}
                    role="option"
                    aria-selected={isActive}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors ${
                      isActive
                        ? "bg-primary/10"
                        : "hover:bg-surface2"
                    }`}
                  >
                    {/* Emoji */}
                    <span className="text-lg shrink-0">{ego.emoji}</span>

                    {/* Name + description */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-sm font-medium truncate ${
                          isActive ? "text-primary" : "text-text"
                        }`}>
                          {ego.name}
                        </span>
                        {isActive && (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-primary/15 text-primary font-medium shrink-0">
                            {t("alterEgo.active")}
                          </span>
                        )}
                        {ego.is_builtin ? (
                          <span className="hidden sm:inline text-[9px] px-1 py-0.5 rounded bg-overlay text-subtext shrink-0">
                            {t("alterEgo.builtin")}
                          </span>
                        ) : (
                          <span className="hidden sm:inline text-[9px] px-1 py-0.5 rounded bg-green/15 text-green shrink-0">
                            {t("alterEgo.custom")}
                          </span>
                        )}
                      </div>
                      {ego.description && (
                        <p className="text-xs text-text2 truncate mt-0.5">
                          {ego.description}
                        </p>
                      )}
                    </div>

                    {/* Checkmark */}
                    <span className="w-4 text-center shrink-0">
                      {isActive && <Check size={14} strokeWidth={2.5} className="text-primary" />}
                    </span>
                  </button>
                );
              })
            )}
          </div>

          {/* Footer note */}
          <div className="border-t border-overlay/50 px-3 py-1.5">
            <span className="text-[10px] text-subtext">
              {t("alterEgo.switchingTo", { name: "..." }).replace("...", "").replace("Switching to ", "").replace("Cambiando a ", "")}
              Rain can create custom egos via chat
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
