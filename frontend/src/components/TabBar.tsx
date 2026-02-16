"use client";

import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { AgentStatus } from "@/lib/types";

function statusDotClass(status: AgentStatus): string {
  switch (status) {
    case "idle":
      return "bg-green shadow-[0_0_4px_var(--green)]";
    case "working":
      return "bg-cyan animate-dot-pulse-cyan";
    case "done":
      return "bg-green animate-dot-flash-green";
    case "error":
      return "bg-red animate-dot-pulse-red";
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
    // New agent defaults to "fileBrowser" panel — sync UI to match
    setActivePanel("fileBrowser");
  };

  return (
    <nav className="relative flex items-center bg-bg border-b border-overlay overflow-x-auto scrollbar-none">
      {/* Neon underline */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px opacity-40"
        style={{
          background: "linear-gradient(90deg, var(--cyan), var(--magenta))",
        }}
      />

      {/* Tabs */}
      {agentEntries.map((agent) => {
        const isActive = agent.id === activeAgentId;
        return (
          <div
            key={agent.id}
            onClick={() => switchToAgent(agent.id)}
            className={`group relative flex items-center gap-1.5 px-3 py-2 rounded-t-lg cursor-pointer transition-colors select-none shrink-0 ${
              isActive
                ? "bg-surface border border-b-0 border-overlay"
                : "hover:bg-surface2/50"
            }`}
          >
            {/* Neon top edge for active tab */}
            {isActive && (
              <div
                className="absolute top-0 left-0 right-0 h-0.5 rounded-t-lg"
                style={{
                  background: "linear-gradient(90deg, var(--cyan), var(--magenta))",
                }}
              />
            )}

            {/* Status dot */}
            <div
              className={`w-[7px] h-[7px] rounded-full shrink-0 ${statusDotClass(agent.status)}`}
            />

            {/* Label */}
            <span
              className={`font-[family-name:var(--font-jetbrains)] text-xs truncate max-w-[120px] ${
                isActive ? "text-text" : "text-text2"
              }`}
            >
              {folderName(agent.cwd, agent.label)}
            </span>

            {/* Unread badge */}
            {agent.unread > 0 && !isActive && (
              <span className="min-w-[16px] h-4 flex items-center justify-center px-1 rounded-full bg-magenta text-white text-[10px] font-bold animate-badge-pop">
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
                className="ml-1 w-4 h-4 flex items-center justify-center rounded text-subtext hover:text-red hover:bg-red/10 opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                title="Close"
              >
                &times;
              </button>
            )}
          </div>
        );
      })}

      {/* New agent "+" button */}
      <button
        onClick={handleNewAgent}
        className="shrink-0 w-8 h-8 mx-1 flex items-center justify-center rounded border border-dashed border-overlay text-subtext hover:border-cyan hover:text-cyan transition-colors text-lg"
        title={t("btn.newAgent.title")}
      >
        +
      </button>
    </nav>
  );
}
