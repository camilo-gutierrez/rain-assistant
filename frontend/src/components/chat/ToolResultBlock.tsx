"use client";

import React, { useState } from "react";
import type { ToolResultMessage } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";

interface Props {
  message: ToolResultMessage;
}

const TRUNCATE_AT = 300;

const ToolResultBlock = React.memo(function ToolResultBlock({ message }: Props) {
  const [expanded, setExpanded] = useState(false);
  const { t } = useTranslation();

  const isTruncated = message.content.length > TRUNCATE_AT;
  const displayText = expanded
    ? message.content
    : message.content.slice(0, TRUNCATE_AT);

  const borderColor = message.isError ? "border-l-red" : "border-l-green";
  const bgClass = message.isError ? "bg-red/5" : "bg-green/5";

  return (
    <div
      className={`self-start max-w-[85%] border-l-[3px] ${borderColor} rounded-r-lg px-3 py-2 ${bgClass} ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      <pre className="text-xs text-text2 font-[family-name:var(--font-jetbrains)] whitespace-pre-wrap break-words max-h-[120px] overflow-y-auto">
        {displayText}
        {isTruncated && !expanded && "..."}
      </pre>

      {isTruncated && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-1 text-[10px] text-primary hover:underline"
        >
          {t("chat.showFullOutput")}
        </button>
      )}
    </div>
  );
});

export default ToolResultBlock;
