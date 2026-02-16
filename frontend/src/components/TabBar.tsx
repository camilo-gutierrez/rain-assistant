"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { AgentStatus } from "@/lib/types";
import ModeToggle from "@/components/computer-use/ModeToggle";

function statusDotClass(status: AgentStatus): string {
  switch (status) {
    case "idle":
      return "bg-green";
    case "working":
      return "bg-primary animate-pulse";
    case "done":
      return "bg-green";
    case "error":
      return "bg-red";
    default:
      return "bg-subtext";
  }
}

function folderName(cwd: string | null, label: string): string {
  if (!cwd) return label;
  const parts = cwd.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts[parts.length - 1] || label;
}

export default function TabBar() {
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const switchToAgent = useAgentStore((s) => s.switchToAgent);
  const closeAgent = useAgentStore((s) => s.closeAgent);
  const createAgent = useAgentStore((s) => s.createAgent);
  const send = useConnectionStore((s) => s.send);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const { t } = useTranslation();

  const agentEntries = Object.values(agents);
  const canClose = agentEntries.length > 1;

  const handleNewAgent = () => {
    const newId = createAgent();
    switchToAgent(newId);
    setActivePanel("fileBrowser");
  };

  return (
    <nav className="flex items-center bg-surface border-b border-overlay overflow-x-auto scrollbar-none">
      {agentEntries.map((agent) => {
        const isActive = agent.id === activeAgentId;
        return (
          <div
            key={agent.id}
            onClick={() => switchToAgent(agent.id)}
            className={`group relative flex items-center gap-2 px-4 py-2.5 cursor-pointer transition-colors select-none shrink-0 border-b-2 ${
              isActive
                ? "border-b-primary text-text bg-surface2/50"
                : "border-b-transparent text-text2 hover:bg-surface2/30 hover:text-text"
            }`}
          >
            {/* Status dot */}
            <div
              className={`w-2 h-2 rounded-full shrink-0 ${statusDotClass(agent.status)}`}
            />

            {/* Label */}
            <span className={`text-sm truncate max-w-[140px] ${isActive ? "font-medium" : ""}`}>
              {folderName(agent.cwd, agent.label)}
            </span>

            {/* Unread badge */}
            {agent.unread > 0 && !isActive && (
              <span className="min-w-[18px] h-[18px] flex items-center justify-center px-1 rounded-full bg-primary text-on-primary text-[10px] font-bold animate-fade-in">
                {agent.unread > 99 ? "99+" : agent.unread}
              </span>
            )}

            {/* Close button */}
            {canClose && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeAgent(agent.id, send);
                }}
                className="ml-0.5 w-5 h-5 flex items-center justify-center rounded-full text-subtext hover:text-red hover:bg-red/10 opacity-0 group-hover:opacity-100 transition-all text-xs"
                title="Close"
              >
                &times;
              </button>
            )}
          </div>
        );
      })}

      {/* Mode toggle */}
      <ModeToggle />

      {/* New agent button */}
      <button
        onClick={handleNewAgent}
        className="shrink-0 w-8 h-8 mx-2 flex items-center justify-center rounded-full text-subtext hover:bg-primary/10 hover:text-primary transition-colors text-lg"
        title={t("btn.newAgent.title")}
      >
        +
      </button>
    </nav>
  );
}
