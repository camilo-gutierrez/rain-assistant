"use client";

import { useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useNotifications } from "@/hooks/useNotifications";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import StatusBar from "@/components/StatusBar";
import HistorySidebar from "@/components/HistorySidebar";
import TabBar from "@/components/TabBar";
import PinPanel from "@/components/panels/PinPanel";
import ApiKeyPanel from "@/components/panels/ApiKeyPanel";
import FileBrowserPanel from "@/components/panels/FileBrowserPanel";
import ChatPanel from "@/components/panels/ChatPanel";
import MetricsPanel from "@/components/panels/MetricsPanel";
import SettingsPanel from "@/components/panels/SettingsPanel";

export default function HomePage() {
  // Initialize central hooks (call once)
  useWebSocket();
  useNotifications();

  const activePanel = useUIStore((s) => s.activePanel);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const ensureDefaultAgent = useAgentStore((s) => s.ensureDefaultAgent);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const activeAgentPanel = useAgentStore((s) => {
    const agent = s.activeAgentId ? s.agents[s.activeAgentId] : null;
    return agent?.activePanel ?? null;
  });
  const authToken = useConnectionStore((s) => s.authToken);
  const connect = useConnectionStore((s) => s.connect);
  const theme = useSettingsStore((s) => s.theme);

  // On mount: ensure a default agent exists, apply theme, and auto-connect if we have a token
  useEffect(() => {
    ensureDefaultAgent();

    // Apply theme to document
    document.documentElement.setAttribute("data-theme", theme);

    if (authToken) {
      // We already have a token from a previous session, skip PIN
      setActivePanel("apiKey");
      connect();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep theme in sync when it changes
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // When switching agents, restore that agent's panel (chat or fileBrowser)
  useEffect(() => {
    if (activeAgentPanel && (activePanel === "chat" || activePanel === "fileBrowser")) {
      setActivePanel(activeAgentPanel);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeAgentId]);

  const showTabBar = activePanel === "chat" || activePanel === "fileBrowser";

  return (
    <div className="flex flex-col h-dvh overflow-hidden">
      <StatusBar />
      <HistorySidebar />
      {showTabBar && <TabBar />}
      <main className="flex-1 flex flex-col overflow-hidden">
        {activePanel === "pin" && <PinPanel />}
        {activePanel === "apiKey" && <ApiKeyPanel />}
        {activePanel === "fileBrowser" && <FileBrowserPanel />}
        {activePanel === "chat" && <ChatPanel />}
        {activePanel === "metrics" && <MetricsPanel />}
        {activePanel === "settings" && <SettingsPanel />}
      </main>
    </div>
  );
}
