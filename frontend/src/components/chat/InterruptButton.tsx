"use client";

import { Square, OctagonX } from "lucide-react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";

export default function InterruptButton() {
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const setInterruptPending = useAgentStore((s) => s.setInterruptPending);
  const setInterruptTimer = useAgentStore((s) => s.setInterruptTimer);
  const setProcessing = useAgentStore((s) => s.setProcessing);
  const setAgentStatus = useAgentStore((s) => s.setAgentStatus);
  const appendMessage = useAgentStore((s) => s.appendMessage);
  const finalizeStreaming = useAgentStore((s) => s.finalizeStreaming);
  const send = useConnectionStore((s) => s.send);
  const { t } = useTranslation();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const isProcessing = activeAgent?.isProcessing || false;
  const interruptPending = activeAgent?.interruptPending || false;
  const interruptTimerId = activeAgent?.interruptTimerId || null;

  if (!isProcessing || !activeAgentId) return null;

  const isForceMode = interruptPending && interruptTimerId === null;
  const isStopping = interruptPending && interruptTimerId !== null;

  const handleClick = () => {
    if (!activeAgentId) return;

    if (isForceMode) {
      finalizeStreaming(activeAgentId);
      setProcessing(activeAgentId, false);
      setInterruptPending(activeAgentId, false);
      setAgentStatus(activeAgentId, "idle");
      appendMessage(activeAgentId, {
        id: crypto.randomUUID(),
        type: "system",
        text: t("chat.forceStopped"),
        timestamp: Date.now(),
        animate: true,
      });
      return;
    }

    send({ type: "interrupt", agent_id: activeAgentId });
    setInterruptPending(activeAgentId, true);

    const timerId = setTimeout(() => {
      setInterruptTimer(activeAgentId, null);
    }, 5000);

    setInterruptTimer(activeAgentId, timerId);
  };

  let buttonText: string;
  let buttonClass: string;

  if (isForceMode) {
    buttonText = t("chat.forceStop");
    buttonClass = "bg-yellow/10 text-yellow border-yellow/30 hover:bg-yellow/20";
  } else if (isStopping) {
    buttonText = t("chat.stopping");
    buttonClass = "bg-surface2 text-subtext border-overlay cursor-wait";
  } else {
    buttonText = t("chat.stop");
    buttonClass = "bg-red/10 text-red border-red/30 hover:bg-red/20";
  }

  return (
    <div className="flex items-center justify-center py-2">
      <button
        onClick={handleClick}
        disabled={isStopping}
        className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium border transition-all focus-ring ${buttonClass}`}
      >
        {isForceMode ? <OctagonX size={16} /> : <Square size={14} fill="currentColor" />}
        {buttonText}
      </button>
      <span className="ml-2 text-[11px] text-subtext hidden sm:inline">Esc</span>
    </div>
  );
}
