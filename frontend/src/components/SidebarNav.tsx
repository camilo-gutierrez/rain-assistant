"use client";

import { useUIStore } from "@/stores/useUIStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useTranslation } from "@/hooks/useTranslation";
import { MessageSquare, FolderOpen, BarChart3, Settings, Plus, Sparkles, Bot, Inbox } from "lucide-react";
import McpToolsSection from "./McpToolsSection";

export default function SidebarNav() {
  const activePanel = useUIStore((s) => s.activePanel);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const toggleMetrics = useUIStore((s) => s.toggleMetricsDrawer);
  const toggleSettings = useUIStore((s) => s.toggleSettingsDrawer);
  const toggleDirectors = useUIStore((s) => s.toggleDirectorsDrawer);
  const toggleInbox = useUIStore((s) => s.toggleInboxDrawer);
  const inboxUnreadCount = useUIStore((s) => s.inboxUnreadCount);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const clearMessages = useAgentStore((s) => s.clearMessages);
  const { t } = useTranslation();

  const handleNewChat = () => {
    if (activeAgentId) {
      clearMessages(activeAgentId);
    }
    setActivePanel("chat");
  };

  const mainNav = [
    {
      id: "chat" as const,
      label: "Chat",
      icon: <MessageSquare size={18} />,
      action: () => setActivePanel("chat"),
      active: activePanel === "chat",
    },
    {
      id: "files" as const,
      label: "Files",
      icon: <FolderOpen size={18} />,
      action: () => setActivePanel("fileBrowser"),
      active: activePanel === "fileBrowser",
    },
  ];

  const secondaryNav = [
    {
      id: "directors" as const,
      label: t("directors.title"),
      icon: <Bot size={18} />,
      action: toggleDirectors,
      active: false,
      badge: 0,
    },
    {
      id: "inbox" as const,
      label: t("inbox.title"),
      icon: <Inbox size={18} />,
      action: toggleInbox,
      active: false,
      badge: inboxUnreadCount,
    },
    {
      id: "metrics" as const,
      label: t("btn.metricsToggle.title"),
      icon: <BarChart3 size={18} />,
      action: toggleMetrics,
      active: false,
      badge: 0,
    },
    {
      id: "settings" as const,
      label: t("btn.settings.title"),
      icon: <Settings size={18} />,
      action: toggleSettings,
      active: false,
      badge: 0,
    },
  ];

  return (
    <div className="flex flex-col gap-1 px-3 pt-4 pb-2">
      {/* Brand mark */}
      <div className="flex items-center gap-2.5 px-2 mb-3">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center shadow-sm">
          <Sparkles size={16} className="text-on-primary" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-bold text-text leading-tight">Rain</span>
          <span className="text-xs text-subtext leading-tight">{t("sidebar.subtitle")}</span>
        </div>
      </div>

      {/* New conversation button */}
      <button
        onClick={handleNewChat}
        className="group flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-overlay/80 bg-surface2/40 text-text text-sm font-medium transition-all duration-200 hover:bg-primary hover:text-on-primary hover:border-primary hover:shadow-md active:scale-[0.98] mb-1"
      >
        <Plus size={16} strokeWidth={2.5} className="transition-transform duration-200 group-hover:rotate-90" />
        <span>{t("sidebar.newChat")}</span>
      </button>

      {/* Main navigation */}
      <div className="flex flex-col gap-0.5 mt-1">
        {mainNav.map((item) => (
          <button
            key={item.id}
            onClick={item.action}
            className={`group flex items-center gap-3 px-3 py-2 rounded-xl transition-all duration-150 text-sm ${
              item.active
                ? "bg-primary/10 text-primary font-semibold shadow-[inset_0_0_0_1px_rgba(var(--primary-rgb),0.15)]"
                : "text-text2 hover:bg-surface2/70 hover:text-text"
            }`}
            title={item.label}
          >
            <span className={`flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-150 ${
              item.active
                ? "bg-primary/15 text-primary shadow-sm"
                : "bg-transparent group-hover:bg-surface2/80"
            }`}>
              {item.icon}
            </span>
            <span>{item.label}</span>
            {item.active && (
              <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary animate-pulse-ring" />
            )}
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-overlay/60 to-transparent mx-1 my-2" />

      {/* Secondary navigation (drawers) */}
      <div className="flex flex-col gap-0.5">
        {secondaryNav.map((item) => (
          <button
            key={item.id}
            onClick={item.action}
            className="group flex items-center gap-3 px-3 py-2 rounded-xl transition-all duration-150 text-sm text-text2 hover:bg-surface2/70 hover:text-text"
            title={item.label}
          >
            <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-transparent group-hover:bg-surface2/80 transition-all duration-150">
              {item.icon}
            </span>
            <span>{item.label}</span>
            {item.badge > 0 && (
              <span className="ml-auto min-w-[18px] h-[18px] flex items-center justify-center px-1 rounded-full bg-primary text-on-primary text-xs font-bold">
                {item.badge > 99 ? "99+" : item.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-overlay/60 to-transparent mx-1 my-2" />

      {/* MCP Tools */}
      <McpToolsSection />
    </div>
  );
}
