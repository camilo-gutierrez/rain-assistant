"use client";

import { useEffect, useRef } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useMetricsStore } from "@/stores/useMetricsStore";
import { useUIStore } from "@/stores/useUIStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useToastStore } from "@/stores/useToastStore";
import { useTTSStore } from "@/hooks/useTTS";
import { handleToolMessage } from "@/hooks/useToolMessages";
import { handlePermissionMessage } from "@/hooks/usePermissionMessages";
import { handleComputerUseMessage } from "@/hooks/useComputerUseMessages";
import { handleSubAgentMessage } from "@/hooks/useSubAgentMessages";
import { handleVoiceMessage } from "@/hooks/useVoiceMessages";
import type { WSReceiveMessage } from "@/lib/types";
import { synthesize } from "@/lib/api";
import { autoSaveConversation, loadHistoryForAgent } from "@/lib/historyUtils";
import { translate } from "@/lib/translations";

/**
 * Central WebSocket hook — call once in page.tsx.
 * Manages WS lifecycle and routes incoming messages to the appropriate stores.
 *
 * Domain-specific message handling is delegated to focused handlers:
 *  - handleToolMessage       (tool_use, tool_result)
 *  - handlePermissionMessage  (permission_request)
 *  - handleComputerUseMessage (mode_changed, computer_screenshot, computer_action)
 *  - handleSubAgentMessage    (subagent_spawned, subagent_completed)
 */
export function useWebSocket() {
  const ws = useConnectionStore((s) => s.ws);
  const connectionStatus = useConnectionStore((s) => s.connectionStatus);
  const authToken = useConnectionStore((s) => s.authToken);
  const notifiedRef = useRef(false);

  // ── Route incoming WS messages ──
  useEffect(() => {
    if (!ws) return;

    const handleMessage = (e: MessageEvent) => {
      let msg: WSReceiveMessage;
      try { msg = JSON.parse(e.data); } catch { console.error("WS parse error"); return; }

      const agentStore = useAgentStore.getState();
      const connectionStore = useConnectionStore.getState();
      const agentId = ("agent_id" in msg && msg.agent_id) || agentStore.activeAgentId;
      if (!agentId) return;

      // Delegate to domain-specific handlers first
      if (handleToolMessage(msg, agentId)) return;
      if (handlePermissionMessage(msg, agentId)) return;
      if (handleComputerUseMessage(msg, agentId)) return;
      if (handleSubAgentMessage(msg, agentId)) return;
      if (handleVoiceMessage(msg, agentId)) return;

      // Core routing
      switch (msg.type) {
        case "ping":
          connectionStore.send({ type: "pong" });
          break;

        case "api_key_loaded": {
          const provider = msg.provider || "claude";
          useSettingsStore.getState().setAIProvider(provider);
          connectionStore.setUsingApiKey(true);
          connectionStore.setCurrentProvider(provider);
          const ui = useUIStore.getState();
          if (ui.activePanel === "apiKey") ui.setActivePanel("fileBrowser");
          break;
        }

        case "status": {
          if (agentId === agentStore.activeAgentId || !msg.agent_id) {
            connectionStore.setStatusText(msg.text);
            connectionStore.setConnectionStatus("connected");
          }
          if (msg.cwd && agentStore.agents[agentId]) {
            agentStore.setAgentCwd(agentId, msg.cwd);
            if (!agentStore.agents[agentId].historyLoaded) {
              loadHistoryForAgent(msg.cwd, agentId, authToken);
            }
          }
          break;
        }

        case "assistant_text":
          if (!agentStore.agents[agentId]) break;
          agentStore.updateStreamingMessage(agentId, msg.text);
          agentStore.incrementUnread(agentId);
          break;

        case "model_info":
          useMetricsStore.getState().updateModelInfo(msg.model);
          break;

        case "rate_limits":
          useMetricsStore.getState().updateRateLimits(msg.limits);
          break;

        case "result":
          handleResult(msg, agentId, authToken);
          break;

        case "error":
          handleError(msg, agentId);
          break;

        case "agent_destroyed":
          break;

        case "alter_ego_changed":
          useSettingsStore.getState().setActiveEgoId(msg.ego_id || "rain");
          break;
      }
    };

    ws.addEventListener("message", handleMessage);
    return () => ws.removeEventListener("message", handleMessage);
  }, [ws, authToken]);

  // ── On connect: reinit agents on server ──
  useEffect(() => {
    if (connectionStatus === "connected" && !notifiedRef.current) {
      notifiedRef.current = true;
      const send = useConnectionStore.getState().send;
      const { aiProvider, aiModel } = useSettingsStore.getState();
      const storedKey = typeof window !== "undefined"
        ? sessionStorage.getItem(`rain-api-key-${aiProvider}`) : null;
      if (storedKey) send({ type: "set_api_key", key: storedKey, provider: aiProvider, model: aiModel });
      useAgentStore.getState().reinitAgentsOnServer(send);
    }
    if (connectionStatus !== "connected") notifiedRef.current = false;
  }, [connectionStatus]);

  // ── Toast on connection status change ──
  const prevStatusRef = useRef<string>(connectionStatus);
  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = connectionStatus;
    const lang = useSettingsStore.getState().language;
    if (connectionStatus === "disconnected" && prev === "connected") {
      useToastStore.getState().addToast({ type: "warning", message: translate(lang, "toast.connectionLost") });
    }
    if (connectionStatus === "connected" && (prev === "disconnected" || prev === "error")) {
      useToastStore.getState().addToast({ type: "success", message: translate(lang, "toast.connectionRestored") });
    }
  }, [connectionStatus]);
}

