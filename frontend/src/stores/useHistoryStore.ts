import { create } from "zustand";
import type { ConversationMeta } from "@/lib/types";

interface HistoryState {
  conversations: ConversationMeta[];
  isLoading: boolean;
  isSaving: boolean;
  activeConversationId: string | null;

  setConversations: (conversations: ConversationMeta[]) => void;
  setLoading: (val: boolean) => void;
  setSaving: (val: boolean) => void;
  setActiveConversationId: (id: string | null) => void;
}

export const useHistoryStore = create<HistoryState>()((set) => ({
  conversations: [],
  isLoading: false,
  isSaving: false,
  activeConversationId: null,

  setConversations: (conversations) => set({ conversations }),
  setLoading: (isLoading) => set({ isLoading }),
  setSaving: (isSaving) => set({ isSaving }),
  setActiveConversationId: (activeConversationId) =>
    set({ activeConversationId }),
}));
