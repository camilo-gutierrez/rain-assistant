import { describe, it, expect, beforeEach } from "vitest";
import { useUIStore } from "@/stores/useUIStore";

// Reset store between tests
beforeEach(() => {
  useUIStore.setState({
    activePanel: "pin",
    tabFocused: true,
    unreadCount: 0,
    metricsDrawerOpen: false,
    settingsDrawerOpen: false,
    memoriesDrawerOpen: false,
    alterEgosDrawerOpen: false,
    marketplaceDrawerOpen: false,
    mobileSidebarOpen: false,
  });
});

describe("useUIStore", () => {
  // --- Initial state ---

  describe("initial state", () => {
    it("starts with default values", () => {
      const state = useUIStore.getState();
      expect(state.activePanel).toBe("pin");
      expect(state.tabFocused).toBe(true);
      expect(state.unreadCount).toBe(0);
      expect(state.metricsDrawerOpen).toBe(false);
      expect(state.settingsDrawerOpen).toBe(false);
      expect(state.memoriesDrawerOpen).toBe(false);
      expect(state.alterEgosDrawerOpen).toBe(false);
      expect(state.marketplaceDrawerOpen).toBe(false);
      expect(state.mobileSidebarOpen).toBe(false);
    });
  });

  // --- setActivePanel ---

  describe("setActivePanel()", () => {
    it("changes the active panel", () => {
      useUIStore.getState().setActivePanel("chat");
      expect(useUIStore.getState().activePanel).toBe("chat");
    });

    it("can set each panel type", () => {
      const panels = ["pin", "apiKey", "fileBrowser", "chat"] as const;
      for (const panel of panels) {
        useUIStore.getState().setActivePanel(panel);
        expect(useUIStore.getState().activePanel).toBe(panel);
      }
    });
  });

  // --- Drawer toggles ---

  describe("toggleMetricsDrawer()", () => {
    it("toggles metrics drawer on and off", () => {
      expect(useUIStore.getState().metricsDrawerOpen).toBe(false);

      useUIStore.getState().toggleMetricsDrawer();
      expect(useUIStore.getState().metricsDrawerOpen).toBe(true);

      useUIStore.getState().toggleMetricsDrawer();
      expect(useUIStore.getState().metricsDrawerOpen).toBe(false);
    });
  });

  describe("toggleSettingsDrawer()", () => {
    it("toggles settings drawer on and off", () => {
      expect(useUIStore.getState().settingsDrawerOpen).toBe(false);

      useUIStore.getState().toggleSettingsDrawer();
      expect(useUIStore.getState().settingsDrawerOpen).toBe(true);

      useUIStore.getState().toggleSettingsDrawer();
      expect(useUIStore.getState().settingsDrawerOpen).toBe(false);
    });
  });

  describe("toggleMemoriesDrawer()", () => {
    it("toggles memories drawer on and off", () => {
      expect(useUIStore.getState().memoriesDrawerOpen).toBe(false);

      useUIStore.getState().toggleMemoriesDrawer();
      expect(useUIStore.getState().memoriesDrawerOpen).toBe(true);

      useUIStore.getState().toggleMemoriesDrawer();
      expect(useUIStore.getState().memoriesDrawerOpen).toBe(false);
    });
  });

  describe("toggleAlterEgosDrawer()", () => {
    it("toggles alter egos drawer on and off", () => {
      expect(useUIStore.getState().alterEgosDrawerOpen).toBe(false);

      useUIStore.getState().toggleAlterEgosDrawer();
      expect(useUIStore.getState().alterEgosDrawerOpen).toBe(true);

      useUIStore.getState().toggleAlterEgosDrawer();
      expect(useUIStore.getState().alterEgosDrawerOpen).toBe(false);
    });
  });

  describe("toggleMarketplaceDrawer()", () => {
    it("toggles marketplace drawer on and off", () => {
      expect(useUIStore.getState().marketplaceDrawerOpen).toBe(false);

      useUIStore.getState().toggleMarketplaceDrawer();
      expect(useUIStore.getState().marketplaceDrawerOpen).toBe(true);

      useUIStore.getState().toggleMarketplaceDrawer();
      expect(useUIStore.getState().marketplaceDrawerOpen).toBe(false);
    });
  });

  describe("toggleMobileSidebar()", () => {
    it("toggles mobile sidebar on and off", () => {
      expect(useUIStore.getState().mobileSidebarOpen).toBe(false);

      useUIStore.getState().toggleMobileSidebar();
      expect(useUIStore.getState().mobileSidebarOpen).toBe(true);

      useUIStore.getState().toggleMobileSidebar();
      expect(useUIStore.getState().mobileSidebarOpen).toBe(false);
    });
  });

  // --- Drawers are independent ---

  describe("drawer independence", () => {
    it("toggling one drawer does not affect others", () => {
      useUIStore.getState().toggleMetricsDrawer();
      expect(useUIStore.getState().metricsDrawerOpen).toBe(true);
      expect(useUIStore.getState().settingsDrawerOpen).toBe(false);
      expect(useUIStore.getState().memoriesDrawerOpen).toBe(false);
      expect(useUIStore.getState().alterEgosDrawerOpen).toBe(false);
      expect(useUIStore.getState().marketplaceDrawerOpen).toBe(false);
      expect(useUIStore.getState().mobileSidebarOpen).toBe(false);
    });
  });

  // --- Tab focus ---

  describe("setTabFocused()", () => {
    it("sets tab as focused and resets unread count", () => {
      // First, increment unread a few times
      useUIStore.getState().incrementUnreadCount();
      useUIStore.getState().incrementUnreadCount();
      expect(useUIStore.getState().unreadCount).toBe(2);

      // Now blur and refocus
      useUIStore.getState().setTabFocused(false);
      expect(useUIStore.getState().tabFocused).toBe(false);
      expect(useUIStore.getState().unreadCount).toBe(2); // unread preserved on blur

      useUIStore.getState().setTabFocused(true);
      expect(useUIStore.getState().tabFocused).toBe(true);
      expect(useUIStore.getState().unreadCount).toBe(0); // reset on focus
    });
  });

  // --- Unread count ---

  describe("incrementUnreadCount()", () => {
    it("increments the unread count", () => {
      useUIStore.getState().incrementUnreadCount();
      expect(useUIStore.getState().unreadCount).toBe(1);

      useUIStore.getState().incrementUnreadCount();
      expect(useUIStore.getState().unreadCount).toBe(2);
    });
  });

  describe("resetUnreadCount()", () => {
    it("resets unread count to zero", () => {
      useUIStore.getState().incrementUnreadCount();
      useUIStore.getState().incrementUnreadCount();
      useUIStore.getState().incrementUnreadCount();
      expect(useUIStore.getState().unreadCount).toBe(3);

      useUIStore.getState().resetUnreadCount();
      expect(useUIStore.getState().unreadCount).toBe(0);
    });
  });
});
