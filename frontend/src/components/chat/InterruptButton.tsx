"use client";

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

  // Only visible when processing
  if (!isProcessing || !activeAgentId) return null;

  // Determine state: normal stop, stopping, or force stop
  const isForceMode = interruptPending && interruptTimerId === null;
  const isStopping = interruptPending && interruptTimerId !== null;

  const handleClick = () => {
    if (!activeAgentId) return;

    if (isForceMode) {
      // Force stop: reset client-side processing state
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

    // Normal stop: send interrupt
    send({ type: "interrupt", agent_id: activeAgentId });
    setInterruptPending(activeAgentId, true);

    // Start 5s timer for force stop mode
    const timerId = setTimeout(() => {
      // After 5s, clear the timer to enable force mode
      setInterruptTimer(activeAgentId, null);
    }, 5000);

    setInterruptTimer(activeAgentId, timerId);
  };

  let buttonText: string;
  let buttonClass: string;

  if (isForceMode) {
    buttonText = t("chat.forceStop");
    buttonClass =
      "border-yellow text-yellow animate-neon-pulse-yellow";
  } else if (isStopping) {
    buttonText = t("chat.stopping");
    buttonClass =
      "bg-overlay text-subtext cursor-wait border-overlay";
  } else {
    buttonText = t("chat.stop");
    buttonClass =
      "border-red text-red animate-neon-pulse-red";
  }

  return (
    <button
      onClick={handleClick}
      disabled={isStopping}
      className={`px-5 py-3 rounded-lg font-[family-name:var(--font-orbitron)] text-xs font-bold uppercase tracking-wider border transition-all shrink-0 ${buttonClass}`}
      style={
        isForceMode
          ? { background: "linear-gradient(135deg, rgba(255,204,0,0.15), rgba(255,204,0,0.05))" }
          : isStopping
          ? undefined
          : { background: "linear-gradient(135deg, rgba(255,34,102,0.15), rgba(255,34,102,0.05))" }
      }
    >
      {buttonText}
    </button>
  );
}
