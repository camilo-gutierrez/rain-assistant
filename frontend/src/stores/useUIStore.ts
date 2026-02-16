import { create } from "zustand";
import type { ActivePanel } from "@/lib/types";

interface UIState {
  activePanel: ActivePanel;
  previousPanel: ActivePanel | null;
  tabFocused: boolean;
  unreadCount: number;

  setActivePanel: (panel: ActivePanel) => void;
  toggleMetrics: () => void;
  toggleSettings: () => void;
  setTabFocused: (val: boolean) => void;
  incrementUnreadCount: () => void;
  resetUnreadCount: () => void;
}

export const useUIStore = create<UIState>()((set, get) => ({
  activePanel: "pin",
  previousPanel: null,
  tabFocused: true,
  unreadCount: 0,

  setActivePanel: (panel) => set({ activePanel: panel }),

  toggleMetrics: () => {
    const { activePanel } = get();
    if (activePanel === "metrics") {
      // Return to previous panel
      const prev = get().previousPanel || "chat";
      set({ activePanel: prev, previousPanel: null });
    } else {
      set({ previousPanel: activePanel, activePanel: "metrics" });
    }
  },

  toggleSettings: () => {
    const { activePanel } = get();
    if (activePanel === "settings") {
      const prev = get().previousPanel || "chat";
      set({ activePanel: prev, previousPanel: null });
    } else {
      set({ previousPanel: activePanel, activePanel: "settings" });
    }
  },

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
