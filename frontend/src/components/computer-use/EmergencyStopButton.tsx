"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";

export default function EmergencyStopButton() {
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const agent = useAgentStore((s) =>
    s.activeAgentId ? s.agents[s.activeAgentId] : null
  );
  const send = useConnectionStore((s) => s.send);
  const { t } = useTranslation();

  if (!agent || !activeAgentId || agent.mode !== "computer_use" || !agent.isProcessing) {
    return null;
  }

  const handleEmergencyStop = () => {
    send({ type: "emergency_stop", agent_id: activeAgentId });
    useAgentStore.getState().setProcessing(activeAgentId, false);
    useAgentStore.getState().setAgentStatus(activeAgentId, "idle");
  };

  return (
    <button
      onClick={handleEmergencyStop}
      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red text-white font-bold text-sm hover:bg-red/80 transition-colors animate-pulse shadow-lg"
    >
      <span className="text-lg">⚠️</span>
      {t("cu.emergencyStop")}
    </button>
  );
}
