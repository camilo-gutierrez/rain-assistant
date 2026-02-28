"use client";

import { useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useNotifications } from "@/hooks/useNotifications";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useTranslation } from "@/hooks/useTranslation";
import SecurityBanner from "@/components/SecurityBanner";
import StatusBar from "@/components/StatusBar";
import HistorySidebar from "@/components/HistorySidebar";
import SidebarNav from "@/components/SidebarNav";
import MobileBottomNav from "@/components/MobileBottomNav";
import DrawerOverlay from "@/components/DrawerOverlay";
import TabBar from "@/components/TabBar";
import PinPanel from "@/components/panels/PinPanel";
import ApiKeyPanel from "@/components/panels/ApiKeyPanel";
import FileBrowserPanel from "@/components/panels/FileBrowserPanel";
import ChatPanel from "@/components/panels/ChatPanel";
import MetricsPanel from "@/components/panels/MetricsPanel";
import SettingsPanel from "@/components/panels/SettingsPanel";
import MemoriesPanel from "@/components/panels/MemoriesPanel";
import AlterEgosPanel from "@/components/panels/AlterEgosPanel";
import MarketplacePanel from "@/components/panels/MarketplacePanel";
import DirectorsPanel from "@/components/panels/DirectorsPanel";
import DirectorsInboxPanel from "@/components/panels/DirectorsInboxPanel";
import ToastContainer from "@/components/Toast";

export default function HomePage() {
  useWebSocket();
  useNotifications();

  const activePanel = useUIStore((s) => s.activePanel);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const metricsDrawerOpen = useUIStore((s) => s.metricsDrawerOpen);
  const settingsDrawerOpen = useUIStore((s) => s.settingsDrawerOpen);
  const memoriesDrawerOpen = useUIStore((s) => s.memoriesDrawerOpen);
  const alterEgosDrawerOpen = useUIStore((s) => s.alterEgosDrawerOpen);
  const marketplaceDrawerOpen = useUIStore((s) => s.marketplaceDrawerOpen);
  const directorsDrawerOpen = useUIStore((s) => s.directorsDrawerOpen);
  const inboxDrawerOpen = useUIStore((s) => s.inboxDrawerOpen);
  const toggleMetricsDrawer = useUIStore((s) => s.toggleMetricsDrawer);
  const toggleSettingsDrawer = useUIStore((s) => s.toggleSettingsDrawer);
  const toggleMemoriesDrawer = useUIStore((s) => s.toggleMemoriesDrawer);
  const toggleAlterEgosDrawer = useUIStore((s) => s.toggleAlterEgosDrawer);
  const toggleMarketplaceDrawer = useUIStore((s) => s.toggleMarketplaceDrawer);
  const toggleDirectorsDrawer = useUIStore((s) => s.toggleDirectorsDrawer);
  const toggleInboxDrawer = useUIStore((s) => s.toggleInboxDrawer);
  const ensureDefaultAgent = useAgentStore((s) => s.ensureDefaultAgent);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const activeAgentPanel = useAgentStore((s) => {
    const agent = s.activeAgentId ? s.agents[s.activeAgentId] : null;
    return agent?.activePanel ?? null;
  });
  const authToken = useConnectionStore((s) => s.authToken);
  const connect = useConnectionStore((s) => s.connect);
  const theme = useSettingsStore((s) => s.theme);
  const { t } = useTranslation();

  useEffect(() => {
    ensureDefaultAgent();
    document.documentElement.setAttribute("data-theme", theme);

    if (authToken) {
      setActivePanel("apiKey");
      connect();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (activeAgentPanel && (activePanel === "chat" || activePanel === "fileBrowser")) {
      setActivePanel(activeAgentPanel);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeAgentId]);

  const showTabBar = activePanel === "chat" || activePanel === "fileBrowser";
  const showSidebar = activePanel === "chat" || activePanel === "fileBrowser";

  return (
    <div className="flex flex-col h-dvh overflow-hidden bg-bg">
      <SecurityBanner />
      <StatusBar />

      <div className="flex flex-1 overflow-hidden">
        {/* Desktop sidebar */}
        {showSidebar && (
          <aside className="hidden md:flex w-[280px] shrink-0 flex-col bg-surface border-r border-overlay/30">
            <div className="overflow-y-auto flex-1 flex flex-col min-h-0">
              <SidebarNav />
              <div className="h-px bg-gradient-to-r from-transparent via-overlay/50 to-transparent mx-4 shrink-0" />
              <HistorySidebar mode="inline" />
            </div>
          </aside>
        )}

        {/* Main content area */}
        <div className="flex-1 flex flex-col overflow-hidden transition-all duration-200">
          {showTabBar && <TabBar />}
          <main className="flex-1 flex flex-col overflow-hidden">
            {activePanel === "pin" && <PinPanel />}
            {activePanel === "apiKey" && <ApiKeyPanel />}
            {activePanel === "fileBrowser" && <FileBrowserPanel />}
            {activePanel === "chat" && <ChatPanel />}
          </main>
        </div>
      </div>

      {/* Mobile bottom nav */}
      {showTabBar && <MobileBottomNav />}

      {/* Mobile history drawer */}
      <HistorySidebar mode="drawer" />

      {/* Memories drawer */}
      <DrawerOverlay
        open={memoriesDrawerOpen}
        onClose={toggleMemoriesDrawer}
        title={t("memories.title")}
      >
        <MemoriesPanel />
      </DrawerOverlay>

      {/* Alter Egos drawer */}
      <DrawerOverlay
        open={alterEgosDrawerOpen}
        onClose={toggleAlterEgosDrawer}
        title={t("alterEgo.title")}
      >
        <AlterEgosPanel />
      </DrawerOverlay>

      {/* Marketplace drawer */}
      <DrawerOverlay
        open={marketplaceDrawerOpen}
        onClose={toggleMarketplaceDrawer}
        title={t("marketplace.title")}
      >
        <MarketplacePanel />
      </DrawerOverlay>

      {/* Directors drawer */}
      <DrawerOverlay
        open={directorsDrawerOpen}
        onClose={toggleDirectorsDrawer}
        title={t("directors.title")}
      >
        <DirectorsPanel />
      </DrawerOverlay>

      {/* Inbox drawer */}
      <DrawerOverlay
        open={inboxDrawerOpen}
        onClose={toggleInboxDrawer}
        title={t("inbox.title")}
      >
        <DirectorsInboxPanel />
      </DrawerOverlay>

      {/* Metrics drawer */}
      <DrawerOverlay
        open={metricsDrawerOpen}
        onClose={toggleMetricsDrawer}
        title={t("metrics.title")}
      >
        <MetricsPanel />
      </DrawerOverlay>

      {/* Settings drawer */}
      <DrawerOverlay
        open={settingsDrawerOpen}
        onClose={toggleSettingsDrawer}
        title={t("btn.settings.title")}
      >
        <SettingsPanel />
      </DrawerOverlay>

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  );
}
