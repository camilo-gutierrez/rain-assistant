"use client";

import { useState, useEffect } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { fetchMcpStatus, type McpServerInfo } from "@/lib/api";
import { ChevronDown, ChevronUp, Plug, Mail, Globe, Home, Calendar } from "lucide-react";

interface McpCategory {
  id: string;
  serverName: string;
  labelKey: string;
  icon: React.ReactNode;
  toolCount: number;
  prompt: string;
  setupPrompt: string;
}

const mcpCategories: McpCategory[] = [
  {
    id: "hub",
    serverName: "rain-hub",
    labelKey: "mcp.hub",
    toolCount: 3,
    prompt: "Muéstrame el menú de Rain con todas las capacidades disponibles",
    setupPrompt: "Quiero configurar Rain. Usa la herramienta rain_setup_guide para guiarme paso a paso.",
    icon: <Plug size={18} strokeWidth={1.8} />,
  },
  {
    id: "email",
    serverName: "rain-email",
    labelKey: "mcp.email",
    toolCount: 8,
    prompt: "Quiero usar las funciones de email. Muéstrame qué puedo hacer con el correo.",
    setupPrompt: "Quiero configurar mi correo electrónico. Usa la herramienta email_setup_oauth para ayudarme a conectar mi cuenta de Gmail paso a paso.",
    icon: <Mail size={18} strokeWidth={1.8} />,
  },
  {
    id: "browser",
    serverName: "rain-browser",
    labelKey: "mcp.browser",
    toolCount: 11,
    prompt: "Quiero navegar por la web. Muéstrame qué puedo hacer con el navegador.",
    setupPrompt: "Quiero usar el navegador web. Ábrelo y muéstrame qué puedo hacer.",
    icon: <Globe size={18} strokeWidth={1.8} />,
  },
  {
    id: "calendar",
    serverName: "rain-calendar",
    labelKey: "mcp.calendar",
    toolCount: 8,
    prompt: "Quiero ver mi calendario. Muéstrame mis eventos próximos.",
    setupPrompt: "Quiero configurar mi calendario. Usa la herramienta calendar_setup_oauth para ayudarme a conectar mi Google Calendar paso a paso.",
    icon: <Calendar size={18} strokeWidth={1.8} />,
  },
  {
    id: "smarthome",
    serverName: "rain-smarthome",
    labelKey: "mcp.smarthome",
    toolCount: 10,
    prompt: "Quiero controlar mi smart home. Muéstrame los dispositivos disponibles.",
    setupPrompt: "Quiero configurar mi smart home. Usa la herramienta home_setup para ayudarme a conectar Home Assistant paso a paso.",
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

type McpStatus = "ok" | "error" | "loading" | "unknown";

function getServerStatus(
  serverName: string,
  servers: Record<string, McpServerInfo>
): McpStatus {
  const info = servers[serverName];
  if (!info) return "unknown";
  return info.status === "ok" ? "ok" : "error";
}

function StatusDot({ status }: { status: McpStatus }) {
  if (status === "loading") return null;

  const colors: Record<McpStatus, string> = {
    ok: "bg-green",
    error: "bg-yellow",
    unknown: "bg-text2/30",
    loading: "",
  };

  return (
    <span
      className={`w-1.5 h-1.5 rounded-full shrink-0 ${colors[status]}`}
    />
  );
}

export default function McpToolsSection() {
  const [collapsed, setCollapsed] = useState(getInitialCollapsed);
  const [servers, setServers] = useState<Record<string, McpServerInfo>>({});
  const [loaded, setLoaded] = useState(false);
  const send = useConnectionStore((s) => s.send);
  const authToken = useConnectionStore((s) => s.authToken);
  const connectionStatus = useConnectionStore((s) => s.connectionStatus);
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

  // Fetch MCP status on connect
  useEffect(() => {
    if (connectionStatus !== "connected" || !authToken) return;
    let cancelled = false;
    fetchMcpStatus(authToken).then((data) => {
      if (!cancelled) {
        setServers(data.servers);
        setLoaded(true);
      }
    });
    return () => { cancelled = true; };
  }, [connectionStatus, authToken]);

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

    const status = getServerStatus(category.serverName, servers);
    // Pick the right prompt: setup if not configured, normal if ok
    const prompt = status === "ok" ? category.prompt : category.setupPrompt;

    setActivePanel("chat");

    appendMessage(activeAgentId, {
      id: crypto.randomUUID(),
      type: "user",
      text: prompt,
      timestamp: Date.now(),
      animate: true,
    });

    const sent = send({
      type: "send_message",
      text: prompt,
      agent_id: activeAgentId,
    });

    if (sent) {
      setProcessing(activeAgentId, true);
      setAgentStatus(activeAgentId, "working");
    }
  };

  return (
    <div className="px-1 py-1">
      {/* Section header */}
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

      {!collapsed && (
        <div className="flex flex-col gap-0.5 animate-fade-in">
          {mcpCategories.map((category) => {
            const status = loaded
              ? getServerStatus(category.serverName, servers)
              : "loading";

            return (
              <button
                key={category.id}
                onClick={() => handleToolClick(category)}
                disabled={!hasCwd || isProcessing}
                className="group flex items-center gap-3 px-3 py-2 rounded-[10px] transition-colors duration-150 text-sm text-text2 hover:bg-surface2/60 hover:text-text disabled:opacity-30 disabled:cursor-not-allowed"
                title={
                  status === "error"
                    ? t("mcp.clickToSetup", { label: t(category.labelKey) })
                    : t(category.labelKey)
                }
              >
                <span className="text-text2 group-hover:text-text transition-colors duration-150">
                  {category.icon}
                </span>
                <span className="flex-1 text-left">{t(category.labelKey)}</span>
                <StatusDot status={status} />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
