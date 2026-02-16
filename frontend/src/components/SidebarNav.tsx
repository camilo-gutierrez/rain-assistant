"use client";

import { useUIStore } from "@/stores/useUIStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useTranslation } from "@/hooks/useTranslation";
import McpToolsSection from "./McpToolsSection";

export default function SidebarNav() {
  const activePanel = useUIStore((s) => s.activePanel);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const toggleMetrics = useUIStore((s) => s.toggleMetricsDrawer);
  const toggleSettings = useUIStore((s) => s.toggleSettingsDrawer);
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
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      ),
      action: () => setActivePanel("chat"),
      active: activePanel === "chat",
    },
    {
      id: "files" as const,
      label: "Files",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        </svg>
      ),
      action: () => setActivePanel("fileBrowser"),
      active: activePanel === "fileBrowser",
    },
  ];

  const secondaryNav = [
    {
      id: "metrics" as const,
      label: t("btn.metricsToggle.title"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      ),
      action: toggleMetrics,
      active: false,
    },
    {
      id: "settings" as const,
      label: t("btn.settings.title"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      ),
      action: toggleSettings,
      active: false,
    },
  ];

  return (
    <div className="flex flex-col gap-1 px-3 pt-3 pb-2">
      {/* New conversation button */}
      <button
        onClick={handleNewChat}
        className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-medium transition-all duration-200 hover:opacity-90 hover:shadow-md active:scale-[0.98] mb-1"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        <span>{t("sidebar.newChat")}</span>
      </button>

      {/* Main navigation */}
      <div className="flex flex-col gap-0.5 mt-1">
        {mainNav.map((item) => (
          <button
            key={item.id}
            onClick={item.action}
            className={`group flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 text-sm ${
              item.active
                ? "bg-primary/10 text-primary font-medium border-l-[3px] border-l-primary pl-[9px]"
                : "text-text2 hover:bg-surface2 hover:text-text border-l-[3px] border-l-transparent pl-[9px]"
            }`}
            title={item.label}
          >
            <span className={`flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150 ${
              item.active ? "bg-primary/15" : "bg-surface2 group-hover:bg-overlay/50"
            }`}>
              {item.icon}
            </span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="h-px bg-overlay/60 mx-2 my-1.5" />

      {/* Secondary navigation (drawers) */}
      <div className="flex flex-col gap-0.5">
        {secondaryNav.map((item) => (
          <button
            key={item.id}
            onClick={item.action}
            className="group flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 text-sm text-text2 hover:bg-surface2 hover:text-text border-l-[3px] border-l-transparent pl-[9px]"
            title={item.label}
          >
            <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-surface2 group-hover:bg-overlay/50 transition-colors duration-150">
              {item.icon}
            </span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="h-px bg-overlay/60 mx-2 my-1.5" />

      {/* MCP Tools */}
      <McpToolsSection />
    </div>
  );
}