// ── Helpers ──

/** Complete an agent turn: clear processing state, set final status. */
function finalizeProcessing(agentId: string, status: "done" | "error") {
  const agentStore = useAgentStore.getState();
  agentStore.setProcessing(agentId, false);
  agentStore.setInterruptPending(agentId, false);
  const agent = agentStore.agents[agentId];
  if (agent?.interruptTimerId) {
    clearTimeout(agent.interruptTimerId);
    agentStore.setInterruptTimer(agentId, null);
  }
  agentStore.setAgentStatus(agentId, status);
}

/** Try TTS auto-play for the last assistant message. */
function maybeAutoPlayTTS(agentId: string, authToken: string | null) {
  const settings = useSettingsStore.getState();
  if (!settings.ttsEnabled || !settings.ttsAutoPlay) return;

  const agent = useAgentStore.getState().agents[agentId];
  if (!agent) return;
  const lastMsg = [...agent.messages].reverse().find((m) => m.type === "assistant");
  if (!lastMsg || lastMsg.type !== "assistant" || !lastMsg.text.trim()) return;

  const ttsStore = useTTSStore.getState();
  ttsStore.setPlaybackState("loading");
  ttsStore.setPlayingMessageId(lastMsg.id);

  const resetTTS = () => {
    useTTSStore.getState().setPlaybackState("idle");
    useTTSStore.getState().setPlayingMessageId(null);
  };

  synthesize(lastMsg.text, settings.ttsVoice, "+0%", authToken)
    .then((blob) => {
      if (!blob) { resetTTS(); return; }
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onplay = () => useTTSStore.getState().setPlaybackState("playing");
      audio.onended = () => { URL.revokeObjectURL(url); resetTTS(); };
      audio.onerror = () => { URL.revokeObjectURL(url); resetTTS(); };
      audio.play().catch(() => { URL.revokeObjectURL(url); resetTTS(); });
    })
    .catch(resetTTS);
}

function handleResult(
  msg: Extract<WSReceiveMessage, { type: "result" }>,
  agentId: string,
  authToken: string | null,
) {
  const agentStore = useAgentStore.getState();
  agentStore.finalizeStreaming(agentId);
  if (msg.usage) useMetricsStore.getState().updateUsageInfo(msg.usage);

  // Append system message with cost/duration info
  if (msg.cost != null || msg.duration_ms != null) {
    let info = "";
    if (msg.duration_ms) info += (msg.duration_ms / 1000).toFixed(1) + "s";
    if (msg.num_turns) info += " | " + msg.num_turns + " turns";
    if (msg.cost) info += " | $" + msg.cost.toFixed(4);
    if (info) {
      agentStore.appendMessage(agentId, {
        id: crypto.randomUUID(), type: "system", text: info,
        timestamp: Date.now(), animate: true,
      });
    }
  }

  if (msg.session_id) agentStore.setAgentSessionId(agentId, msg.session_id);
  autoSaveConversation(agentId, authToken);
  if (!msg.is_error) maybeAutoPlayTTS(agentId, authToken);

  finalizeProcessing(agentId, "done");
  if (agentId === agentStore.activeAgentId) {
    useConnectionStore.getState().setStatusText("Ready");
  }
}

function handleError(
  msg: Extract<WSReceiveMessage, { type: "error" }>,
  agentId: string,
) {
  const agentStore = useAgentStore.getState();
  agentStore.finalizeStreaming(agentId);
  agentStore.appendMessage(agentId, {
    id: crypto.randomUUID(), type: "system", text: "Error: " + msg.text,
    timestamp: Date.now(), animate: true,
  });
  useToastStore.getState().addToast({ type: "error", message: msg.text });

  finalizeProcessing(agentId, "error");
  if (agentId === agentStore.activeAgentId) {
    const cs = useConnectionStore.getState();
    cs.setStatusText(msg.text);
    cs.setConnectionStatus("error");
  }
}
