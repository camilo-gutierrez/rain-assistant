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
}

const mcpCategories: McpCategory[] = [
  {
    id: "hub",
    labelKey: "mcp.hub",
    toolCount: 3,
    prompt: "Muéstrame el menú de Rain con todas las capacidades disponibles",
    icon: <Plug size={18} strokeWidth={1.8} />,
  },
  {
    id: "email",
    labelKey: "mcp.email",
    toolCount: 8,
    prompt: "Quiero usar las funciones de email. Muéstrame qué puedo hacer con el correo.",
    icon: <Mail size={18} strokeWidth={1.8} />,
  },
  {
    id: "browser",
    labelKey: "mcp.browser",
    toolCount: 11,
    prompt: "Quiero navegar por la web. Muéstrame qué puedo hacer con el navegador.",
    icon: <Globe size={18} strokeWidth={1.8} />,
  },
  {
    id: "smarthome",
    labelKey: "mcp.smarthome",
    toolCount: 10,
    prompt: "Quiero controlar mi smart home. Muéstrame los dispositivos disponibles.",
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

  return (
    <div className="px-1 py-1">
      {/* Section header — ChatGPT style muted label */}
      <button
        onClick={toggleCollapsed}
        className="flex items-center gap-2 px-2 py-1.5 mb-1 w-full group cursor-pointer rounded-lg hover:bg-surface2/40 transition-colors duration-150"
      >
        <span className="text-xs font-medium text-subtext uppercase tracking-wide">
          {t("mcp.title")}
        </span>
        <span className="flex-1" />
        <span className="text-subtext group-hover:text-text transition-colors duration-150">
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </span>
      </button>

      {/* Minimal list — ChatGPT GPT shortcuts style */}
      {!collapsed && (
        <div className="flex flex-col gap-0.5 animate-fade-in">
          {mcpCategories.map((category) => (
            <button
              key={category.id}
              onClick={() => handleToolClick(category)}
              disabled={!hasCwd || isProcessing}
              className="group flex items-center gap-3 px-3 py-2 rounded-[10px] transition-colors duration-150 text-sm text-text2 hover:bg-surface2/60 hover:text-text disabled:opacity-30 disabled:cursor-not-allowed"
              title={t(category.labelKey)}
            >
              <span className="text-text2 group-hover:text-text transition-colors duration-150">
                {category.icon}
              </span>
              <span className="flex-1 text-left">{t(category.labelKey)}</span>
              <span className="text-xs text-subtext">{category.toolCount}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
