"use client";

import React, { useState } from "react";
import type { PermissionRequestMessage } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";

interface Props {
  message: PermissionRequestMessage;
}

function getToolDetail(tool: string, input: Record<string, unknown>): string {
  switch (tool) {
    case "Write":
    case "Edit":
    case "Read":
      return typeof input.file_path === "string" ? input.file_path : "";
    case "Bash":
      return typeof input.command === "string"
        ? input.command.length > 200
          ? input.command.slice(0, 200) + "..."
          : input.command
        : "";
    case "NotebookEdit":
      return typeof input.notebook_path === "string" ? input.notebook_path : "";
    default:
      if (typeof input.file_path === "string") return input.file_path;
      if (typeof input.command === "string") return input.command;
      return "";
  }
}

const PermissionRequestBlock = React.memo(function PermissionRequestBlock({
  message,
}: Props) {
  const { t } = useTranslation();
  const send = useConnectionStore((s) => s.send);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const updatePermissionStatus = useAgentStore((s) => s.updatePermissionStatus);

  const [pin, setPin] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRed = message.level === "red";
  const isPending = message.status === "pending";

  const borderColor = isRed ? "border-l-red" : "border-l-yellow";
  const bgClass = isRed ? "bg-red/5" : "bg-yellow/5";
  const badgeBg = isRed ? "bg-red/15 text-red" : "bg-yellow/15 text-yellow";

  const detail = getToolDetail(message.tool, message.input);

  const handleApprove = () => {
    if (!activeAgentId) return;
    if (isRed && !pin.trim()) return;

    setIsSubmitting(true);
    const sent = send({
      type: "permission_response",
      request_id: message.requestId,
      agent_id: activeAgentId,
      approved: true,
      ...(isRed ? { pin: pin.trim() } : {}),
    });

    if (sent) {
      updatePermissionStatus(activeAgentId, message.requestId, "approved");
    } else {
      setIsSubmitting(false);
    }
  };

  const handleDeny = () => {
    if (!activeAgentId) return;

    setIsSubmitting(true);
    const sent = send({
      type: "permission_response",
      request_id: message.requestId,
      agent_id: activeAgentId,
      approved: false,
    });

    if (sent) {
      updatePermissionStatus(activeAgentId, message.requestId, "denied");
    } else {
      setIsSubmitting(false);
    }
  };

  // Resolved state (approved / denied / expired)
  if (!isPending) {
    const statusKey =
      message.status === "approved"
        ? "perm.approved"
        : message.status === "denied"
          ? "perm.denied"
          : "perm.expired";

    const statusColor =
      message.status === "approved"
        ? "text-green"
        : message.status === "denied"
          ? "text-red"
          : "text-text2";

    return (
      <div
        className={`self-start max-w-[85%] border-l-[3px] ${borderColor} rounded-r-lg px-3 py-2 ${bgClass} opacity-70`}
      >
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${badgeBg}`}>
            {isRed ? t("perm.levelRed") : t("perm.levelYellow")}
          </span>
          <span className="text-xs font-semibold text-text1">
            {message.tool}
          </span>
        </div>
        {detail && (
          <div className="text-xs text-text2 font-[family-name:var(--font-jetbrains)] mt-1 break-all">
            {detail}
          </div>
        )}
        <div className={`text-xs font-semibold mt-1.5 ${statusColor}`}>
          ✓ {t(statusKey)}
        </div>
      </div>
    );
  }

  // Pending state — show action buttons
  return (
    <div
      className={`self-start max-w-[85%] border-l-[3px] ${borderColor} rounded-r-lg px-3 py-2.5 ${bgClass} ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${badgeBg}`}>
          {isRed ? t("perm.levelRed") : t("perm.levelYellow")}
        </span>
        <span className="text-xs font-semibold text-text1">
          {message.tool}
        </span>
      </div>

      {/* Tool detail */}
      {detail && (
        <div className="text-xs text-text2 font-[family-name:var(--font-jetbrains)] mt-1 break-all">
          {detail}
        </div>
      )}

      {/* Danger reason (RED only) */}
      {isRed && message.reason && (
        <div className="text-xs text-red mt-1.5 flex items-center gap-1">
          <span>⚠</span>
          <span>{message.reason}</span>
        </div>
      )}

      {/* PIN input (RED only) */}
      {isRed && (
        <div className="mt-2">
          <input
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleApprove();
            }}
            placeholder={t("perm.enterPin")}
            disabled={isSubmitting}
            className="w-full px-2 py-1 text-xs rounded border border-border bg-bg text-text1 placeholder:text-text2/50 focus:outline-none focus:border-primary"
            autoFocus
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 mt-2">
        <button
          onClick={handleApprove}
          disabled={isSubmitting || (isRed && !pin.trim())}
          className="px-3 py-1 text-xs font-medium rounded bg-green/15 text-green hover:bg-green/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? t("perm.processing") : t("perm.approve")}
        </button>
        <button
          onClick={handleDeny}
          disabled={isSubmitting}
          className="px-3 py-1 text-xs font-medium rounded bg-red/15 text-red hover:bg-red/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {t("perm.deny")}
        </button>
      </div>
    </div>
  );
});

export default PermissionRequestBlock;
