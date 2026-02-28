"use client";

import React, { useState, useCallback } from "react";
import { Copy, Check, CheckCircle, XCircle } from "lucide-react";
import type { ToolResultMessage } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";
import { useToastStore } from "@/stores/useToastStore";

interface Props {
  message: ToolResultMessage;
}

const TRUNCATE_AT = 300;

const ToolResultBlock = React.memo(function ToolResultBlock({ message }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const { t } = useTranslation();
  const addToast = useToastStore((s) => s.addToast);

  const isTruncated = message.content.length > TRUNCATE_AT;
  const displayText = expanded
    ? message.content
    : message.content.slice(0, TRUNCATE_AT);

  const borderColor = message.isError ? "border-l-red" : "border-l-green";
  const bgClass = message.isError ? "bg-red/5" : "bg-green/5";

  const handleCopy = useCallback(async () => {
    if (copied) return;
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      addToast({ type: "success", message: t("toast.copySuccess"), duration: 2000 });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API may fail silently
    }
  }, [copied, message.content, addToast, t]);

  return (
    <div
      className={`group relative self-start max-w-[85%] border-l-2 ${borderColor} rounded-r-lg px-3 py-2 ${bgClass} ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          {message.isError ? (
            <XCircle size={13} className="text-red" />
          ) : (
            <CheckCircle size={13} className="text-green" />
          )}
          <span className={`text-xs font-semibold ${message.isError ? "text-red" : "text-green"}`}>
            {message.isError ? "Error" : "Result"}
          </span>
        </div>
        {/* Copy button */}
        {message.content.trim() && (
          <button
            onClick={handleCopy}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg bg-surface2/80 text-subtext hover:text-primary hover:bg-primary/10 transition-all duration-200 opacity-0 group-hover:opacity-100 touch-visible"
            aria-label={t("a11y.copy")}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
        )}
      </div>

      <pre className="text-xs text-text2 font-mono whitespace-pre-wrap break-words max-h-[120px] overflow-y-auto">
        {displayText}
        {isTruncated && !expanded && "..."}
      </pre>

      {isTruncated && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-1 text-xs text-primary hover:underline py-1"
        >
          {t("chat.showFullOutput")}
        </button>
      )}
    </div>
  );
});

export default ToolResultBlock;
