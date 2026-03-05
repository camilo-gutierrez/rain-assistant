"use client";

import { useEffect, useRef, useState } from "react";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { useUIStore } from "@/stores/useUIStore";
import { useHistory } from "@/hooks/useHistory";
import { useTranslation } from "@/hooks/useTranslation";
import { X, Clock, MessageSquare, Trash2 } from "lucide-react";
import type { ConversationMeta } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import { SkeletonList } from "@/components/Skeleton";

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
        <div className="flex items-center justify-between px-5 py-4 border-b border-overlay/40">
          <div className="flex items-center gap-2.5">
            <Clock size={18} className="text-text2" />
            <h2 className="text-sm font-semibold text-text">
              {t("history.title")}
            </h2>
          </div>
          <button
            onClick={toggleMobileSidebar}
            className="min-w-[44px] min-h-[44px] flex items-center justify-center rounded-[10px] hover:bg-surface2/60 transition-colors text-text2 hover:text-text focus-ring"
            aria-label={t("a11y.close")}
          >
            <X size={18} />
          </button>
        </div>
      )}

      {mode === "inline" && (
        <div className="flex items-center gap-2 px-3 py-2">
          <span className="text-xs font-medium text-subtext uppercase tracking-wide">
            {t("history.title")}
          </span>
          {conversations.length > 0 && (
            <span className="ml-auto text-xs text-subtext">
              {conversations.length}
            </span>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="px-3 py-3">
            <SkeletonList count={3} height="h-14" gap="space-y-1" />
          </div>
        ) : conversations.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title={t("history.empty")}
            hint={t("sidebar.emptyHint")}
          />
        ) : (
          <div className="flex flex-col gap-0.5 px-2 py-1">
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

      <div className="px-4 py-2 text-xs text-subtext text-center">
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
        className={`fixed top-0 left-0 h-full w-80 max-w-[85vw] bg-surface z-50 flex flex-col shadow-lg transition-transform duration-300 pl-[env(safe-area-inset-left)] ${
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
      className={`group relative px-3 py-2 cursor-pointer rounded-[10px] transition-colors duration-150 ${
        isActive
          ? "bg-surface2 text-text"
          : "hover:bg-surface2/50"
      }`}
      onClick={onLoad}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className={`text-sm truncate leading-tight ${isActive ? "font-medium text-text" : "text-text"}`}>
            {conv.label}
          </div>
          <div className="text-xs text-subtext truncate mt-0.5 leading-tight">
            {conv.preview || "..."}
          </div>
          <div className="flex items-center gap-1.5 mt-1 text-xs text-subtext">
            <span>{formatDate(conv.updatedAt)}</span>
            <span className="text-overlay">·</span>
            <span>{conv.messageCount} msgs</span>
            {conv.totalCost > 0 && (
              <>
                <span className="text-overlay">·</span>
                <span className="text-green">${conv.totalCost.toFixed(4)}</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={onDelete}
          className={`shrink-0 p-1.5 rounded-lg text-xs transition-all duration-150 mt-0.5 ${
            isConfirmingDelete
              ? "text-red bg-red/10"
              : "text-subtext hover:text-red hover:bg-red/5 opacity-0 group-hover:opacity-100 touch-visible"
          }`}
          title={isConfirmingDelete ? t("history.confirmDelete") : t("history.delete")}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
