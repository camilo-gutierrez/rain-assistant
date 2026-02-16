"use client";

import React from "react";
import type { ToolUseMessage } from "@/lib/types";

interface Props {
  message: ToolUseMessage;
}

function getToolDetail(tool: string, input: Record<string, unknown>): string {
  switch (tool) {
    case "Read":
    case "Write":
    case "Edit":
      return typeof input.file_path === "string" ? input.file_path : "";
    case "Bash":
      return typeof input.command === "string"
        ? input.command.length > 120
          ? input.command.slice(0, 120) + "..."
          : input.command
        : "";
    case "Glob":
      return typeof input.pattern === "string" ? input.pattern : "";
    case "Grep":
      return typeof input.pattern === "string" ? input.pattern : "";
    case "TodoWrite":
      return "Updating task list";
    case "WebSearch":
      return typeof input.query === "string" ? input.query : "";
    case "WebFetch":
      return typeof input.url === "string" ? input.url : "";
    default:
      if (typeof input.file_path === "string") return input.file_path;
      if (typeof input.command === "string") return input.command;
      if (typeof input.pattern === "string") return input.pattern;
      return "";
  }
}

const ToolUseBlock = React.memo(function ToolUseBlock({ message }: Props) {
  const detail = getToolDetail(message.tool, message.input);

  return (
    <div
      className={`self-start max-w-[85%] border-l-[3px] border-l-primary rounded-r-lg px-3 py-2 bg-primary/5 ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      <div className="text-xs font-semibold text-primary">
        {message.tool}
      </div>
      {detail && (
        <div className="text-xs text-text2 font-[family-name:var(--font-jetbrains)] mt-0.5 truncate">
          {detail}
        </div>
      )}
    </div>
  );
});

export default ToolUseBlock;
