"use client";

import React, { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import { Copy, Check, AlertTriangle } from "lucide-react";
import { useTTS, useTTSStore } from "@/hooks/useTTS";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useToastStore } from "@/stores/useToastStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { UserMessage, AssistantMessage, SystemMessage } from "@/lib/types";

const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    // Allow class for syntax highlighting
    code: [...(defaultSchema.attributes?.code || []), 'className'],
    span: [...(defaultSchema.attributes?.span || []), 'className', 'style'],
  },
  // Block dangerous protocols
  protocols: {
    ...defaultSchema.protocols,
    href: ['http', 'https', 'mailto'],
    src: ['http', 'https'],
  },
  // Explicitly block script, iframe, object, embed, form
  tagNames: (defaultSchema.tagNames || []).filter(
    (tag: string) => !['script', 'iframe', 'object', 'embed', 'form', 'input', 'textarea', 'select', 'button'].includes(tag)
  ),
}

interface Props {
  message: UserMessage | AssistantMessage | SystemMessage;
}

const MessageBubble = React.memo(function MessageBubble({ message }: Props) {
  const [copied, setCopied] = useState(false);
  const { play, stop } = useTTS();
  const ttsEnabled = useSettingsStore((s) => s.ttsEnabled);
  const playbackState = useTTSStore((s) => s.playbackState);
  const playingMessageId = useTTSStore((s) => s.playingMessageId);
  const addToast = useToastStore((s) => s.addToast);
  const { t } = useTranslation();

  const handleCopy = useCallback(async () => {
    if (copied) return;
    try {
      await navigator.clipboard.writeText((message as AssistantMessage).text);
      setCopied(true);
      addToast({ type: "success", message: t("toast.copySuccess"), duration: 2000 });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API may fail silently
    }
  }, [copied, message, addToast, t]);

  if (message.type === "system") {
    const isError = message.text.toLowerCase().startsWith("error") || message.text.includes("Error:");
    const isMeta = /^\d+\.?\d*s\s*\|/.test(message.text);
    const animClass = message.animate ? "animate-msg-appear" : "";

    if (isError) {
      return (
        <div className={`self-start flex items-start gap-2 bg-red/8 border border-red/20 rounded-lg px-3 py-2 ${animClass}`}>
          <AlertTriangle size={14} className="text-red mt-0.5 shrink-0" />
          <span className="text-xs text-red break-words">{message.text}</span>
        </div>
      );
    }

    if (isMeta) {
      return (
        <div className={`self-center bg-surface2/60 rounded-full px-3 py-1 ${animClass}`}>
          <span className="text-[11px] text-subtext tabular-nums">{message.text}</span>
        </div>
      );
    }

    return (
      <div className={`self-center bg-surface2/40 rounded-full px-4 py-1.5 ${animClass}`}>
        <span className="text-xs text-subtext">{message.text}</span>
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
      className={`group relative self-start max-w-[85%] bg-surface rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm ${
        message.animate ? "animate-msg-appear" : ""
      }`}
    >
      {/* Copy button — desktop: visible on hover, touch: always visible */}
      {!assistantMsg.isStreaming && assistantMsg.text.trim() && (
        <button
          onClick={handleCopy}
          className="absolute top-1.5 right-1.5 min-w-[32px] min-h-[32px] flex items-center justify-center rounded-md border border-overlay bg-surface text-subtext hover:text-primary hover:border-primary transition-all opacity-0 group-hover:opacity-100 touch-visible"
          aria-label="Copy"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      )}

      {assistantMsg.isStreaming ? (
        <div className="text-sm text-text whitespace-pre-wrap break-words">
          {assistantMsg.text}
          <span className="inline-block w-1.5 h-4 bg-primary ml-0.5 animate-pulse" />
        </div>
      ) : (
        <>
          <div className="text-sm text-text prose prose-sm max-w-none break-words overflow-hidden [&_pre]:bg-surface2 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_pre]:text-xs [&_code]:font-[family-name:var(--font-jetbrains)] [&_code]:text-primary [&_pre_code]:text-text [&_a]:text-primary [&_a]:no-underline hover:[&_a]:underline [&_table]:border-overlay [&_th]:border-overlay [&_td]:border-overlay [&_table]:block [&_table]:overflow-x-auto [&_table]:max-w-full [&_blockquote]:border-l-primary/30 [&_blockquote]:text-text2 [&_img]:max-w-full [&_img]:h-auto">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
            >
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
