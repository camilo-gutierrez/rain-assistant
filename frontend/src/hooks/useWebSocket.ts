"use client";

import { useEffect, useRef } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useMetricsStore } from "@/stores/useMetricsStore";
import { useUIStore } from "@/stores/useUIStore";
import type { WSReceiveMessage, AnyMessage } from "@/lib/types";
import { loadMessages } from "@/lib/api";

/**
 * Central WebSocket hook — call once in page.tsx.
 * Manages WS lifecycle and routes incoming messages to the appropriate stores.
 */
export function useWebSocket() {
  const ws = useConnectionStore((s) => s.ws);
  const connectionStatus = useConnectionStore((s) => s.connectionStatus);
  const authToken = useConnectionStore((s) => s.authToken);
  const notifiedRef = useRef(false);

  useEffect(() => {
    if (!ws) return;

    const handleMessage = (e: MessageEvent) => {
      let msg: WSReceiveMessage;
      try {
        msg = JSON.parse(e.data);
      } catch {
        console.error("WS parse error");
        return;
      }

      const agentStore = useAgentStore.getState();
      const metricsStore = useMetricsStore.getState();
      const connectionStore = useConnectionStore.getState();
      const agentId = ("agent_id" in msg && msg.agent_id) || agentStore.activeAgentId;
      if (!agentId) return;

      switch (msg.type) {
        case "status": {
          if (agentId === agentStore.activeAgentId || !msg.agent_id) {
            connectionStore.setStatusText(msg.text);
            connectionStore.setConnectionStatus("connected");
          }
          if (msg.cwd && agentStore.agents[agentId]) {
            agentStore.setAgentCwd(agentId, msg.cwd);
            // Load history when we get the resolved cwd from server
            loadHistoryForAgent(msg.cwd, agentId, authToken);
          }
          break;
        }

        case "assistant_text": {
          if (!agentStore.agents[agentId]) break;
          agentStore.updateStreamingMessage(agentId, msg.text);
          agentStore.incrementUnread(agentId);
          break;
        }

        case "tool_use": {
          if (!agentStore.agents[agentId]) break;
          agentStore.finalizeStreaming(agentId);
          const toolMsg: AnyMessage = {
            id: crypto.randomUUID(),
            type: "tool_use",
            tool: msg.tool,
            input: msg.input,
            toolUseId: msg.id,
            timestamp: Date.now(),
            animate: true,
          };
          agentStore.appendMessage(agentId, toolMsg);
          agentStore.incrementUnread(agentId);
          break;
        }

        case "tool_result": {
          if (!agentStore.agents[agentId]) break;
          const resultMsg: AnyMessage = {
            id: crypto.randomUUID(),
            type: "tool_result",
            content: msg.content,
            isError: msg.is_error,
            toolUseId: msg.tool_use_id,
            timestamp: Date.now(),
            animate: true,
          };
          agentStore.appendMessage(agentId, resultMsg);
          agentStore.incrementUnread(agentId);
          break;
        }

        case "model_info": {
          metricsStore.updateModelInfo(msg.model);
          break;
        }

        case "rate_limits": {
          metricsStore.updateRateLimits(msg.limits);
          break;
        }

        case "result": {
          agentStore.finalizeStreaming(agentId);
          if (msg.usage) metricsStore.updateUsageInfo(msg.usage);

          // Append system message with cost/duration info
          if (msg.cost != null || msg.duration_ms != null) {
            let info = "";
            if (msg.duration_ms) info += (msg.duration_ms / 1000).toFixed(1) + "s";
            if (msg.num_turns) info += " | " + msg.num_turns + " turns";
            if (msg.cost) info += " | $" + msg.cost.toFixed(4);
            if (info) {
              agentStore.appendMessage(agentId, {
                id: crypto.randomUUID(),
                type: "system",
                text: info,
                timestamp: Date.now(),
                animate: true,
              });
            }
          }

          // Complete processing
          agentStore.setProcessing(agentId, false);
          agentStore.setInterruptPending(agentId, false);
          const agent = agentStore.agents[agentId];
          if (agent?.interruptTimerId) {
            clearTimeout(agent.interruptTimerId);
            agentStore.setInterruptTimer(agentId, null);
          }
          agentStore.setAgentStatus(agentId, "done");

          if (agentId === agentStore.activeAgentId) {
            connectionStore.setStatusText("Ready");
          }
          break;
        }

        case "error": {
          agentStore.finalizeStreaming(agentId);
          agentStore.appendMessage(agentId, {
            id: crypto.randomUUID(),
            type: "system",
            text: "Error: " + msg.text,
            timestamp: Date.now(),
            animate: true,
          });

          // Complete processing with error status
          agentStore.setProcessing(agentId, false);
          agentStore.setInterruptPending(agentId, false);
          const errAgent = agentStore.agents[agentId];
          if (errAgent?.interruptTimerId) {
            clearTimeout(errAgent.interruptTimerId);
            agentStore.setInterruptTimer(agentId, null);
          }
          agentStore.setAgentStatus(agentId, "error");

          if (agentId === agentStore.activeAgentId) {
            connectionStore.setStatusText(msg.text);
            connectionStore.setConnectionStatus("error");
          }
          break;
        }

        case "agent_destroyed":
          // Handled client-side by closeAgent
          break;
      }
    };

    ws.addEventListener("message", handleMessage);
    return () => ws.removeEventListener("message", handleMessage);
  }, [ws, authToken]);

  // On connect, reinit agents on server
  useEffect(() => {
    if (connectionStatus === "connected" && !notifiedRef.current) {
      notifiedRef.current = true;
      const agentStore = useAgentStore.getState();
      const send = useConnectionStore.getState().send;
      agentStore.reinitAgentsOnServer(send);
    }
    if (connectionStatus !== "connected") {
      notifiedRef.current = false;
    }
  }, [connectionStatus]);
}

