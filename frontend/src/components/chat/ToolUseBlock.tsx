"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
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
  const [expanded, setExpanded] = useState(false);
  const detail = getToolDetail(message.tool, message.input);
  const hasInput = Object.keys(message.input).length > 0;

  return (
    <div
      className={`self-start max-w-[85%] border-l-[3px] border-l-primary rounded-r-lg px-3 py-2 bg-primary/5 ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-semibold text-primary shrink-0">
            {message.tool}
          </span>
          {!expanded && detail && (
            <span className="text-xs text-text2 font-mono truncate">
              {detail.length > 80 ? detail.slice(0, 80) + "..." : detail}
            </span>
          )}
        </div>
        {hasInput && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center text-subtext hover:text-primary transition-colors shrink-0 rounded-md hover:bg-surface2/60"
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>
      {expanded && (
        <pre className="mt-1.5 text-xs text-text2 font-mono whitespace-pre-wrap break-words bg-surface2/40 rounded-md p-2 max-h-[300px] overflow-y-auto">
          {JSON.stringify(message.input, null, 2)}
        </pre>
      )}
    </div>
  );
});

export default ToolUseBlock;
