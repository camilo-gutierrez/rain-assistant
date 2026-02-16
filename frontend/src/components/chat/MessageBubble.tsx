"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { UserMessage, AssistantMessage, SystemMessage } from "@/lib/types";

interface Props {
  message: UserMessage | AssistantMessage | SystemMessage;
}

const MessageBubble = React.memo(function MessageBubble({ message }: Props) {
  if (message.type === "system") {
    return (
      <div
        className={`text-center italic text-xs text-subtext font-[family-name:var(--font-jetbrains)] py-1 ${
          message.animate ? "animate-msg-appear" : ""
        }`}
      >
        {message.text}
      </div>
    );
  }

  if (message.type === "user") {
    return (
      <div
        className={`self-end max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 ${
          message.animate ? "animate-msg-appear" : ""
        }`}
        style={{
          background: "linear-gradient(135deg, rgba(0,212,255,0.15), rgba(191,90,242,0.15))",
        }}
      >
        <p className="text-sm text-text whitespace-pre-wrap break-words">
          {message.text}
        </p>
      </div>
    );
  }

  // Assistant message
  const assistantMsg = message as AssistantMessage;

  return (
    <div
      className={`self-start max-w-[85%] bg-surface rounded-2xl rounded-bl-md px-4 py-2.5 border border-overlay/50 ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      {assistantMsg.isStreaming ? (
        // During streaming, render raw text for performance
        <div className="text-sm text-text whitespace-pre-wrap break-words font-[family-name:var(--font-jetbrains)]">
          {assistantMsg.text}
          <span className="inline-block w-1.5 h-4 bg-cyan ml-0.5 animate-pulse" />
        </div>
      ) : (
        // After streaming, render markdown
        <div className="text-sm text-text prose prose-invert prose-sm max-w-none break-words [&_pre]:bg-surface2 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_code]:font-[family-name:var(--font-jetbrains)] [&_code]:text-cyan [&_pre_code]:text-text [&_a]:text-cyan [&_a]:no-underline hover:[&_a]:underline [&_table]:border-overlay [&_th]:border-overlay [&_td]:border-overlay [&_blockquote]:border-l-mauve [&_blockquote]:text-text2">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {assistantMsg.text}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
});

export default MessageBubble;
