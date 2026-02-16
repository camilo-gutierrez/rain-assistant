"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTTS, useTTSStore } from "@/hooks/useTTS";
import { useSettingsStore } from "@/stores/useSettingsStore";
import type { UserMessage, AssistantMessage, SystemMessage } from "@/lib/types";

interface Props {
  message: UserMessage | AssistantMessage | SystemMessage;
}

const MessageBubble = React.memo(function MessageBubble({ message }: Props) {
  const { play, stop } = useTTS();
  const ttsEnabled = useSettingsStore((s) => s.ttsEnabled);
  const playbackState = useTTSStore((s) => s.playbackState);
  const playingMessageId = useTTSStore((s) => s.playingMessageId);

  if (message.type === "system") {
    return (
      <div
        className={`text-center italic text-xs text-subtext py-1 ${
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
        className={`self-end max-w-[85%] rounded-2xl rounded-br-sm px-4 py-2.5 bg-primary text-on-primary ${
          message.animate ? "animate-msg-appear" : ""
        }`}
      >
        <p className="text-sm whitespace-pre-wrap break-words">
          {message.text}
        </p>
      </div>
    );
  }

  // Assistant message
  const assistantMsg = message as AssistantMessage;
  const isThisPlaying = playingMessageId === message.id;
  const isLoading = isThisPlaying && playbackState === "loading";
  const isPlaying = isThisPlaying && playbackState === "playing";

  return (
    <div
      className={`self-start max-w-[85%] bg-surface rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      {assistantMsg.isStreaming ? (
        <div className="text-sm text-text whitespace-pre-wrap break-words">
          {assistantMsg.text}
          <span className="inline-block w-1.5 h-4 bg-primary ml-0.5 animate-pulse" />
        </div>
      ) : (
        <>
          <div className="text-sm text-text prose prose-sm max-w-none break-words [&_pre]:bg-surface2 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_code]:font-[family-name:var(--font-jetbrains)] [&_code]:text-primary [&_pre_code]:text-text [&_a]:text-primary [&_a]:no-underline hover:[&_a]:underline [&_table]:border-overlay [&_th]:border-overlay [&_td]:border-overlay [&_blockquote]:border-l-primary/30 [&_blockquote]:text-text2">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {assistantMsg.text}
            </ReactMarkdown>
          </div>

          {ttsEnabled && assistantMsg.text.trim() && (
            <button
              onClick={() =>
                isPlaying || isLoading
                  ? stop()
                  : play(assistantMsg.text, message.id)
              }
              className={`mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md border transition-all ${
                isPlaying
                  ? "border-primary text-primary"
                  : isLoading
                  ? "border-overlay text-subtext cursor-wait"
                  : "border-overlay text-subtext hover:text-primary hover:border-primary"
              }`}
            >
              <svg
                className={`w-3 h-3 ${isPlaying ? "animate-pulse" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                {isPlaying || isLoading ? (
                  <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" stroke="none" />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.536 8.464a5 5 0 010 7.072M17.95 6.05a8 8 0 010 11.9M6.5 8.788V15.21a1 1 0 00.553.894l5 2.5A1 1 0 0013.5 17.71V6.29a1 1 0 00-1.447-.894l-5 2.5A1 1 0 006.5 8.79z"
                  />
                )}
              </svg>
              {isLoading && (
                <span className="animate-pulse">...</span>
              )}
            </button>
          )}
        </>
      )}
    </div>
  );
});

export default MessageBubble;
