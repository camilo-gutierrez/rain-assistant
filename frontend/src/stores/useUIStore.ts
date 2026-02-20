import { create } from "zustand";
import type { ActivePanel } from "@/lib/types";

interface UIState {
  activePanel: ActivePanel;
  tabFocused: boolean;
  unreadCount: number;
  metricsDrawerOpen: boolean;
  settingsDrawerOpen: boolean;
  memoriesDrawerOpen: boolean;
  alterEgosDrawerOpen: boolean;
  marketplaceDrawerOpen: boolean;
  mobileSidebarOpen: boolean;

  setActivePanel: (panel: ActivePanel) => void;
  toggleMetricsDrawer: () => void;
  toggleSettingsDrawer: () => void;
  toggleMemoriesDrawer: () => void;
  toggleAlterEgosDrawer: () => void;
  toggleMarketplaceDrawer: () => void;
  toggleMobileSidebar: () => void;
  setTabFocused: (val: boolean) => void;
  incrementUnreadCount: () => void;
  resetUnreadCount: () => void;
}

export const useUIStore = create<UIState>()((set) => ({
  activePanel: "pin",
  tabFocused: true,
  unreadCount: 0,
  metricsDrawerOpen: false,
  settingsDrawerOpen: false,
  memoriesDrawerOpen: false,
  alterEgosDrawerOpen: false,
  marketplaceDrawerOpen: false,
  mobileSidebarOpen: false,

  setActivePanel: (panel) => set({ activePanel: panel }),

  toggleMetricsDrawer: () =>
    set((s) => ({ metricsDrawerOpen: !s.metricsDrawerOpen })),

  toggleSettingsDrawer: () =>
    set((s) => ({ settingsDrawerOpen: !s.settingsDrawerOpen })),

  toggleMemoriesDrawer: () =>
    set((s) => ({ memoriesDrawerOpen: !s.memoriesDrawerOpen })),

  toggleAlterEgosDrawer: () =>
    set((s) => ({ alterEgosDrawerOpen: !s.alterEgosDrawerOpen })),

  toggleMarketplaceDrawer: () =>
    set((s) => ({ marketplaceDrawerOpen: !s.marketplaceDrawerOpen })),

  toggleMobileSidebar: () =>
    set((s) => ({ mobileSidebarOpen: !s.mobileSidebarOpen })),

  setTabFocused: (tabFocused) => {
    if (tabFocused) {
      set({ tabFocused, unreadCount: 0 });
    } else {
      set({ tabFocused });
    }
  },

  incrementUnreadCount: () =>
    set((s) => ({ unreadCount: s.unreadCount + 1 })),

  resetUnreadCount: () => set({ unreadCount: 0 }),
}));
