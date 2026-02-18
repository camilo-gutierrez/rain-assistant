"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { AgentStatus } from "@/lib/types";
import ModeToggle from "@/components/computer-use/ModeToggle";
import { X, Plus } from "lucide-react";

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

  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const agentEntries = Object.values(agents);
  const canClose = agentEntries.length > 1;

  const updateScrollIndicators = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateScrollIndicators();
    el.addEventListener("scroll", updateScrollIndicators, { passive: true });
    const ro = new ResizeObserver(updateScrollIndicators);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", updateScrollIndicators);
      ro.disconnect();
    };
  }, [updateScrollIndicators, agentEntries.length]);

  const handleNewAgent = () => {
    const newId = createAgent();
    switchToAgent(newId);
    setActivePanel("fileBrowser");
  };

  return (
    <nav className="relative flex items-center bg-surface border-b border-overlay">
      {/* Left scroll fade indicator */}
      {canScrollLeft && (
        <div className="absolute left-0 top-0 bottom-0 w-6 bg-gradient-to-r from-surface to-transparent z-10 pointer-events-none" />
      )}

      {/* Scrollable tabs container */}
      <div
        ref={scrollRef}
        className="flex items-center overflow-x-auto scrollbar-none flex-1"
      >
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

              {/* Close button — always semi-visible on mobile, hover-revealed on desktop */}
              {canClose && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeAgent(agent.id, send);
                  }}
                  className="ml-0.5 min-w-[32px] min-h-[32px] flex items-center justify-center rounded-full text-subtext hover:text-red hover:bg-red/10 opacity-60 sm:opacity-0 sm:group-hover:opacity-100 transition-all"
                  title="Close"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Right scroll fade indicator */}
      {canScrollRight && (
        <div className="absolute right-[calc(2.5rem+40px)] top-0 bottom-0 w-6 bg-gradient-to-l from-surface to-transparent z-10 pointer-events-none" />
      )}

      {/* Mode toggle */}
      <ModeToggle />

      {/* New agent button */}
      <button
        onClick={handleNewAgent}
        className="shrink-0 w-9 h-9 mx-2 flex items-center justify-center rounded-full text-subtext hover:bg-primary/10 hover:text-primary transition-colors"
        title={t("btn.newAgent.title")}
      >
        <Plus size={18} />
      </button>
    </nav>
  );
}
