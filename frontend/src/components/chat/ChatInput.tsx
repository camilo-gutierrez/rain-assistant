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

    // Append user message to store
    appendMessage(activeAgentId, {
      id: crypto.randomUUID(),
      type: "user",
      text: trimmed,
      timestamp: Date.now(),
      animate: true,
    });

    // Send via WebSocket
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
      // WebSocket not connected — remove the optimistic message
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
    <div className="flex items-center gap-2 px-4 py-2 bg-surface border-t border-overlay">
      <input
        ref={inputRef}
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t("chat.inputPlaceholder")}
        disabled={isProcessing || !hasCwd}
        className="flex-1 bg-surface2 text-text border border-cyan/20 rounded-lg px-4 py-2.5 text-sm placeholder:text-subtext focus:outline-none focus:border-cyan focus:shadow-[0_0_12px_var(--neon-glow)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <button
        onClick={handleSend}
        disabled={!text.trim() || isProcessing || !hasCwd}
        className="px-5 py-2.5 rounded-lg font-[family-name:var(--font-orbitron)] text-xs font-bold uppercase tracking-wider border transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-[0_0_16px_rgba(0,255,136,0.3)]"
        style={{
          borderImage: "linear-gradient(135deg, var(--green), var(--cyan)) 1",
          color: "var(--green)",
        }}
      >
        {t("chat.sendBtn")}
      </button>
    </div>
  );
}
