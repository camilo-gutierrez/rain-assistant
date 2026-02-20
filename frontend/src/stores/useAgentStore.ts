import { create } from "zustand";
import type { Agent, AgentMode, AgentPanel, AgentStatus, AnyMessage, DisplayInfo, PermissionRequestMessage, SubAgentInfo, WSSendMessage } from "@/lib/types";

interface AgentState {
  agents: Record<string, Agent>;
  activeAgentId: string | null;
  tabCounter: number;

  // Agent lifecycle
  ensureDefaultAgent: () => void;
  createAgent: (agentId?: string | null) => string;
  switchToAgent: (agentId: string) => void;
  closeAgent: (agentId: string, sendFn: (msg: WSSendMessage) => void) => void;
  setAgentStatus: (agentId: string, status: AgentStatus) => void;
  incrementUnread: (agentId: string) => void;
  setAgentCwd: (agentId: string, cwd: string) => void;
  setAgentBrowsePath: (agentId: string, path: string) => void;
  setAgentPanel: (agentId: string, panel: AgentPanel) => void;

  // Message actions
  appendMessage: (agentId: string, message: AnyMessage) => void;
  updateStreamingMessage: (agentId: string, text: string) => void;
  finalizeStreaming: (agentId: string) => void;
  clearMessages: (agentId: string) => void;
  setMessages: (agentId: string, messages: AnyMessage[]) => void;
  setHistoryLoaded: (agentId: string, val: boolean) => void;
  setAgentSessionId: (agentId: string, sessionId: string | null) => void;

  // Permission
  updatePermissionStatus: (agentId: string, requestId: string, status: PermissionRequestMessage["status"]) => void;

  // Computer Use
  setAgentMode: (agentId: string, mode: AgentMode) => void;
  setDisplayInfo: (agentId: string, info: DisplayInfo) => void;
  updateLastScreenshot: (agentId: string, image: string) => void;
  incrementComputerIteration: (agentId: string) => void;

  // Processing state
  setProcessing: (agentId: string, val: boolean) => void;
  setInterruptPending: (agentId: string, val: boolean) => void;
  setInterruptTimer: (agentId: string, timerId: ReturnType<typeof setTimeout> | null) => void;

  // Sub-agents
  addSubAgent: (parentId: string, info: SubAgentInfo) => void;
  updateSubAgentStatus: (parentId: string, subId: string, status: SubAgentInfo["status"]) => void;
  removeSubAgent: (parentId: string, subId: string) => void;

  // Scroll
  saveScrollPos: (agentId: string, pos: number) => void;

  // Helpers
  getActiveAgent: () => Agent | null;
  reinitAgentsOnServer: (sendFn: (msg: WSSendMessage) => void) => void;
}

function uniqueAgentId(counter: number): string {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 6);
  return `agent-${counter}-${ts}-${rand}`;
}

function createAgentObject(id: string, label: string): Agent {
  return {
    id,
    cwd: null,
    currentBrowsePath: "~",
    label,
    status: "idle",
    unread: 0,
    messages: [],
    scrollPos: 0,
    streamText: "",
    streamMessageId: null,
    isProcessing: false,
    interruptPending: false,
    interruptTimerId: null,
    historyLoaded: false,
    sessionId: null,
    activePanel: "fileBrowser",
    // Computer Use
    mode: "coding",
    displayInfo: null,
    lastScreenshot: null,
    computerIteration: 0,
    // Sub-agents
    subAgents: [],
  };
}

