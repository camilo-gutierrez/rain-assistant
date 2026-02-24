import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAgentStore } from "@/stores/useAgentStore";

// Reset the Zustand store between tests
beforeEach(() => {
  useAgentStore.setState({
    agents: {},
    activeAgentId: null,
    tabCounter: 0,
  });
});

describe("useAgentStore", () => {
  // --- ensureDefaultAgent ---

  describe("ensureDefaultAgent()", () => {
    it("creates a default agent when no agents exist", () => {
      const { ensureDefaultAgent } = useAgentStore.getState();
      ensureDefaultAgent();

      const state = useAgentStore.getState();
      expect(state.agents["default"]).toBeDefined();
      expect(state.agents["default"].label).toBe("Agent 1");
      expect(state.activeAgentId).toBe("default");
    });

    it("does not create a duplicate default agent", () => {
      const { ensureDefaultAgent } = useAgentStore.getState();
      ensureDefaultAgent();
      ensureDefaultAgent();

      const state = useAgentStore.getState();
      expect(Object.keys(state.agents)).toHaveLength(1);
    });

    it("sets activeAgentId to 'default' when it is null", () => {
      const { ensureDefaultAgent } = useAgentStore.getState();
      ensureDefaultAgent();
      expect(useAgentStore.getState().activeAgentId).toBe("default");
    });
  });

  // --- createAgent ---

  describe("createAgent()", () => {
    it("creates a new agent with an auto-generated id", () => {
      const { createAgent } = useAgentStore.getState();
      const id = createAgent();

      const state = useAgentStore.getState();
      expect(state.agents[id]).toBeDefined();
      expect(id).toMatch(/^agent-/);
    });

    it("creates an agent with a given id", () => {
      const { createAgent } = useAgentStore.getState();
      createAgent("my-custom-id");

      const state = useAgentStore.getState();
      expect(state.agents["my-custom-id"]).toBeDefined();
    });

    it("increments tabCounter on each createAgent call", () => {
      const store = useAgentStore.getState();
      store.createAgent();
      expect(useAgentStore.getState().tabCounter).toBe(1);

      useAgentStore.getState().createAgent();
      expect(useAgentStore.getState().tabCounter).toBe(2);
    });

    it("creates agents with correct default properties", () => {
      const { createAgent } = useAgentStore.getState();
      const id = createAgent("test-agent");

      const agent = useAgentStore.getState().agents["test-agent"];
      expect(agent.cwd).toBeNull();
      expect(agent.currentBrowsePath).toBe("~");
      expect(agent.status).toBe("idle");
      expect(agent.unread).toBe(0);
      expect(agent.messages).toEqual([]);
      expect(agent.isProcessing).toBe(false);
      expect(agent.mode).toBe("coding");
      expect(agent.activePanel).toBe("fileBrowser");
      expect(agent.subAgents).toEqual([]);
    });
  });

  // --- switchToAgent ---

  describe("switchToAgent()", () => {
    it("switches the active agent id", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.createAgent("b");

      useAgentStore.getState().switchToAgent("b");
      expect(useAgentStore.getState().activeAgentId).toBe("b");
    });

    it("resets unread count when switching to an agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.createAgent("b");

      // Manually set unread on b
      useAgentStore.setState((s) => ({
        agents: {
          ...s.agents,
          b: { ...s.agents["b"], unread: 5 },
        },
      }));

      useAgentStore.getState().switchToAgent("b");
      expect(useAgentStore.getState().agents["b"].unread).toBe(0);
    });

    it("does nothing when switching to a nonexistent agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.switchToAgent("a");

      useAgentStore.getState().switchToAgent("nonexistent");
      expect(useAgentStore.getState().activeAgentId).toBe("a");
    });
  });

  // --- closeAgent ---

  describe("closeAgent()", () => {
    it("removes an agent and sends destroy_agent message", () => {
      const sendFn = vi.fn();
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.createAgent("b");

      useAgentStore.getState().closeAgent("a", sendFn);

      const state = useAgentStore.getState();
      expect(state.agents["a"]).toBeUndefined();
      expect(state.agents["b"]).toBeDefined();
      expect(sendFn).toHaveBeenCalledWith({
        type: "destroy_agent",
        agent_id: "a",
      });
    });

    it("does not remove the last remaining agent", () => {
      const sendFn = vi.fn();
      const store = useAgentStore.getState();
      store.createAgent("only");

      useAgentStore.getState().closeAgent("only", sendFn);

      expect(useAgentStore.getState().agents["only"]).toBeDefined();
      expect(sendFn).not.toHaveBeenCalled();
    });

    it("switches to another agent when closing the active agent", () => {
      const sendFn = vi.fn();
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.createAgent("b");
      store.switchToAgent("a");

      useAgentStore.getState().closeAgent("a", sendFn);
      expect(useAgentStore.getState().activeAgentId).toBe("b");
    });
  });

  // --- setAgentStatus ---

  describe("setAgentStatus()", () => {
    it("sets the status of an agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      useAgentStore.getState().setAgentStatus("a", "working");
      expect(useAgentStore.getState().agents["a"].status).toBe("working");
    });

    it("ignores nonexistent agents", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      useAgentStore.getState().setAgentStatus("nonexistent", "working");
      // Should not throw; only 'a' should exist
      expect(useAgentStore.getState().agents["a"].status).toBe("idle");
    });
  });

  // --- incrementUnread ---

  describe("incrementUnread()", () => {
    it("increments unread for a non-active agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.createAgent("b");
      store.switchToAgent("a");

      useAgentStore.getState().incrementUnread("b");
      expect(useAgentStore.getState().agents["b"].unread).toBe(1);

      useAgentStore.getState().incrementUnread("b");
      expect(useAgentStore.getState().agents["b"].unread).toBe(2);
    });

    it("does not increment unread for the active agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.switchToAgent("a");

      useAgentStore.getState().incrementUnread("a");
      expect(useAgentStore.getState().agents["a"].unread).toBe(0);
    });
  });

  // --- setAgentCwd ---

  describe("setAgentCwd()", () => {
    it("sets the cwd on an agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      useAgentStore.getState().setAgentCwd("a", "/home/user/project");
      expect(useAgentStore.getState().agents["a"].cwd).toBe(
        "/home/user/project"
      );
    });
  });

  // --- setAgentPanel ---

  describe("setAgentPanel()", () => {
    it("changes the active panel of an agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");
      expect(useAgentStore.getState().agents["a"].activePanel).toBe(
        "fileBrowser"
      );

      useAgentStore.getState().setAgentPanel("a", "chat");
      expect(useAgentStore.getState().agents["a"].activePanel).toBe("chat");
    });
  });

  // --- Message actions ---

  describe("appendMessage()", () => {
    it("appends a message to the agent's message list", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      const msg = {
        id: "msg-1",
        type: "user" as const,
        text: "Hello",
        timestamp: Date.now(),
        animate: false,
      };

      useAgentStore.getState().appendMessage("a", msg);
      expect(useAgentStore.getState().agents["a"].messages).toHaveLength(1);
      expect(useAgentStore.getState().agents["a"].messages[0]).toEqual(msg);
    });
  });

  describe("clearMessages()", () => {
    it("clears all messages and resets streaming state", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      const msg = {
        id: "msg-1",
        type: "user" as const,
        text: "Hello",
        timestamp: Date.now(),
        animate: false,
      };
      useAgentStore.getState().appendMessage("a", msg);
      expect(useAgentStore.getState().agents["a"].messages).toHaveLength(1);

      useAgentStore.getState().clearMessages("a");
      const agent = useAgentStore.getState().agents["a"];
      expect(agent.messages).toEqual([]);
      expect(agent.streamText).toBe("");
      expect(agent.streamMessageId).toBeNull();
    });
  });

  describe("setMessages()", () => {
    it("replaces the entire messages array", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      const msgs = [
        {
          id: "m1",
          type: "user" as const,
          text: "First",
          timestamp: 1,
          animate: false,
        },
        {
          id: "m2",
          type: "assistant" as const,
          text: "Second",
          timestamp: 2,
          animate: false,
          isStreaming: false,
        },
      ];

      useAgentStore.getState().setMessages("a", msgs);
      expect(useAgentStore.getState().agents["a"].messages).toEqual(msgs);
    });
  });

  // --- Processing state ---

  describe("setProcessing()", () => {
    it("sets isProcessing on an agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      useAgentStore.getState().setProcessing("a", true);
      expect(useAgentStore.getState().agents["a"].isProcessing).toBe(true);

      useAgentStore.getState().setProcessing("a", false);
      expect(useAgentStore.getState().agents["a"].isProcessing).toBe(false);
    });
  });

  // --- Computer Use ---

  describe("setAgentMode()", () => {
    it("sets mode and resets computer use state", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      // Set some computer use state first
      useAgentStore.setState((s) => ({
        agents: {
          ...s.agents,
          a: {
            ...s.agents["a"],
            computerIteration: 5,
            lastScreenshot: "base64data",
          },
        },
      }));

      useAgentStore.getState().setAgentMode("a", "computer_use");
      const agent = useAgentStore.getState().agents["a"];
      expect(agent.mode).toBe("computer_use");
      expect(agent.computerIteration).toBe(0);
      expect(agent.lastScreenshot).toBeNull();
    });
  });

  describe("incrementComputerIteration()", () => {
    it("increments the computer iteration counter", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      useAgentStore.getState().incrementComputerIteration("a");
      expect(useAgentStore.getState().agents["a"].computerIteration).toBe(1);

      useAgentStore.getState().incrementComputerIteration("a");
      expect(useAgentStore.getState().agents["a"].computerIteration).toBe(2);
    });
  });

  // --- Sub-agents ---

  describe("sub-agents", () => {
    it("addSubAgent adds a sub-agent to the parent", () => {
      const store = useAgentStore.getState();
      store.createAgent("parent");

      const subInfo = {
        id: "sub-1",
        shortName: "Research",
        parentId: "parent",
        task: "Search for info",
        status: "running" as const,
      };

      useAgentStore.getState().addSubAgent("parent", subInfo);
      expect(
        useAgentStore.getState().agents["parent"].subAgents
      ).toHaveLength(1);
      expect(useAgentStore.getState().agents["parent"].subAgents[0]).toEqual(
        subInfo
      );
    });

    it("updateSubAgentStatus updates a sub-agent's status", () => {
      const store = useAgentStore.getState();
      store.createAgent("parent");

      const subInfo = {
        id: "sub-1",
        shortName: "Research",
        parentId: "parent",
        task: "Search for info",
        status: "running" as const,
      };

      useAgentStore.getState().addSubAgent("parent", subInfo);
      useAgentStore
        .getState()
        .updateSubAgentStatus("parent", "sub-1", "completed");

      expect(
        useAgentStore.getState().agents["parent"].subAgents[0].status
      ).toBe("completed");
    });

    it("removeSubAgent removes a sub-agent from the parent", () => {
      const store = useAgentStore.getState();
      store.createAgent("parent");

      useAgentStore.getState().addSubAgent("parent", {
        id: "sub-1",
        shortName: "A",
        parentId: "parent",
        task: "Task A",
        status: "running",
      });
      useAgentStore.getState().addSubAgent("parent", {
        id: "sub-2",
        shortName: "B",
        parentId: "parent",
        task: "Task B",
        status: "running",
      });

      useAgentStore.getState().removeSubAgent("parent", "sub-1");
      const subs = useAgentStore.getState().agents["parent"].subAgents;
      expect(subs).toHaveLength(1);
      expect(subs[0].id).toBe("sub-2");
    });
  });

  // --- getActiveAgent ---

  describe("getActiveAgent()", () => {
    it("returns the active agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");
      store.switchToAgent("a");

      const active = useAgentStore.getState().getActiveAgent();
      expect(active).not.toBeNull();
      expect(active!.id).toBe("a");
    });

    it("returns null when no active agent is set", () => {
      expect(useAgentStore.getState().getActiveAgent()).toBeNull();
    });
  });

  // --- saveScrollPos ---

  describe("saveScrollPos()", () => {
    it("saves a scroll position for an agent", () => {
      const store = useAgentStore.getState();
      store.createAgent("a");

      useAgentStore.getState().saveScrollPos("a", 420);
      expect(useAgentStore.getState().agents["a"].scrollPos).toBe(420);
    });
  });
});
