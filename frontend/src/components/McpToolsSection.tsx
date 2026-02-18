"use client";

import { useState } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { ChevronDown, ChevronUp, Plug, Mail, Globe, Home } from "lucide-react";

interface McpCategory {
  id: string;
  labelKey: string;
  icon: React.ReactNode;
  toolCount: number;
  prompt: string;
  color: string;
  bg: string;
  border: string;
  hoverBg: string;
}

const mcpCategories: McpCategory[] = [
  {
    id: "hub",
    labelKey: "mcp.hub",
    toolCount: 3,
    prompt: "Muéstrame el menú de Rain con todas las capacidades disponibles",
    color: "text-primary",
    bg: "bg-primary/6",
    border: "border-primary/10",
    hoverBg: "hover:bg-primary/12",
    icon: <Plug size={18} strokeWidth={1.8} />,
  },
  {
    id: "email",
    labelKey: "mcp.email",
    toolCount: 8,
    prompt: "Quiero usar las funciones de email. Muéstrame qué puedo hacer con el correo.",
    color: "text-green",
    bg: "bg-green/6",
    border: "border-green/10",
    hoverBg: "hover:bg-green/12",
    icon: <Mail size={18} strokeWidth={1.8} />,
  },
  {
    id: "browser",
    labelKey: "mcp.browser",
    toolCount: 11,
    prompt: "Quiero navegar por la web. Muéstrame qué puedo hacer con el navegador.",
    color: "text-cyan",
    bg: "bg-cyan/6",
    border: "border-cyan/10",
    hoverBg: "hover:bg-cyan/12",
    icon: <Globe size={18} strokeWidth={1.8} />,
  },
  {
    id: "smarthome",
    labelKey: "mcp.smarthome",
    toolCount: 10,
    prompt: "Quiero controlar mi smart home. Muéstrame los dispositivos disponibles.",
    color: "text-mauve",
    bg: "bg-mauve/6",
    border: "border-mauve/10",
    hoverBg: "hover:bg-mauve/12",
    icon: <Home size={18} strokeWidth={1.8} />,
  },
];

const MCP_COLLAPSED_KEY = "rain-mcp-collapsed";

function getInitialCollapsed(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const stored = localStorage.getItem(MCP_COLLAPSED_KEY);
    return stored === null ? true : stored === "true";
  } catch {
    return true;
  }
}

export default function McpToolsSection() {
  const [collapsed, setCollapsed] = useState(getInitialCollapsed);
  const send = useConnectionStore((s) => s.send);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const agents = useAgentStore((s) => s.agents);
  const appendMessage = useAgentStore((s) => s.appendMessage);
  const setProcessing = useAgentStore((s) => s.setProcessing);
  const setAgentStatus = useAgentStore((s) => s.setAgentStatus);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const { t } = useTranslation();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const hasCwd = !!activeAgent?.cwd;
  const isProcessing = activeAgent?.isProcessing || false;

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(MCP_COLLAPSED_KEY, String(next));
      } catch { /* ignore */ }
      return next;
    });
  };

  const handleToolClick = (category: McpCategory) => {
    if (!activeAgentId || !hasCwd || isProcessing) return;

    setActivePanel("chat");

    appendMessage(activeAgentId, {
      id: crypto.randomUUID(),
      type: "user",
      text: category.prompt,
      timestamp: Date.now(),
      animate: true,
    });

    const sent = send({
      type: "send_message",
      text: category.prompt,
      agent_id: activeAgentId,
    });

    if (sent) {
      setProcessing(activeAgentId, true);
      setAgentStatus(activeAgentId, "working");
    }
  };

  const totalTools = mcpCategories.reduce((sum, c) => sum + c.toolCount, 0);

  return (
    <div className="px-1 py-1">
      {/* Collapsible section header */}
      <button
        onClick={toggleCollapsed}
        className="flex items-center gap-2 px-2 py-1.5 mb-1.5 w-full group cursor-pointer rounded-lg hover:bg-surface2/40 transition-colors"
      >
        <span className="text-[10px] uppercase tracking-widest text-subtext font-semibold group-hover:text-text transition-colors">
          {t("mcp.title")}
        </span>
        <div className="flex-1 h-px bg-gradient-to-r from-overlay/40 to-transparent" />
        <span className="text-[10px] font-bold text-primary bg-primary/8 px-1.5 py-0.5 rounded-md tabular-nums">
          {totalTools}
        </span>
        <span className="text-subtext group-hover:text-text transition-colors">
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </span>
      </button>

      {/* 2x2 grid of MCP category cards */}
      {!collapsed && (
        <div className="grid grid-cols-2 gap-1.5 animate-fade-in">
          {mcpCategories.map((category) => (
            <button
              key={category.id}
              onClick={() => handleToolClick(category)}
              disabled={!hasCwd || isProcessing}
              className={`
                group relative flex flex-col items-center gap-1.5 p-2.5 rounded-xl
                border transition-all duration-200 cursor-pointer
                ${category.bg} ${category.border} ${category.hoverBg}
                hover:shadow-sm active:scale-[0.97]
                disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:shadow-none
              `}
              title={t(category.labelKey)}
            >
              <span className={`${category.color} transition-transform duration-200 group-hover:scale-110`}>
                {category.icon}
              </span>
              <span className="text-[11px] font-medium text-text leading-tight">
                {t(category.labelKey)}
              </span>
              <span className={`text-[9px] font-bold px-1.5 py-px rounded-md ${category.color} opacity-60`}>
                {category.toolCount}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
