import { create } from "zustand";

export interface Toast {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
  duration: number;
  dismissible: boolean;
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id" | "duration" | "dismissible"> & { duration?: number; dismissible?: boolean }) => void;
  removeToast: (id: string) => void;
}

const MAX_TOASTS = 3;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (toast) => {
    const id = crypto.randomUUID();
    const newToast: Toast = {
      id,
      type: toast.type,
      message: toast.message,
      duration: toast.duration ?? 4000,
      dismissible: toast.dismissible ?? true,
    };

    set((state) => ({
      toasts: [...state.toasts.slice(-(MAX_TOASTS - 1)), newToast],
    }));

    // Auto-dismiss
    if (newToast.duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, newToast.duration);
    }
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));
