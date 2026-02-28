"use client";

import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { MessageSquare, FolderOpen, Bot, Inbox, Settings } from "lucide-react";

export default function MobileBottomNav() {
  const activePanel = useUIStore((s) => s.activePanel);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const toggleDirectors = useUIStore((s) => s.toggleDirectorsDrawer);
  const toggleInbox = useUIStore((s) => s.toggleInboxDrawer);
  const toggleSettings = useUIStore((s) => s.toggleSettingsDrawer);
  const inboxUnreadCount = useUIStore((s) => s.inboxUnreadCount);
  const { t } = useTranslation();

  const items = [
    {
      id: "chat",
      label: "Chat",
      icon: <MessageSquare size={20} />,
      action: () => setActivePanel("chat"),
      active: activePanel === "chat",
      badge: 0,
    },
    {
      id: "files",
      label: "Files",
      icon: <FolderOpen size={20} />,
      action: () => setActivePanel("fileBrowser"),
      active: activePanel === "fileBrowser",
      badge: 0,
    },
    {
      id: "directors",
      label: t("directors.title"),
      icon: <Bot size={20} />,
      action: toggleDirectors,
      active: false,
      badge: 0,
    },
    {
      id: "inbox",
      label: t("inbox.title"),
      icon: <Inbox size={20} />,
      action: toggleInbox,
      active: false,
      badge: inboxUnreadCount,
    },
    {
      id: "settings",
      label: t("btn.settings.title"),
      icon: <Settings size={20} />,
      action: toggleSettings,
      active: false,
      badge: 0,
    },
  ];

  return (
    <nav className="md:hidden flex items-center justify-around bg-surface/95 backdrop-blur-md border-t border-overlay/30 py-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))]">
      {items.map((item) => (
        <button
          key={item.id}
          onClick={item.action}
          className={`relative flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg transition-colors min-w-[60px] min-h-[44px] ${
            item.active ? "text-primary" : "text-text2"
          }`}
        >
          <span className="relative">
            {item.icon}
            {item.badge > 0 && (
              <span className="absolute -top-1 -right-1.5 min-w-[14px] h-[14px] flex items-center justify-center px-0.5 rounded-full bg-primary text-on-primary text-xs font-bold">
                {item.badge > 9 ? "9+" : item.badge}
              </span>
            )}
          </span>
          <span className="text-xs leading-tight">{item.label}</span>
          {/* Active indicator bar */}
          {item.active && (
            <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-6 h-[2px] rounded-full bg-primary" />
          )}
        </button>
      ))}
    </nav>
  );
}
