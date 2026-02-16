"use client";

import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";

interface McpCategory {
  id: string;
  labelKey: string;
  icon: React.ReactNode;
  toolCount: number;
  prompt: string;
  color: string;       // text/icon color
  bg: string;          // background
  border: string;      // border color
  hoverBorder: string; // border on hover
  glow: string;        // subtle glow on hover
}

const mcpCategories: McpCategory[] = [
  {
    id: "hub",
    labelKey: "mcp.hub",
    toolCount: 3,
    prompt: "Muéstrame el menú de Rain con todas las capacidades disponibles",
    color: "text-primary",
    bg: "bg-primary/8",
    border: "border-primary/15",
    hoverBorder: "hover:border-primary/40",
    glow: "hover:shadow-[0_0_12px_rgba(var(--primary-rgb),0.15)]",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    id: "email",
    labelKey: "mcp.email",
    toolCount: 8,
    prompt: "Quiero usar las funciones de email. Muéstrame qué puedo hacer con el correo.",
    color: "text-green",
    bg: "bg-green/8",
    border: "border-green/15",
    hoverBorder: "hover:border-green/40",
    glow: "hover:shadow-[0_0_12px_rgba(129,199,132,0.15)]",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <polyline points="22,7 12,13 2,7" />
      </svg>
    ),
  },
  {
    id: "browser",
    labelKey: "mcp.browser",
    toolCount: 11,
    prompt: "Quiero navegar por la web. Muéstrame qué puedo hacer con el navegador.",
    color: "text-cyan",
    bg: "bg-cyan/8",
    border: "border-cyan/15",
    hoverBorder: "hover:border-cyan/40",
    glow: "hover:shadow-[0_0_12px_rgba(144,202,249,0.15)]",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
  },
  {
    id: "smarthome",
    labelKey: "mcp.smarthome",
    toolCount: 10,
    prompt: "Quiero controlar mi smart home. Muéstrame los dispositivos disponibles.",
    color: "text-mauve",
    bg: "bg-mauve/8",
    border: "border-mauve/15",
    hoverBorder: "hover:border-mauve/40",
    glow: "hover:shadow-[0_0_12px_rgba(206,147,216,0.15)]",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
  },
];

export default function McpToolsSection() {
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

  const handleToolClick = (category: McpCategory) => {
    if (!activeAgentId || !hasCwd || isProcessing) return;

    // Switch to chat
    setActivePanel("chat");

    // Add user message
    appendMessage(activeAgentId, {
      id: crypto.randomUUID(),
      type: "user",
      text: category.prompt,
      timestamp: Date.now(),
      animate: true,
    });

    // Send to backend
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

  return (
    <div className="px-3 py-2">
      {/* Section header */}
      <div className="flex items-center gap-2 px-1 mb-2">
        <span className="text-[10px] uppercase tracking-widest text-subtext font-semibold">
          {t("mcp.title")}
        </span>
        <div className="flex-1 h-px bg-overlay/40" />
        <span className="text-[10px] text-subtext tabular-nums">
          {mcpCategories.reduce((sum, c) => sum + c.toolCount, 0)}
        </span>
      </div>

      {/* 2x2 grid of MCP category cards */}
      <div className="grid grid-cols-2 gap-1.5">
        {mcpCategories.map((category) => (
          <button
            key={category.id}
            onClick={() => handleToolClick(category)}
            disabled={!hasCwd || isProcessing}
            className={`
              group relative flex flex-col items-center gap-1 p-2.5 rounded-xl
              border transition-all duration-200 cursor-pointer
              ${category.bg} ${category.border} ${category.hoverBorder} ${category.glow}
              hover:scale-[1.03] active:scale-[0.97]
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:hover:shadow-none
            `}
            title={t(category.labelKey)}
          >
            {/* Icon */}
            <span className={`${category.color} transition-transform duration-200 group-hover:scale-110`}>
              {category.icon}
            </span>

            {/* Label */}
            <span className="text-[11px] font-medium text-text leading-tight">
              {t(category.labelKey)}
            </span>

            {/* Tool count badge */}
            <span className={`
              text-[9px] font-semibold px-1.5 py-0.5 rounded-full
              ${category.bg} ${category.color} opacity-70
            `}>
              {category.toolCount} tools
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
