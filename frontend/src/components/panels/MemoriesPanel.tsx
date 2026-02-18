"use client";

import { useEffect, useState, useCallback } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import { fetchMemories, addMemory, deleteMemory, clearAllMemories } from "@/lib/api";
import type { Memory } from "@/lib/types";
import { Brain, Plus, Trash2, X, AlertTriangle } from "lucide-react";

const CATEGORY_COLORS: Record<string, string> = {
  preference: "bg-blue-500/15 text-blue-600",
  fact: "bg-green-500/15 text-green-600",
  pattern: "bg-purple-500/15 text-purple-600",
  project: "bg-amber-500/15 text-amber-600",
};

export default function MemoriesPanel() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);

  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [newContent, setNewContent] = useState("");
  const [newCategory, setNewCategory] = useState("fact");
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const loadMemories = useCallback(async () => {
    if (!authToken) return;
    try {
      const data = await fetchMemories(authToken);
      setMemories(data.memories);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    loadMemories();
  }, [loadMemories]);

  async function handleAdd() {
    if (!newContent.trim() || !authToken) return;
    try {
      await addMemory(newContent.trim(), newCategory, authToken);
      setNewContent("");
      loadMemories();
    } catch {
      // silently fail
    }
  }

  async function handleDelete(id: string) {
    if (!authToken) return;
    try {
      await deleteMemory(id, authToken);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch {
      // silently fail
    }
  }

  async function handleClearAll() {
    if (!authToken) return;
    try {
      await clearAllMemories(authToken);
      setMemories([]);
      setShowClearConfirm(false);
    } catch {
      // silently fail
    }
  }

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={20} className="text-primary" />
          <h2 className="text-base font-semibold text-text">
            {t("memories.title")}
          </h2>
          {memories.length > 0 && (
            <span className="text-xs text-text2 bg-surface2 px-1.5 py-0.5 rounded-full">
              {memories.length}
            </span>
          )}
        </div>
        {memories.length > 0 && (
          <button
            onClick={() => setShowClearConfirm(true)}
            className="text-xs text-red hover:text-red/80 transition-colors"
          >
            {t("memories.clearAll")}
          </button>
        )}
      </div>

      {/* Clear confirmation */}
      {showClearConfirm && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red/10 border border-red/20">
          <AlertTriangle size={16} className="text-red shrink-0" />
          <span className="text-sm text-text flex-1">{t("memories.clearConfirm")}</span>
          <button
            onClick={handleClearAll}
            className="text-xs px-2 py-1 rounded bg-red text-white hover:bg-red/80"
          >
            {t("memories.clearAll")}
          </button>
          <button
            onClick={() => setShowClearConfirm(false)}
            className="text-text2 hover:text-text"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Add new memory */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder={t("memories.addPlaceholder")}
          className="flex-1 text-sm px-3 py-2 rounded-lg bg-surface2 border border-overlay text-text placeholder:text-subtext focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <select
          value={newCategory}
          onChange={(e) => setNewCategory(e.target.value)}
          className="text-xs px-2 py-1 rounded-lg bg-surface2 border border-overlay text-text focus:outline-none"
        >
          <option value="fact">{t("memories.category.fact")}</option>
          <option value="preference">{t("memories.category.preference")}</option>
          <option value="pattern">{t("memories.category.pattern")}</option>
          <option value="project">{t("memories.category.project")}</option>
        </select>
        <button
          onClick={handleAdd}
          disabled={!newContent.trim()}
          className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg bg-primary text-on-primary hover:bg-primary/80 disabled:opacity-40 transition-colors"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Memory list */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 rounded-lg shimmer-bg" />
          ))}
        </div>
      ) : memories.length === 0 ? (
        <div className="text-center py-8">
          <Brain size={32} className="mx-auto text-text2/40 mb-2" />
          <p className="text-sm text-text2">{t("memories.empty")}</p>
          <p className="text-xs text-subtext mt-1">{t("memories.emptyHint")}</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="group flex items-start gap-2 p-2.5 rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors"
            >
              {/* Category badge */}
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 mt-0.5 ${
                CATEGORY_COLORS[memory.category] || CATEGORY_COLORS.fact
              }`}>
                {t(`memories.category.${memory.category}`)}
              </span>

              {/* Content */}
              <span className="text-sm text-text flex-1">{memory.content}</span>

              {/* Delete */}
              <button
                onClick={() => handleDelete(memory.id)}
                className="opacity-0 group-hover:opacity-100 text-text2 hover:text-red transition-all shrink-0"
                title="Delete"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
