"use client";

import { useEffect, useState } from "react";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { useUIStore } from "@/stores/useUIStore";
import { useHistory } from "@/hooks/useHistory";
import { useTranslation } from "@/hooks/useTranslation";
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

  useEffect(() => {
    if (isVisible) {
      refreshList();
      setConfirmDelete(null);
    }
  }, [isVisible, refreshList]);

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
        <div className="flex items-center justify-between px-4 py-3 border-b border-overlay">
          <h2 className="text-sm font-semibold text-text">
            {t("history.title")}
          </h2>
          <button
            onClick={toggleMobileSidebar}
            className="p-2 rounded-full hover:bg-surface2 transition-colors text-text2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

      {mode === "inline" && (
        <div className="flex items-center gap-2 px-4 py-2.5">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-subtext">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span className="text-xs font-semibold text-subtext uppercase tracking-wider">
            {t("history.title")}
          </span>
          {conversations.length > 0 && (
            <span className="ml-auto text-[10px] font-medium text-text2 bg-surface2 px-1.5 py-0.5 rounded-full">
              {conversations.length}
            </span>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-text2 text-sm">
            {t("history.loading")}
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 px-6">
            <div className="w-12 h-12 rounded-2xl bg-surface2 flex items-center justify-center mb-3 animate-[float_3s_ease-in-out_infinite]">
              <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-subtext">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                <line x1="9" y1="10" x2="15" y2="10" />
              </svg>
            </div>
            <p className="text-sm text-text2 text-center">
              {t("history.empty")}
            </p>
            <p className="text-xs text-subtext text-center mt-1">
              {t("sidebar.emptyHint")}
            </p>
          </div>
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

      <div className="px-4 py-2.5 border-t border-overlay/60 text-xs text-subtext text-center">
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
          className="fixed inset-0 bg-black/40 z-40"
          onClick={toggleMobileSidebar}
        />
      )}
      <div
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
      className={`group px-3 py-2.5 cursor-pointer rounded-lg transition-all duration-150 ${
        isActive
          ? "bg-primary/8 border-l-[3px] border-l-primary pl-[9px]"
          : "border-l-[3px] border-l-transparent pl-[9px] hover:bg-surface2/60"
      }`}
      onClick={onLoad}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className={`text-xs font-medium truncate ${isActive ? "text-primary" : "text-text"}`}>
            {conv.label}
          </div>
          <div className="text-xs text-text2 truncate mt-0.5">
            {conv.preview || "..."}
          </div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-subtext">
            <span>{formatDate(conv.updatedAt)}</span>
            <span className="w-0.5 h-0.5 rounded-full bg-subtext" />
            <span>{conv.messageCount} msgs</span>
            {conv.totalCost > 0 && (
              <>
                <span className="w-0.5 h-0.5 rounded-full bg-subtext" />
                <span>${conv.totalCost.toFixed(4)}</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={onDelete}
          className={`shrink-0 p-1.5 rounded-lg text-xs transition-all duration-150 ${
            isConfirmingDelete
              ? "text-red bg-red/10"
              : "text-subtext hover:text-red hover:bg-red/5 opacity-0 group-hover:opacity-100"
          }`}
          title={isConfirmingDelete ? t("history.confirmDelete") : t("history.delete")}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
