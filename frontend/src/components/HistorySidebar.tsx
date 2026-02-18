"use client";

import { useEffect, useRef, useState } from "react";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { useUIStore } from "@/stores/useUIStore";
import { useHistory } from "@/hooks/useHistory";
import { useTranslation } from "@/hooks/useTranslation";
import { X, Clock, MessageSquare, Trash2 } from "lucide-react";
import type { ConversationMeta } from "@/lib/types";

interface HistorySidebarProps {
  mode: "inline" | "drawer";
}

export default function HistorySidebar({ mode }: HistorySidebarProps) {
  const conversations = useHistoryStore((s) => s.conversations);
  const isLoading = useHistoryStore((s) => s.isLoading);
  const activeConversationId = useHistoryStore((s) => s.activeConversationId);
  const mobileSidebarOpen = useUIStore((s) => s.mobileSidebarOpen);
  const toggleMobileSidebar = useUIStore((s) => s.toggleMobileSidebar);
  const { refreshList, load, remove } = useHistory();
  const { t } = useTranslation();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const isVisible = mode === "inline" || mobileSidebarOpen;
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isVisible) {
      refreshList();
      setConfirmDelete(null);
    }
  }, [isVisible, refreshList]);

  // Drawer mode: Escape key handling + body scroll lock
  useEffect(() => {
    if (mode !== "drawer" || !mobileSidebarOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        toggleMobileSidebar();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [mode, mobileSidebarOpen, toggleMobileSidebar]);

  const formatDate = (ts: number) =>
    new Date(ts).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmDelete === id) {
      remove(id);
      setConfirmDelete(null);
    } else {
      setConfirmDelete(id);
    }
  };

  const content = (
    <>
      {mode === "drawer" && (
        <div className="flex items-center justify-between px-5 py-4 border-b border-overlay/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Clock size={16} className="text-primary" />
            </div>
            <h2 className="text-sm font-bold text-text">
              {t("history.title")}
            </h2>
          </div>
          <button
            onClick={toggleMobileSidebar}
            className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-xl hover:bg-surface2 transition-colors text-text2 hover:text-text focus-ring"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {mode === "inline" && (
        <div className="flex items-center gap-2 px-4 py-2.5">
          <Clock size={13} className="text-subtext" />
          <span className="text-[10px] font-semibold text-subtext uppercase tracking-widest">
            {t("history.title")}
          </span>
          {conversations.length > 0 && (
            <span className="ml-auto text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
              {conversations.length}
            </span>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-2 px-3 py-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="rounded-xl bg-surface2/40 p-3 animate-pulse">
                <div className="h-3.5 w-3/4 bg-surface2 rounded-md mb-2" />
                <div className="h-3 w-1/2 bg-surface2 rounded-md" />
              </div>
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 px-6">
            <div className="w-14 h-14 rounded-2xl bg-surface2/60 flex items-center justify-center mb-3">
              <MessageSquare size={24} strokeWidth={1.5} className="text-subtext/60" />
            </div>
            <p className="text-sm text-text2 text-center font-medium">
              {t("history.empty")}
            </p>
            <p className="text-xs text-subtext text-center mt-1.5 max-w-[200px] leading-relaxed">
              {t("sidebar.emptyHint")}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1 px-2 py-2">
            {conversations.map((conv) => (
              <ConversationEntry
                key={conv.id}
                conv={conv}
                isActive={conv.id === activeConversationId}
                isConfirmingDelete={confirmDelete === conv.id}
                onLoad={() => {
                  load(conv.id);
                  if (mode === "drawer") toggleMobileSidebar();
                }}
                onDelete={(e) => handleDelete(conv.id, e)}
                formatDate={formatDate}
                t={t}
              />
            ))}
          </div>
        )}
      </div>

      <div className="px-4 py-2.5 border-t border-overlay/40 text-[10px] text-subtext text-center font-medium">
        {t("history.count", { n: conversations.length, max: 5 })}
      </div>
    </>
  );

  if (mode === "inline") {
    return <div className="flex flex-col flex-1 min-h-0">{content}</div>;
  }

  return (
    <>
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 backdrop-blur-overlay"
          onClick={toggleMobileSidebar}
        />
      )}
      <div
        ref={drawerRef}
        className={`fixed top-0 left-0 h-full w-80 max-w-[85vw] bg-surface z-50 flex flex-col shadow-lg transition-transform duration-300 ${
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {content}
      </div>
    </>
  );
}

function ConversationEntry({
  conv,
  isActive,
  isConfirmingDelete,
  onLoad,
  onDelete,
  formatDate,
  t,
}: {
  conv: ConversationMeta;
  isActive: boolean;
  isConfirmingDelete: boolean;
  onLoad: () => void;
  onDelete: (e: React.MouseEvent) => void;
  formatDate: (ts: number) => string;
  t: (key: string) => string;
}) {
  return (
    <div
      className={`group relative px-3 py-2.5 cursor-pointer rounded-xl transition-all duration-150 ${
        isActive
          ? "bg-primary/10 shadow-[inset_0_0_0_1px_rgba(var(--primary-rgb),0.2)]"
          : "hover:bg-surface2/60"
      }`}
      onClick={onLoad}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className={`text-[13px] font-semibold truncate leading-tight ${isActive ? "text-primary" : "text-text"}`}>
            {conv.label}
          </div>
          <div className="text-xs text-text2 truncate mt-1 leading-tight opacity-80">
            {conv.preview || "..."}
          </div>
          <div className="flex items-center gap-1.5 mt-1.5 text-[10px] text-subtext">
            <span>{formatDate(conv.updatedAt)}</span>
            <span className="text-overlay">|</span>
            <span>{conv.messageCount} msgs</span>
            {conv.totalCost > 0 && (
              <>
                <span className="text-overlay">|</span>
                <span className="text-green font-medium">${conv.totalCost.toFixed(4)}</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={onDelete}
          className={`shrink-0 p-1.5 rounded-lg text-xs transition-all duration-150 mt-0.5 ${
            isConfirmingDelete
              ? "text-red bg-red/10 shadow-[inset_0_0_0_1px_rgba(211,47,47,0.2)]"
              : "text-subtext hover:text-red hover:bg-red/5 opacity-0 group-hover:opacity-100 touch-visible"
          }`}
          title={isConfirmingDelete ? t("history.confirmDelete") : t("history.delete")}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}
