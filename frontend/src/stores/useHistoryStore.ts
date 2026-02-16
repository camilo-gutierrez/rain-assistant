import { create } from "zustand";
import type { ConversationMeta } from "@/lib/types";

interface HistoryState {
  conversations: ConversationMeta[];
  isLoading: boolean;
  isSaving: boolean;
  sidebarOpen: boolean;
  activeConversationId: string | null;

  setConversations: (conversations: ConversationMeta[]) => void;
  setLoading: (val: boolean) => void;
  setSaving: (val: boolean) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (val: boolean) => void;
  setActiveConversationId: (id: string | null) => void;
}

export const useHistoryStore = create<HistoryState>()((set) => ({
  conversations: [],
  isLoading: false,
  isSaving: false,
  sidebarOpen: false,
  activeConversationId: null,

  setConversations: (conversations) => set({ conversations }),
  setLoading: (isLoading) => set({ isLoading }),
  setSaving: (isSaving) => set({ isSaving }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setActiveConversationId: (activeConversationId) =>
    set({ activeConversationId }),
}));
