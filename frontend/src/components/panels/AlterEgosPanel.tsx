"use client";

import { useEffect, useState, useCallback } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useTranslation } from "@/hooks/useTranslation";
import { fetchAlterEgos, deleteAlterEgo } from "@/lib/api";
import type { AlterEgo } from "@/lib/types";
import { Sparkles, Trash2, Check } from "lucide-react";
import { SkeletonList } from "@/components/Skeleton";

export default function AlterEgosPanel() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);
  const send = useConnectionStore((s) => s.send);
  const activeEgoId = useSettingsStore((s) => s.activeEgoId);
  const setActiveEgoId = useSettingsStore((s) => s.setActiveEgoId);

  const [egos, setEgos] = useState<AlterEgo[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadEgos = useCallback(async () => {
    if (!authToken) return;
    try {
      const data = await fetchAlterEgos(authToken);
      setEgos(data.egos);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    loadEgos();
  }, [loadEgos]);

  function handleActivate(egoId: string) {
    if (egoId === activeEgoId) return;
    setActiveEgoId(egoId);
    send({ type: "set_alter_ego", ego_id: egoId });
  }

  async function handleDelete(egoId: string) {
    if (!authToken || egoId === "rain") return;
    try {
      await deleteAlterEgo(egoId, authToken);
      setEgos((prev) => prev.filter((e) => e.id !== egoId));
      if (egoId === activeEgoId) {
        setActiveEgoId("rain");
        send({ type: "set_alter_ego", ego_id: "rain" });
      }
    } catch {
      // silently fail
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Sparkles size={20} className="text-primary" />
        <h2 className="text-base font-semibold text-text">
          {t("alterEgo.title")}
        </h2>
        <span className="text-xs text-text2 bg-surface2 px-1.5 py-0.5 rounded-full">
          {egos.length}
        </span>
      </div>

      {loading ? (
        <SkeletonList count={3} height="h-20" gap="space-y-3" />
      ) : (
        <div className="space-y-2">
          {egos.map((ego) => {
            const isActive = ego.id === activeEgoId;
            const isExpanded = expandedId === ego.id;
            return (
              <div
                key={ego.id}
                className={`rounded-xl border transition-all ${
                  isActive
                    ? "border-primary/30 bg-primary/5"
                    : "border-overlay bg-surface2/30 hover:bg-surface2/60"
                }`}
              >
                <div className="flex items-center gap-3 p-3">
                  <span className="text-2xl shrink-0">{ego.emoji}</span>
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : ego.id)}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-text truncate">
                        {ego.name}
                      </span>
                      {isActive && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-semibold">
                          {t("alterEgo.active")}
                        </span>
                      )}
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                        ego.is_builtin
                          ? "bg-overlay text-subtext"
                          : "bg-green/15 text-green"
                      }`}>
                        {ego.is_builtin ? t("alterEgo.builtin") : t("alterEgo.custom")}
                      </span>
                    </div>
                    <p className="text-xs text-text2 truncate mt-0.5">
                      {ego.description}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {!isActive && (
                      <button
                        onClick={() => handleActivate(ego.id)}
                        className="text-xs px-2.5 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 font-medium transition-colors"
                      >
                        {t("alterEgo.switch")}
                      </button>
                    )}
                    {isActive && (
                      <div className="w-8 h-8 flex items-center justify-center">
                        <Check size={16} className="text-primary" />
                      </div>
                    )}
                    {!ego.is_builtin && (
                      <button
                        onClick={() => handleDelete(ego.id)}
                        className="w-8 h-8 flex items-center justify-center rounded-lg text-text2 hover:text-red hover:bg-red/10 transition-colors"
                        title={t("alterEgo.delete")}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
                {isExpanded && (
                  <div className="px-3 pb-3 pt-0">
                    <div className="text-xs text-text2 bg-surface2/50 rounded-lg p-2.5 max-h-32 overflow-y-auto font-mono leading-relaxed">
                      {ego.system_prompt}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <p className="text-xs text-subtext text-center">
        {t("alterEgo.createHintShort")}
      </p>
    </div>
  );
}
