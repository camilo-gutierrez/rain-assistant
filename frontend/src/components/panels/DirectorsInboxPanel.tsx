"use client";

import { useEffect, useState, useCallback } from "react";
import React from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { fetchInbox, updateInboxItem } from "@/lib/api";
import type { InboxItem } from "@/lib/types";
import {
  Inbox,
  CheckCircle,
  XCircle,
  Archive,
  FileText,
  Code,
  BarChart3,
  Bell,
  PenLine,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import EmptyState from "@/components/EmptyState";
import { SkeletonList } from "@/components/Skeleton";
import ReactMarkdown from "react-markdown";

type Filter = "all" | "unread";

const TYPE_ICONS: Record<string, typeof FileText> = {
  report: BarChart3,
  draft: PenLine,
  analysis: FileText,
  code: Code,
  notification: Bell,
};

const TYPE_KEYS: Record<string, string> = {
  report: "inbox.typeReport",
  draft: "inbox.typeDraft",
  analysis: "inbox.typeAnalysis",
  code: "inbox.typeCode",
  notification: "inbox.typeNotification",
};

const STATUS_COLORS: Record<string, string> = {
  unread: "bg-primary",
  read: "bg-subtext",
  approved: "bg-green",
  rejected: "bg-red",
  archived: "bg-subtext/50",
};

export default function DirectorsInboxPanel() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);
  const setInboxUnreadCount = useUIStore((s) => s.setInboxUnreadCount);

  const [items, setItems] = useState<InboxItem[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const params = filter === "unread" ? { status: "unread" } : {};
      const data = await fetchInbox(authToken, params);
      setItems(data.items);
      setInboxUnreadCount(data.unread_count);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken, filter, setInboxUnreadCount]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  async function handleStatusChange(item: InboxItem, newStatus: string) {
    if (!authToken) return;
    try {
      const data = await updateInboxItem(item.id, newStatus, item.user_comment, authToken);
      setItems((prev) => prev.map((it) => it.id === item.id ? data.item : it));
      // Update unread count
      const unread = items.filter((it) => it.id === item.id ? newStatus === "unread" : it.status === "unread").length;
      setInboxUnreadCount(unread);
    } catch {
      // silent
    }
  }

  async function handleExpand(item: InboxItem) {
    if (expandedId === item.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(item.id);
    // Mark as read if unread
    if (item.status === "unread") {
      await handleStatusChange(item, "read");
    }
  }

  const filters: { key: Filter; label: string }[] = [
    { key: "all", label: t("inbox.all") },
    { key: "unread", label: t("inbox.unread") },
  ];

  return (
    <div className="p-4 space-y-4">
      {/* Filter pills */}
      <div className="flex gap-1.5">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
              filter === f.key
                ? "bg-primary text-on-primary"
                : "bg-surface2 text-text2 hover:bg-surface2/80"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Items */}
      {loading ? (
        <SkeletonList count={4} height="h-16" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={t("inbox.empty")}
          hint={t("inbox.emptyHint")}
        />
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <InboxCard
              key={item.id}
              item={item}
              isExpanded={expandedId === item.id}
              onExpand={() => handleExpand(item)}
              onStatusChange={(s) => handleStatusChange(item, s)}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// --- InboxCard sub-component ---

interface InboxCardProps {
  item: InboxItem;
  isExpanded: boolean;
  onExpand: () => void;
  onStatusChange: (status: string) => void;
  t: (key: string) => string;
}

const InboxCard = React.memo(function InboxCard({
  item,
  isExpanded,
  onExpand,
  onStatusChange,
  t,
}: InboxCardProps) {
  const [commenting, setCommenting] = useState(false);
  const [comment, setComment] = useState(item.user_comment || "");
  const [saving, setSaving] = useState(false);
  const authToken = useConnectionStore((s) => s.authToken);

  const TypeIcon = TYPE_ICONS[item.content_type] || FileText;
  const typeLabel = TYPE_KEYS[item.content_type] ? t(TYPE_KEYS[item.content_type]) : item.content_type;
  const timeStr = new Date(item.created_at * 1000).toLocaleString();

  async function saveComment() {
    if (!authToken) return;
    setSaving(true);
    try {
      await updateInboxItem(item.id, item.status, comment || null, authToken);
      setCommenting(false);
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`rounded-lg transition-colors overflow-hidden ${
      item.status === "unread" ? "bg-primary/5 border border-primary/20" : "bg-surface2/50"
    }`}>
      {/* Header row */}
      <button
        onClick={onExpand}
        className="w-full flex items-center gap-2.5 p-3 text-left"
      >
        <div className={`w-2 h-2 rounded-full shrink-0 ${STATUS_COLORS[item.status] || "bg-subtext"}`} />
        <TypeIcon size={14} className="text-text2 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-text truncate">{item.title}</div>
          <div className="text-xs text-subtext flex items-center gap-1.5 mt-0.5">
            <span>{item.director_name}</span>
            <span className="text-xs px-1 py-0 rounded bg-surface2 text-text2">{typeLabel}</span>
            <span>{timeStr}</span>
          </div>
        </div>
        <div className="shrink-0">
          {isExpanded ? <ChevronUp size={14} className="text-text2" /> : <ChevronDown size={14} className="text-text2" />}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-3 border-t border-overlay/50 pt-3">
          {/* Markdown content */}
          <div className="prose prose-sm max-w-none text-text prose-headings:text-text prose-p:text-text2 prose-code:text-primary prose-a:text-blue prose-pre:bg-surface2 prose-pre:text-text overflow-x-auto">
            <ReactMarkdown>{item.content}</ReactMarkdown>
          </div>

          {/* Metadata */}
          {item.metadata && Object.keys(item.metadata).length > 0 && (
            <div className="flex gap-2 flex-wrap text-xs text-subtext">
              {item.metadata.cost !== undefined && (
                <span>${Number(item.metadata.cost).toFixed(4)}</span>
              )}
              {item.metadata.duration !== undefined && (
                <span>{Number(item.metadata.duration).toFixed(1)}s</span>
              )}
            </div>
          )}

          {/* Comment */}
          {commenting ? (
            <div className="space-y-2">
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder={t("inbox.addComment")}
                className="w-full text-sm px-3 py-2 rounded-lg bg-surface2 border border-overlay text-text placeholder:text-subtext resize-none focus-ring"
                rows={2}
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setCommenting(false)}
                  className="text-xs px-2.5 py-1 rounded-lg text-text2 hover:bg-surface2 transition-colors"
                >
                  {t("pin.cancel")}
                </button>
                <button
                  onClick={saveComment}
                  disabled={saving}
                  className="text-xs px-2.5 py-1 rounded-lg bg-primary text-on-primary hover:bg-primary/80 transition-colors disabled:opacity-40"
                >
                  {saving ? <Loader2 size={12} className="animate-spin" /> : "OK"}
                </button>
              </div>
            </div>
          ) : item.user_comment ? (
            <button
              onClick={() => setCommenting(true)}
              className="text-xs text-text2 italic bg-surface2/50 px-2 py-1 rounded w-full text-left hover:bg-surface2 transition-colors"
            >
              {item.user_comment}
            </button>
          ) : null}

          {/* Actions */}
          <div className="flex items-center gap-2">
            {item.status !== "approved" && (
              <button
                onClick={() => onStatusChange("approved")}
                className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-green/10 text-green hover:bg-green/20 transition-colors"
              >
                <CheckCircle size={12} />
                {t("inbox.approve")}
              </button>
            )}
            {item.status !== "rejected" && (
              <button
                onClick={() => onStatusChange("rejected")}
                className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-red/10 text-red hover:bg-red/20 transition-colors"
              >
                <XCircle size={12} />
                {t("inbox.reject")}
              </button>
            )}
            {item.status !== "archived" && (
              <button
                onClick={() => onStatusChange("archived")}
                className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-surface2 text-text2 hover:bg-surface2/80 transition-colors"
              >
                <Archive size={12} />
                {t("inbox.archive")}
              </button>
            )}
            {!commenting && (
              <button
                onClick={() => setCommenting(true)}
                className="ml-auto text-xs text-subtext hover:text-text2 transition-colors"
              >
                {t("inbox.addComment")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
});
