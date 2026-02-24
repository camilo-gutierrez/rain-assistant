"use client";

import type { SubAgentMessage } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";

interface Props {
  message: SubAgentMessage;
}

export default function SubAgentIndicator({ message }: Props) {
  const { t } = useTranslation();
  const isSpawned = message.eventType === "spawned";
  const isCompleted = message.eventType === "completed";
  const isError = message.status === "error";
  const isCancelled = message.status === "cancelled";

  const statusIcon = isSpawned
    ? "\u25B6"  // play
    : isError
      ? "\u2716" // x
      : isCancelled
        ? "\u23F9" // stop
        : "\u2714"; // check

  const statusColor = isSpawned
    ? "text-blue"
    : isError
      ? "text-red"
      : isCancelled
        ? "text-yellow"
        : "text-green";

  const bgColor = isSpawned
    ? "bg-blue/10 border-blue/20"
    : isError
      ? "bg-red/10 border-red/20"
      : isCancelled
        ? "bg-yellow/10 border-yellow/20"
        : "bg-green/10 border-green/20";

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${bgColor} text-sm`}>
      <span className={`text-base mt-0.5 ${statusColor}`}>{statusIcon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-text">
            {message.shortName}
          </span>
          {isSpawned && (
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue/20 text-blue animate-pulse">
              {t("subAgent.running")}
            </span>
          )}
          {isCompleted && !isError && !isCancelled && (
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-green/20 text-green">
              {t("subAgent.done")}
            </span>
          )}
          {isError && (
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-red/20 text-red">
              {t("subAgent.error")}
            </span>
          )}
          {isCancelled && (
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-yellow/20 text-yellow">
              {t("subAgent.cancelled")}
            </span>
          )}
        </div>
        <p className="text-text2 text-xs mt-1 line-clamp-3">
          {message.content}
        </p>
      </div>
    </div>
  );
}
