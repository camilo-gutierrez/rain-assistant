"use client";

import type { SubAgentMessage } from "@/lib/types";

interface Props {
  message: SubAgentMessage;
}

export default function SubAgentIndicator({ message }: Props) {
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
    ? "text-blue-400"
    : isError
      ? "text-red-400"
      : isCancelled
        ? "text-yellow-400"
        : "text-green-400";

  const bgColor = isSpawned
    ? "bg-blue-500/10 border-blue-500/20"
    : isError
      ? "bg-red-500/10 border-red-500/20"
      : isCancelled
        ? "bg-yellow-500/10 border-yellow-500/20"
        : "bg-green-500/10 border-green-500/20";

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${bgColor} text-sm`}>
      <span className={`text-base mt-0.5 ${statusColor}`}>{statusIcon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-text">
            {message.shortName}
          </span>
          {isSpawned && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 animate-pulse">
              running
            </span>
          )}
          {isCompleted && !isError && !isCancelled && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-500/20 text-green-400">
              done
            </span>
          )}
          {isError && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400">
              error
            </span>
          )}
          {isCancelled && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400">
              cancelled
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
