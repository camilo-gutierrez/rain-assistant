"use client";

import { useUIStore } from "@/stores/useUIStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useTranslation } from "@/hooks/useTranslation";
import { MessageSquare, FolderOpen, BarChart3, Settings, Plus, Sparkles, Bot, Inbox, Search } from "lucide-react";
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
      icon: <MessageSquare size={20} strokeWidth={1.8} />,
      action: () => setActivePanel("chat"),
      active: activePanel === "chat",
    },
    {
      id: "files" as const,
      label: "Files",
      icon: <FolderOpen size={20} strokeWidth={1.8} />,
      action: () => setActivePanel("fileBrowser"),
      active: activePanel === "fileBrowser",
    },
  ];

  const secondaryNav = [
    {
      id: "directors" as const,
      label: t("directors.title"),
      icon: <Bot size={20} strokeWidth={1.8} />,
      action: toggleDirectors,
      active: false,
      badge: 0,
    },
    {
      id: "inbox" as const,
      label: t("inbox.title"),
      icon: <Inbox size={20} strokeWidth={1.8} />,
      action: toggleInbox,
      active: false,
      badge: inboxUnreadCount,
    },
    {
      id: "metrics" as const,
      label: t("btn.metricsToggle.title"),
      icon: <BarChart3 size={20} strokeWidth={1.8} />,
      action: toggleMetrics,
      active: false,
      badge: 0,
    },
    {
      id: "settings" as const,
      label: t("btn.settings.title"),
      icon: <Settings size={20} strokeWidth={1.8} />,
      action: toggleSettings,
      active: false,
      badge: 0,
    },
  ];

  return (
    <div className="flex flex-col gap-0.5 px-3 pt-4 pb-2">
      {/* Brand — minimal, ChatGPT-style */}
      <div className="flex items-center justify-between px-2 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
            <Sparkles size={16} className="text-on-primary" />
          </div>
          <span className="text-base font-semibold text-text">Rain</span>
        </div>
      </div>

      {/* New conversation — ghost style */}
      <button
        onClick={handleNewChat}
        className="group flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-sm text-text2 hover:bg-surface2/60 hover:text-text transition-colors duration-150 mb-1"
      >
        <Plus size={20} strokeWidth={1.8} />
        <span>{t("sidebar.newChat")}</span>
      </button>

      {/* Main navigation */}
      <div className="flex flex-col gap-0.5">
        {mainNav.map((item) => (
          <button
            key={item.id}
            onClick={item.action}
            className={`group flex items-center gap-3 px-3 py-2.5 rounded-[10px] transition-colors duration-150 text-sm ${
              item.active
                ? "bg-surface2 text-text font-medium"
                : "text-text2 hover:bg-surface2/60 hover:text-text"
            }`}
            title={item.label}
          >
            <span className={item.active ? "text-text" : "text-text2 group-hover:text-text"}>
              {item.icon}
            </span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      {/* Divider — subtle */}
      <div className="h-px bg-overlay/40 mx-2 my-2" />

      {/* Secondary navigation (drawers) */}
      <div className="flex flex-col gap-0.5">
        {secondaryNav.map((item) => (
          <button
            key={item.id}
            onClick={item.action}
            className="group flex items-center gap-3 px-3 py-2.5 rounded-[10px] transition-colors duration-150 text-sm text-text2 hover:bg-surface2/60 hover:text-text"
            title={item.label}
          >
            <span className="text-text2 group-hover:text-text transition-colors duration-150">
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
      <div className="h-px bg-overlay/40 mx-2 my-2" />

      {/* MCP Tools */}
      <McpToolsSection />
    </div>
  );
}