export const useAgentStore = create<AgentState>()((set, get) => ({
  agents: {},
  activeAgentId: null,
  tabCounter: 0,

  ensureDefaultAgent: () => {
    const { agents, activeAgentId } = get();
    if (Object.keys(agents).length === 0) {
      get().createAgent("default");
    }
    if (!activeAgentId) {
      set({ activeAgentId: "default" });
    }
  },

  createAgent: (agentId = null) => {
    const { tabCounter, agents } = get();
    const isDefault = agentId === "default";
    const newCounter = tabCounter + 1;

    if (!agentId) {
      agentId = uniqueAgentId(newCounter);
    }

    const label = isDefault ? "Agent 1" : `Agent ${newCounter + 1}`;
    const agent = createAgentObject(agentId, label);

    set({
      agents: { ...agents, [agentId]: agent },
      tabCounter: newCounter,
    });

    return agentId;
  },

  switchToAgent: (agentId) => {
    const { agents } = get();
    if (!agents[agentId]) return;

    set((state) => ({
      activeAgentId: agentId,
      agents: {
        ...state.agents,
        [agentId]: { ...state.agents[agentId], unread: 0 },
      },
    }));
  },

  closeAgent: (agentId, sendFn) => {
    const { agents, activeAgentId } = get();
    const agentKeys = Object.keys(agents);
    if (agentKeys.length <= 1) return;

    const agent = agents[agentId];
    if (!agent) return;

    // Clear any pending timers
    if (agent.interruptTimerId) {
      clearTimeout(agent.interruptTimerId);
    }

    // Tell server to destroy this agent
    sendFn({ type: "destroy_agent", agent_id: agentId });

    const newAgents = { ...agents };
    delete newAgents[agentId];

    // If we closed the active tab, switch to another
    let newActiveId = activeAgentId;
    if (activeAgentId === agentId) {
      newActiveId = Object.keys(newAgents)[0];
    }

    set({ agents: newAgents, activeAgentId: newActiveId });
  },

  setAgentStatus: (agentId, status) => {
    const { agents } = get();
    if (!agents[agentId]) return;

    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], status },
      },
    });

    // Flash "done" status briefly, then revert to idle
    if (status === "done") {
      setTimeout(() => {
        const current = get().agents[agentId];
        if (current && current.status === "done") {
          get().setAgentStatus(agentId, "idle");
        }
      }, 3000);
    }
  },

  incrementUnread: (agentId) => {
    const { agents, activeAgentId } = get();
    if (agentId === activeAgentId) return;
    if (!agents[agentId]) return;

    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], unread: agents[agentId].unread + 1 },
      },
    });
  },

  setAgentCwd: (agentId, cwd) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], cwd },
      },
    });
  },

  setAgentBrowsePath: (agentId, path) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], currentBrowsePath: path },
      },
    });
  },

  setAgentPanel: (agentId, panel) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], activePanel: panel },
      },
    });
  },

  // --- Message actions ---

  appendMessage: (agentId, message) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: {
          ...agents[agentId],
          messages: [...agents[agentId].messages, message],
        },
      },
    });
  },

  updateStreamingMessage: (agentId, text) => {
    const { agents } = get();
    const agent = agents[agentId];
    if (!agent) return;

    const newStreamText = agent.streamText + text;

    // If no streaming message exists, create one
    if (!agent.streamMessageId) {
      const msgId = crypto.randomUUID();
      set({
        agents: {
          ...agents,
          [agentId]: {
            ...agent,
            streamText: newStreamText,
            streamMessageId: msgId,
            messages: [
              ...agent.messages,
              {
                id: msgId,
                type: "assistant",
                text: newStreamText,
                isStreaming: true,
                timestamp: Date.now(),
                animate: true,
              },
            ],
          },
        },
      });
    } else {
      // Update existing streaming message
      const messages = agent.messages.map((m) =>
        m.id === agent.streamMessageId && m.type === "assistant"
          ? { ...m, text: newStreamText }
          : m
      );
      set({
        agents: {
          ...agents,
          [agentId]: {
            ...agent,
            streamText: newStreamText,
            messages,
          },
        },
      });
    }
  },

  finalizeStreaming: (agentId) => {
    const { agents } = get();
    const agent = agents[agentId];
    if (!agent || !agent.streamMessageId) return;

    const messages = agent.messages.map((m) =>
      m.id === agent.streamMessageId && m.type === "assistant"
        ? { ...m, isStreaming: false, text: agent.streamText }
        : m
    );

    set({
      agents: {
        ...agents,
        [agentId]: {
          ...agent,
          streamText: "",
          streamMessageId: null,
          messages,
        },
      },
    });
  },

  clearMessages: (agentId) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: {
          ...agents[agentId],
          messages: [],
          streamText: "",
          streamMessageId: null,
        },
      },
    });
  },

  setMessages: (agentId, messages) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: {
          ...agents[agentId],
          messages,
          streamText: "",
          streamMessageId: null,
        },
      },
    });
  },

  setHistoryLoaded: (agentId, val) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], historyLoaded: val },
      },
    });
  },

  setAgentSessionId: (agentId, sessionId) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], sessionId },
      },
    });
  },

  // --- Permission ---

  updatePermissionStatus: (agentId, requestId, status) => {
    const { agents } = get();
    const agent = agents[agentId];
    if (!agent) return;

    const messages = agent.messages.map((m) =>
      m.type === "permission_request" && m.requestId === requestId
        ? { ...m, status }
        : m
    );

    set({
      agents: {
        ...agents,
        [agentId]: { ...agent, messages },
      },
    });
  },

  // --- Computer Use ---

  setAgentMode: (agentId, mode) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], mode, computerIteration: 0, lastScreenshot: null },
      },
    });
  },

  setDisplayInfo: (agentId, info) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], displayInfo: info },
      },
    });
  },

  updateLastScreenshot: (agentId, image) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], lastScreenshot: image },
      },
    });
  },

  incrementComputerIteration: (agentId) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], computerIteration: agents[agentId].computerIteration + 1 },
      },
    });
  },

  // --- Processing state ---

  setProcessing: (agentId, val) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], isProcessing: val },
      },
    });
  },

  setInterruptPending: (agentId, val) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], interruptPending: val },
      },
    });
  },

  setInterruptTimer: (agentId, timerId) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], interruptTimerId: timerId },
      },
    });
  },

  // --- Sub-agents ---

  addSubAgent: (parentId, info) => {
    const { agents } = get();
    const parent = agents[parentId];
    if (!parent) return;
    set({
      agents: {
        ...agents,
        [parentId]: {
          ...parent,
          subAgents: [...parent.subAgents, info],
        },
      },
    });
  },

  updateSubAgentStatus: (parentId, subId, status) => {
    const { agents } = get();
    const parent = agents[parentId];
    if (!parent) return;
    set({
      agents: {
        ...agents,
        [parentId]: {
          ...parent,
          subAgents: parent.subAgents.map((sa) =>
            sa.id === subId ? { ...sa, status } : sa
          ),
        },
      },
    });
  },

  removeSubAgent: (parentId, subId) => {
    const { agents } = get();
    const parent = agents[parentId];
    if (!parent) return;
    set({
      agents: {
        ...agents,
        [parentId]: {
          ...parent,
          subAgents: parent.subAgents.filter((sa) => sa.id !== subId),
        },
      },
    });
  },

  // --- Scroll ---

  saveScrollPos: (agentId, pos) => {
    const { agents } = get();
    if (!agents[agentId]) return;
    set({
      agents: {
        ...agents,
        [agentId]: { ...agents[agentId], scrollPos: pos },
      },
    });
  },

  // --- Helpers ---

  getActiveAgent: () => {
    const { agents, activeAgentId } = get();
    return activeAgentId ? agents[activeAgentId] || null : null;
  },

  reinitAgentsOnServer: (sendFn) => {
    const { agents } = get();
    const updatedAgents = { ...agents };

    for (const [agentId, agent] of Object.entries(agents)) {
      if (agent.cwd) {
        const msg: WSSendMessage = { type: "set_cwd", path: agent.cwd, agent_id: agentId };
        if (agent.sessionId) msg.session_id = agent.sessionId;
        sendFn(msg);
      }
      // Reset processing state since server lost context
      if (agent.isProcessing) {
        updatedAgents[agentId] = {
          ...agent,
          isProcessing: false,
          interruptPending: false,
          interruptTimerId: null,
          status: "idle",
        };
        if (agent.interruptTimerId) {
          clearTimeout(agent.interruptTimerId);
        }
      }
    }

    set({ agents: updatedAgents });
  },
}));
