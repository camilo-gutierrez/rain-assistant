import { create } from "zustand";
import type { WSSendMessage, AIProvider } from "@/lib/types";
import { getWsUrl } from "@/lib/constants";

const TOKEN_STORAGE_KEY = 'rain_session_token';

/**
 * Simple XOR obfuscation for tokens in sessionStorage.
 * NOT cryptographic — prevents casual inspection only.
 * Acceptable because: tokens are ephemeral (session-only),
 * transmitted over WSS, and expire server-side (24h TTL).
 */
function obfuscateToken(token: string): string {
  const key = 'rain_obfuscation_key_2026';
  let result = '';
  for (let i = 0; i < token.length; i++) {
    result += String.fromCharCode(token.charCodeAt(i) ^ key.charCodeAt(i % key.length));
  }
  return btoa(result);
}

function deobfuscateToken(obfuscated: string): string {
  const key = 'rain_obfuscation_key_2026';
  const decoded = atob(obfuscated);
  let result = '';
  for (let i = 0; i < decoded.length; i++) {
    result += String.fromCharCode(decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length));
  }
  return result;
}

function readStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  // Try new obfuscated key first
  const obfuscated = sessionStorage.getItem(TOKEN_STORAGE_KEY);
  if (obfuscated) {
    try {
      return deobfuscateToken(obfuscated);
    } catch {
      return obfuscated; // backward compat: old plain token
    }
  }
  // Backward compat: check old key and migrate
  const old = sessionStorage.getItem('rain-token');
  if (old) {
    sessionStorage.removeItem('rain-token');
    sessionStorage.setItem(TOKEN_STORAGE_KEY, obfuscateToken(old));
    return old;
  }
  return null;
}

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

interface ConnectionState {
  ws: WebSocket | null;
  reconnectTimerId: ReturnType<typeof setTimeout> | null;
  authToken: string | null;
  connectionStatus: ConnectionStatus;
  statusText: string;
  consecutiveFails: number;
  usingApiKey: boolean;
  currentProvider: AIProvider | null;

  setAuthToken: (token: string | null) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setStatusText: (text: string) => void;
  setUsingApiKey: (val: boolean) => void;
  setCurrentProvider: (provider: AIProvider | null) => void;
  connect: () => void;
  disconnect: () => void;
  send: (msg: WSSendMessage) => boolean;
  resetToPin: () => void;
}

export const useConnectionStore = create<ConnectionState>()((set, get) => ({
  ws: null,
  reconnectTimerId: null,
  authToken: readStoredToken(),
  connectionStatus: "disconnected",
  statusText: "",
  consecutiveFails: 0,
  usingApiKey: false,
  currentProvider: null,

  setAuthToken: (token) => {
    if (token) {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, obfuscateToken(token));
    } else {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    // Clean up old key if present
    sessionStorage.removeItem("rain-token");
    set({ authToken: token });
  },

  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setStatusText: (statusText) => set({ statusText }),
  setUsingApiKey: (usingApiKey) => set({ usingApiKey }),
  setCurrentProvider: (currentProvider) => set({ currentProvider }),

  connect: () => {
    const { reconnectTimerId, authToken } = get();

    if (reconnectTimerId) {
      clearTimeout(reconnectTimerId);
      set({ reconnectTimerId: null });
    }

    const wsUrl = getWsUrl();

    set({ connectionStatus: "connecting" });

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      // Send auth token as first message instead of subprotocol
      if (authToken) {
        ws.send(JSON.stringify({ type: 'auth', token: authToken }));
      }
      set({ connectionStatus: "connected", consecutiveFails: 0, statusText: "Connected" });
    };

    // onmessage is handled by useWebSocket hook

    ws.onclose = (e) => {
      set({ connectionStatus: "disconnected", statusText: "Disconnected" });

      // Server explicitly rejected the token or device was revoked
      if (e.code === 4001 || e.code === 4003) {
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
    const { reconnectTimerId } = get();
    if (reconnectTimerId) {
      clearTimeout(reconnectTimerId);
    }
    set({ authToken: null, ws: null, reconnectTimerId: null });
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    sessionStorage.removeItem("rain-token"); // clean up old key
    // UI store will handle panel switching via the useWebSocket hook
  },
}));
