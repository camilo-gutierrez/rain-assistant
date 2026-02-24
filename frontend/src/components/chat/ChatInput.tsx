"use client";

import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useToastStore } from "@/stores/useToastStore";
import { useTranslation } from "@/hooks/useTranslation";

export default function ChatInput() {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  const isDisabled = isProcessing || !hasCwd;

  const adjustHeight = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newHeight = Math.min(el.scrollHeight, 200);
    el.style.height = newHeight + "px";
    el.style.overflowY = el.scrollHeight > 200 ? "auto" : "hidden";
  };

  useEffect(() => {
    adjustHeight();
  }, [text]);

  // Scroll textarea into view when mobile keyboard opens
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const handleResize = () => {
      textareaRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    vv.addEventListener("resize", handleResize);
    return () => vv.removeEventListener("resize", handleResize);
  }, []);

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

      useToastStore.getState().addToast({
        type: "error",
        message: t("toast.sendFailed"),
      });
    }

    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex items-end gap-2">
      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t("chat.inputPlaceholder")}
        disabled={isDisabled}
        enterKeyHint="send"
        autoComplete="off"
        className={`flex-1 bg-surface2 text-text border border-overlay rounded-2xl px-4 py-2.5 text-base sm:text-sm min-h-[44px] max-h-[200px] resize-none overflow-y-hidden placeholder:text-subtext focus-ring transition-all disabled:opacity-50 disabled:cursor-not-allowed`}
      />
      <button
        onClick={handleSend}
        disabled={!text.trim() || isProcessing || !hasCwd}
        className="min-w-[44px] min-h-[44px] w-11 h-11 flex items-center justify-center rounded-full bg-primary text-on-primary transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-dark shrink-0"
      >
        <Send size={18} />
      </button>
    </div>
  );
}
