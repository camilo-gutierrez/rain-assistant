"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { AgentMode } from "@/lib/types";

export default function ModeToggle() {
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const agent = useAgentStore((s) =>
    s.activeAgentId ? s.agents[s.activeAgentId] : null
  );
  const send = useConnectionStore((s) => s.send);
  const { t } = useTranslation();

  if (!agent || !activeAgentId || !agent.cwd) return null;

  const mode = agent.mode;
  const isComputerUse = mode === "computer_use";

  const handleToggle = () => {
    const newMode: AgentMode = isComputerUse ? "coding" : "computer_use";
    send({ type: "set_mode", agent_id: activeAgentId, mode: newMode });
  };

  return (
    <button
      onClick={handleToggle}
      className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 mx-1 rounded-full text-xs font-medium transition-all ${
        isComputerUse
          ? "bg-purple/15 text-purple border border-purple/30 hover:bg-purple/25"
          : "bg-surface2/50 text-subtext border border-overlay hover:bg-surface2 hover:text-text"
      }`}
      title={isComputerUse ? t("cu.switchToCoding") : t("cu.switchToComputerUse")}
    >
      {isComputerUse ? (
        <>
          <span>🖥️</span>
          <span className="hidden sm:inline">{t("cu.modeComputer")}</span>
        </>
      ) : (
        <>
          <span>💻</span>
          <span className="hidden sm:inline">{t("cu.modeCoding")}</span>
        </>
      )}
    </button>
  );
}
