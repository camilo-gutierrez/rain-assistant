"use client";

import { useState, useRef } from "react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";

export default function ChatInput() {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const appendMessage = useAgentStore((s) => s.appendMessage);
  const setProcessing = useAgentStore((s) => s.setProcessing);
  const setAgentStatus = useAgentStore((s) => s.setAgentStatus);
  const send = useConnectionStore((s) => s.send);
  const { t } = useTranslation();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const isProcessing = activeAgent?.isProcessing || false;
  const hasCwd = !!activeAgent?.cwd;

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || !activeAgentId || !hasCwd || isProcessing) return;

    appendMessage(activeAgentId, {
      id: crypto.randomUUID(),
      type: "user",
      text: trimmed,
      timestamp: Date.now(),
      animate: true,
    });

    const sent = send({
      type: "send_message",
      text: trimmed,
      agent_id: activeAgentId,
    });

    if (sent) {
      setProcessing(activeAgentId, true);
      setAgentStatus(activeAgentId, "working");
      setText("");
    } else {
      appendMessage(activeAgentId, {
        id: crypto.randomUUID(),
        type: "system",
        text: t("chat.sendError"),
        timestamp: Date.now(),
        animate: true,
      });
    }

    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex items-center gap-2 px-4 py-3 bg-surface border-t border-overlay">
      <input
        ref={inputRef}
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t("chat.inputPlaceholder")}
        disabled={isProcessing || !hasCwd}
        className="flex-1 bg-surface2 text-text border border-overlay rounded-full px-4 py-2.5 text-sm placeholder:text-subtext focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <button
        onClick={handleSend}
        disabled={!text.trim() || isProcessing || !hasCwd}
        className="w-10 h-10 flex items-center justify-center rounded-full bg-primary text-on-primary transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:bg-primary-dark shrink-0"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
  );
}
