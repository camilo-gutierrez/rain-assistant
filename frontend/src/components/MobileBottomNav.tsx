"use client";

import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { MessageSquare, FolderOpen, BarChart3, Settings } from "lucide-react";

export default function MobileBottomNav() {
  const activePanel = useUIStore((s) => s.activePanel);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const toggleMetrics = useUIStore((s) => s.toggleMetricsDrawer);
  const toggleSettings = useUIStore((s) => s.toggleSettingsDrawer);
  const { t } = useTranslation();

  const items = [
    {
      id: "chat",
      label: "Chat",
      icon: <MessageSquare size={20} />,
      action: () => setActivePanel("chat"),
      active: activePanel === "chat",
    },
    {
      id: "files",
      label: "Files",
      icon: <FolderOpen size={20} />,
      action: () => setActivePanel("fileBrowser"),
      active: activePanel === "fileBrowser",
    },
    {
      id: "metrics",
      label: t("btn.metricsToggle.title"),
      icon: <BarChart3 size={20} />,
      action: toggleMetrics,
      active: false,
    },
    {
      id: "settings",
      label: t("btn.settings.title"),
      icon: <Settings size={20} />,
      action: toggleSettings,
      active: false,
    },
  ];

  return (
    <nav className="md:hidden flex items-center justify-around bg-surface border-t border-overlay py-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))]">
      {items.map((item) => (
        <button
          key={item.id}
          onClick={item.action}
          className={`relative flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg transition-colors min-w-[60px] min-h-[44px] ${
            item.active ? "text-primary" : "text-text2"
          }`}
        >
          {item.icon}
          <span className="text-xs leading-tight">{item.label}</span>
          {/* Active indicator bar */}
          {item.active && (
            <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-5 h-[3px] rounded-full bg-primary" />
          )}
        </button>
      ))}
    </nav>
  );
}
