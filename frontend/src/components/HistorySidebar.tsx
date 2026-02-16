"use client";

import { useEffect, useState } from "react";
import { useHistoryStore } from "@/stores/useHistoryStore";
import { useHistory } from "@/hooks/useHistory";
import { useTranslation } from "@/hooks/useTranslation";
import type { ConversationMeta } from "@/lib/types";

export default function HistorySidebar() {
  const sidebarOpen = useHistoryStore((s) => s.sidebarOpen);
  const conversations = useHistoryStore((s) => s.conversations);
  const isLoading = useHistoryStore((s) => s.isLoading);
  const activeConversationId = useHistoryStore((s) => s.activeConversationId);
  const setSidebarOpen = useHistoryStore((s) => s.setSidebarOpen);
  const { refreshList, load, remove } = useHistory();
  const { t } = useTranslation();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  useEffect(() => {
    if (sidebarOpen) {
      refreshList();
      setConfirmDelete(null);
    }
  }, [sidebarOpen, refreshList]);

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

  return (
    <>
      {/* Backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed top-0 left-0 h-full w-80 max-w-[85vw] bg-surface border-r border-overlay z-50 flex flex-col transition-transform duration-300 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-overlay">
          <h2
            className="font-[family-name:var(--font-orbitron)] text-sm font-bold bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(135deg, var(--cyan), var(--magenta))",
            }}
          >
            {t("history.title")}
          </h2>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 rounded-md hover:bg-surface2 transition-colors text-text2 hover:text-cyan"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center text-text2 text-sm">
              {t("history.loading")}
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center text-text2 text-sm">
              {t("history.empty")}
            </div>
          ) : (
            conversations.map((conv) => (
              <ConversationEntry
                key={conv.id}
                conv={conv}
                isActive={conv.id === activeConversationId}
                isConfirmingDelete={confirmDelete === conv.id}
                onLoad={() => load(conv.id)}
                onDelete={(e) => handleDelete(conv.id, e)}
                formatDate={formatDate}
                t={t}
              />
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-overlay text-xs text-subtext text-center">
          {t("history.count", { n: conversations.length, max: 5 })}
        </div>
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
      className={`group px-4 py-3 border-b border-overlay/50 cursor-pointer hover:bg-surface2/50 transition-colors ${
        isActive ? "bg-surface2 border-l-2 border-l-cyan" : ""
      }`}
      onClick={onLoad}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-[family-name:var(--font-jetbrains)] text-xs font-bold text-text truncate">
            {conv.label}
          </div>
          <div className="text-xs text-text2 truncate mt-0.5">
            {conv.preview || "..."}
          </div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-subtext">
            <span>{formatDate(conv.updatedAt)}</span>
            <span>{conv.messageCount} msgs</span>
            {conv.totalCost > 0 && (
              <span>${conv.totalCost.toFixed(4)}</span>
            )}
          </div>
        </div>
        <button
          onClick={onDelete}
          className={`shrink-0 p-1 rounded text-xs transition-colors ${
            isConfirmingDelete
              ? "text-red bg-red/10"
              : "text-subtext hover:text-red opacity-0 group-hover:opacity-100"
          }`}
          title={
            isConfirmingDelete
              ? t("history.confirmDelete")
              : t("history.delete")
          }
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
