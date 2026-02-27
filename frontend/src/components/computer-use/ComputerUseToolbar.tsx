"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import EmergencyStopButton from "./EmergencyStopButton";
import MonitorSelector from "./MonitorSelector";

export default function ComputerUseToolbar() {
  const agent = useAgentStore((s) =>
    s.activeAgentId ? s.agents[s.activeAgentId] : null
  );
  const send = useConnectionStore((s) => s.send);
  const { t } = useTranslation();

  if (!agent || agent.mode !== "computer_use") return null;

  const monitorCount = agent.displayInfo?.monitor_count ?? 0;
  const monitorIndex = agent.displayInfo?.monitor_index ?? 1;

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-purple/5 border-b border-purple/20">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-purple">
          {t("cu.title")}
        </span>
        {agent.displayInfo && (
          <span className="text-xs text-subtext">
            {agent.displayInfo.screen_width}x{agent.displayInfo.screen_height}
          </span>
        )}
        {agent.computerIteration > 0 && (
          <span className="text-xs text-subtext px-2 py-0.5 rounded-full bg-surface2">
            {t("cu.iteration")} {agent.computerIteration}/{50}
          </span>
        )}
        {monitorCount > 1 && agent.monitors && (
          <MonitorSelector
            monitors={agent.monitors}
            currentIndex={monitorIndex}
            onSelect={(index) => {
              const agentId = useAgentStore.getState().activeAgentId;
              if (agentId) send({ type: "set_monitor", agent_id: agentId, monitor_index: index });
            }}
          />
        )}
      </div>
      <EmergencyStopButton />
    </div>
  );
}
