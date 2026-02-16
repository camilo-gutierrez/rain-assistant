import { create } from "zustand";
import type { WSSendMessage } from "@/lib/types";
import { getWsUrl } from "@/lib/constants";

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

interface ConnectionState {
  ws: WebSocket | null;
  reconnectTimerId: ReturnType<typeof setTimeout> | null;
  authToken: string | null;
  connectionStatus: ConnectionStatus;
  statusText: string;
  consecutiveFails: number;
  usingApiKey: boolean;

  setAuthToken: (token: string | null) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setStatusText: (text: string) => void;
  setUsingApiKey: (val: boolean) => void;
  connect: () => void;
  disconnect: () => void;
  send: (msg: WSSendMessage) => boolean;
  resetToPin: () => void;
}

export const useConnectionStore = create<ConnectionState>()((set, get) => ({
  ws: null,
  reconnectTimerId: null,
  authToken:
    typeof window !== "undefined"
      ? sessionStorage.getItem("rain-token")
      : null,
  connectionStatus: "disconnected",
  statusText: "",
  consecutiveFails: 0,
  usingApiKey: false,

  setAuthToken: (token) => {
    if (token) {
      sessionStorage.setItem("rain-token", token);
    } else {
      sessionStorage.removeItem("rain-token");
    }
    set({ authToken: token });
  },

  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setStatusText: (statusText) => set({ statusText }),
  setUsingApiKey: (usingApiKey) => set({ usingApiKey }),

  connect: () => {
    const { reconnectTimerId, authToken } = get();

    if (reconnectTimerId) {
      clearTimeout(reconnectTimerId);
      set({ reconnectTimerId: null });
    }

    const wsUrl = authToken
      ? `${getWsUrl()}?token=${encodeURIComponent(authToken)}`
      : getWsUrl();

    set({ connectionStatus: "connecting" });

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      set({ connectionStatus: "connected", consecutiveFails: 0, statusText: "Connected" });
    };

    // onmessage is handled by useWebSocket hook

    ws.onclose = (e) => {
      set({ connectionStatus: "disconnected", statusText: "Disconnected" });

      // Server explicitly rejected the token
      if (e.code === 4001) {
        set({ consecutiveFails: 0 });
        get().resetToPin();
        return;
      }

      // Idle timeout — auto-reconnect after 1s
      if (e.code === 4002) {
        set({ consecutiveFails: 0, statusText: "Reconnecting..." });
        const timerId = setTimeout(() => get().connect(), 1000);
        set({ reconnectTimerId: timerId });
        return;
      }

      const fails = get().consecutiveFails + 1;
      set({ consecutiveFails: fails });

      if (fails >= 3) {
        set({ consecutiveFails: 0 });
        get().resetToPin();
        return;
      }

      const timerId = setTimeout(() => get().connect(), 3000);
      set({ reconnectTimerId: timerId });
    };

    ws.onerror = () => ws.close();

    set({ ws });
  },

  disconnect: () => {
    const { ws, reconnectTimerId } = get();
    if (reconnectTimerId) {
      clearTimeout(reconnectTimerId);
    }
    if (ws) {
      ws.close();
    }
    set({ ws: null, reconnectTimerId: null, connectionStatus: "disconnected" });
  },

  send: (msg) => {
    const { ws } = get();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  },

  resetToPin: () => {
    set({ authToken: null, ws: null });
    sessionStorage.removeItem("rain-token");
    // UI store will handle panel switching via the useWebSocket hook
  },
}));
