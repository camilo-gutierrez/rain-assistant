"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import { useTranslation } from "@/hooks/useTranslation";
import EmergencyStopButton from "./EmergencyStopButton";

export default function ComputerUseToolbar() {
  const agent = useAgentStore((s) =>
    s.activeAgentId ? s.agents[s.activeAgentId] : null
  );
  const { t } = useTranslation();

  if (!agent || agent.mode !== "computer_use") return null;

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-purple/5 border-b border-purple/20">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-purple">
          🖥️ {t("cu.title")}
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
      </div>
      <EmergencyStopButton />
    </div>
  );
}