async function loadHistoryForAgent(
  cwd: string,
  agentId: string,
  authToken: string | null
) {
  try {
    const data = await loadMessages(cwd, agentId, authToken);
    if (!data.messages || data.messages.length === 0) return;

    const messages: AnyMessage[] = [];
    for (const msg of data.messages) {
      switch (msg.type) {
        case "text":
          messages.push({
            id: crypto.randomUUID(),
            type: "user",
            text: (msg.content as { text: string }).text,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "assistant_text":
          messages.push({
            id: crypto.randomUUID(),
            type: "assistant",
            text: (msg.content as { text: string }).text,
            isStreaming: false,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "tool_use":
          messages.push({
            id: crypto.randomUUID(),
            type: "tool_use",
            tool: (msg.content as { tool: string }).tool,
            input: (msg.content as { input: Record<string, unknown> }).input || {},
            toolUseId: (msg.content as { id: string }).id,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "tool_result":
          messages.push({
            id: crypto.randomUUID(),
            type: "tool_result",
            content: (msg.content as { content: string }).content,
            isError: (msg.content as { is_error: boolean }).is_error,
            toolUseId: (msg.content as { tool_use_id: string }).tool_use_id,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
        case "result": {
          const r = msg.content as {
            cost?: number;
            duration_ms?: number;
            num_turns?: number;
          };
          if (r.cost != null || r.duration_ms != null) {
            let info = "";
            if (r.duration_ms) info += (r.duration_ms / 1000).toFixed(1) + "s";
            if (r.num_turns) info += " | " + r.num_turns + " turns";
            if (r.cost) info += " | $" + r.cost.toFixed(4);
            if (info) {
              messages.push({
                id: crypto.randomUUID(),
                type: "system",
                text: info,
                timestamp: msg.timestamp,
                animate: false,
              });
            }
          }
          break;
        }
        case "error":
          messages.push({
            id: crypto.randomUUID(),
            type: "system",
            text: "Error: " + (msg.content as { text: string }).text,
            timestamp: msg.timestamp,
            animate: false,
          });
          break;
      }
    }

    useAgentStore.getState().setMessages(agentId, messages);
  } catch (err) {
    console.warn("Failed to load history:", err);
  }
}
