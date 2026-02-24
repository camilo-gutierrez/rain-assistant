import { describe, it, expect, beforeEach, vi } from "vitest";
import { useConnectionStore } from "@/stores/useConnectionStore";

// Reset store between tests
beforeEach(() => {
  // Clear any pending timers
  vi.useRealTimers();
  const { reconnectTimerId } = useConnectionStore.getState();
  if (reconnectTimerId) clearTimeout(reconnectTimerId);

  useConnectionStore.setState({
    ws: null,
    reconnectTimerId: null,
    authToken: null,
    connectionStatus: "disconnected",
    statusText: "",
    consecutiveFails: 0,
    usingApiKey: false,
    currentProvider: null,
  });
});

describe("useConnectionStore", () => {
  // --- Initial state ---

  describe("initial state", () => {
    it("starts disconnected with no token", () => {
      const state = useConnectionStore.getState();
      expect(state.connectionStatus).toBe("disconnected");
      expect(state.ws).toBeNull();
      expect(state.reconnectTimerId).toBeNull();
      expect(state.consecutiveFails).toBe(0);
      expect(state.usingApiKey).toBe(false);
      expect(state.currentProvider).toBeNull();
    });
  });

  // --- setAuthToken ---

  describe("setAuthToken()", () => {
    it("stores a token", () => {
      useConnectionStore.getState().setAuthToken("test-token-123");
      expect(useConnectionStore.getState().authToken).toBe("test-token-123");
    });

    it("clears the token when set to null", () => {
      useConnectionStore.getState().setAuthToken("test-token-123");
      useConnectionStore.getState().setAuthToken(null);
      expect(useConnectionStore.getState().authToken).toBeNull();
    });

    it("persists token to sessionStorage (obfuscated)", () => {
      useConnectionStore.getState().setAuthToken("my-secret-token");
      const stored = sessionStorage.getItem("rain_session_token");
      expect(stored).not.toBeNull();
      // Should NOT be stored as plaintext
      expect(stored).not.toBe("my-secret-token");
    });

    it("removes token from sessionStorage when set to null", () => {
      useConnectionStore.getState().setAuthToken("token");
      useConnectionStore.getState().setAuthToken(null);
      expect(sessionStorage.getItem("rain_session_token")).toBeNull();
    });
  });

  // --- setConnectionStatus ---

  describe("setConnectionStatus()", () => {
    it("updates connection status", () => {
      useConnectionStore.getState().setConnectionStatus("connecting");
      expect(useConnectionStore.getState().connectionStatus).toBe("connecting");
    });
  });

  // --- setStatusText ---

  describe("setStatusText()", () => {
    it("sets status text", () => {
      useConnectionStore.getState().setStatusText("Connected");
      expect(useConnectionStore.getState().statusText).toBe("Connected");
    });
  });

  // --- setUsingApiKey ---

  describe("setUsingApiKey()", () => {
    it("toggles API key usage flag", () => {
      useConnectionStore.getState().setUsingApiKey(true);
      expect(useConnectionStore.getState().usingApiKey).toBe(true);

      useConnectionStore.getState().setUsingApiKey(false);
      expect(useConnectionStore.getState().usingApiKey).toBe(false);
    });
  });

  // --- setCurrentProvider ---

  describe("setCurrentProvider()", () => {
    it("sets current provider", () => {
      useConnectionStore.getState().setCurrentProvider("openai");
      expect(useConnectionStore.getState().currentProvider).toBe("openai");
    });

    it("clears provider when set to null", () => {
      useConnectionStore.getState().setCurrentProvider("claude");
      useConnectionStore.getState().setCurrentProvider(null);
      expect(useConnectionStore.getState().currentProvider).toBeNull();
    });
  });

  // --- send ---

  describe("send()", () => {
    it("returns false when no WebSocket is connected", () => {
      const result = useConnectionStore.getState().send({
        type: "send_message",
        text: "hello",
        agent_id: "default",
      });
      expect(result).toBe(false);
    });

    it("sends message when WebSocket is open", () => {
      const sendFn = vi.fn();
      const mockWs = { readyState: WebSocket.OPEN, send: sendFn } as unknown as WebSocket;
      useConnectionStore.setState({ ws: mockWs });

      const result = useConnectionStore.getState().send({
        type: "send_message",
        text: "hello",
        agent_id: "default",
      });

      expect(result).toBe(true);
      expect(sendFn).toHaveBeenCalledTimes(1);
    });

    it("returns false when WebSocket is not in OPEN state", () => {
      const mockWs = { readyState: WebSocket.CLOSING, send: vi.fn() } as unknown as WebSocket;
      useConnectionStore.setState({ ws: mockWs });

      const result = useConnectionStore.getState().send({
        type: "send_message",
        text: "test",
        agent_id: "default",
      });
      expect(result).toBe(false);
    });
  });

  // --- resetToPin ---

  describe("resetToPin()", () => {
    it("clears auth token and WebSocket", () => {
      useConnectionStore.setState({
        authToken: "some-token",
        ws: {} as WebSocket,
      });

      useConnectionStore.getState().resetToPin();

      const state = useConnectionStore.getState();
      expect(state.authToken).toBeNull();
      expect(state.ws).toBeNull();
    });

    it("clears sessionStorage tokens", () => {
      sessionStorage.setItem("rain_session_token", "obfuscated-data");
      sessionStorage.setItem("rain-token", "old-token");

      useConnectionStore.getState().resetToPin();

      expect(sessionStorage.getItem("rain_session_token")).toBeNull();
      expect(sessionStorage.getItem("rain-token")).toBeNull();
    });

    it("clears pending reconnect timer", () => {
      vi.useFakeTimers();
      const timerId = setTimeout(() => {}, 5000);
      useConnectionStore.setState({ reconnectTimerId: timerId });

      useConnectionStore.getState().resetToPin();

      expect(useConnectionStore.getState().reconnectTimerId).toBeNull();
      vi.useRealTimers();
    });
  });

  // --- disconnect ---

  describe("disconnect()", () => {
    it("closes WebSocket and resets state", () => {
      const closeFn = vi.fn();
      const mockWs = { close: closeFn } as unknown as WebSocket;
      useConnectionStore.setState({ ws: mockWs });

      useConnectionStore.getState().disconnect();

      expect(closeFn).toHaveBeenCalledTimes(1);
      expect(useConnectionStore.getState().ws).toBeNull();
      expect(useConnectionStore.getState().connectionStatus).toBe("disconnected");
    });

    it("clears reconnect timer on disconnect", () => {
      vi.useFakeTimers();
      const timerId = setTimeout(() => {}, 5000);
      useConnectionStore.setState({
        reconnectTimerId: timerId,
        ws: { close: vi.fn() } as unknown as WebSocket,
      });

      useConnectionStore.getState().disconnect();

      expect(useConnectionStore.getState().reconnectTimerId).toBeNull();
      vi.useRealTimers();
    });
  });
});
