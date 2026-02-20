import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../models/agent.dart';
import '../models/message.dart';

const _uuid = Uuid();

class AgentState {
  final Map<String, Agent> agents;
  final String activeAgentId;

  const AgentState({
    this.agents = const {},
    this.activeAgentId = '',
  });

  Agent? get activeAgent => agents[activeAgentId];

  AgentState copyWith({
    Map<String, Agent>? agents,
    String? activeAgentId,
  }) =>
      AgentState(
        agents: agents ?? this.agents,
        activeAgentId: activeAgentId ?? this.activeAgentId,
      );
}

class AgentNotifier extends StateNotifier<AgentState> {
  AgentNotifier() : super(const AgentState());

  /// Create a new agent and set it as active.
  String createAgent({String? label}) {
    final id = 'agent_${_uuid.v4().substring(0, 8)}';
    final agent = Agent(
      id: id,
      label: label ?? 'Agent ${state.agents.length + 1}',
    );
    state = state.copyWith(
      agents: {...state.agents, id: agent},
      activeAgentId: id,
    );
    return id;
  }

  /// Ensure at least one agent exists, return its ID.
  String ensureDefaultAgent() {
    if (state.agents.isEmpty) {
      return createAgent(label: 'Rain');
    }
    return state.activeAgentId;
  }

  void setActiveAgent(String id) {
    if (state.agents.containsKey(id)) {
      // Reset unread for the agent being activated
      final agent = state.agents[id]!;
      agent.unread = 0;
      state = state.copyWith(
        agents: {...state.agents, id: agent},
        activeAgentId: id,
      );
    }
  }

  void removeAgent(String id) {
    final newAgents = Map<String, Agent>.from(state.agents)..remove(id);
    String newActive = state.activeAgentId;
    if (newActive == id) {
      newActive = newAgents.isEmpty ? '' : newAgents.keys.first;
    }
    state = state.copyWith(agents: newAgents, activeAgentId: newActive);
  }

  void renameAgent(String agentId, String newLabel) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.label = newLabel;
    _notify();
  }

  void setAgentCwd(String agentId, String cwd) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.cwd = cwd;
    _notify();
  }

  void setAgentStatus(String agentId, AgentStatus status) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.status = status;
    _notify();
  }

  void setProcessing(String agentId, bool processing) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.isProcessing = processing;
    _notify();
  }

  void setInterruptPending(String agentId, bool pending) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.interruptPending = pending;
    _notify();
  }

  void setAgentSessionId(String agentId, String sessionId) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.sessionId = sessionId;
    _notify();
  }

  void setHistoryLoaded(String agentId, bool loaded) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.historyLoaded = loaded;
    _notify();
  }

  void setAgentMode(String agentId, AgentMode mode) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.mode = mode;
    _notify();
  }

  void setDisplayInfo(String agentId, DisplayInfo info) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.displayInfo = info;
    _notify();
  }

  // ── Message management ──

  void appendMessage(String agentId, Message message) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.messages.add(message);
    _notify();
  }

  void setMessages(String agentId, List<Message> messages) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.messages = messages;
    _notify();
  }

  void incrementUnread(String agentId) {
    final agent = state.agents[agentId];
    if (agent == null || agentId == state.activeAgentId) return;
    agent.unread++;
    _notify();
  }

  /// Accumulate streaming text and update/create the streaming message.
  void updateStreamingMessage(String agentId, String textChunk) {
    final agent = state.agents[agentId];
    if (agent == null) return;

    agent.streamText += textChunk;

    if (agent.streamMessageId != null) {
      // Update existing streaming message
      final idx = agent.messages.indexWhere((m) => m.id == agent.streamMessageId);
      if (idx >= 0 && agent.messages[idx] is AssistantMessage) {
        agent.messages[idx] = (agent.messages[idx] as AssistantMessage).copyWith(
          text: agent.streamText,
        );
      }
    } else {
      // Create new streaming message
      final id = _uuid.v4();
      agent.streamMessageId = id;
      agent.messages.add(AssistantMessage(
        id: id,
        text: agent.streamText,
        isStreaming: true,
        timestamp: DateTime.now().millisecondsSinceEpoch,
      ));
    }
    _notify();
  }

  /// Finalize the current streaming message.
  void finalizeStreaming(String agentId) {
    final agent = state.agents[agentId];
    if (agent == null || agent.streamMessageId == null) return;

    final idx = agent.messages.indexWhere((m) => m.id == agent.streamMessageId);
    if (idx >= 0 && agent.messages[idx] is AssistantMessage) {
      agent.messages[idx] = (agent.messages[idx] as AssistantMessage).copyWith(
        isStreaming: false,
      );
    }

    agent.streamText = '';
    agent.streamMessageId = null;
    _notify();
  }

  /// Update a permission request message status.
  void updatePermissionStatus(String agentId, String requestId, PermissionStatus status) {
    final agent = state.agents[agentId];
    if (agent == null) return;

    final idx = agent.messages.indexWhere(
      (m) => m is PermissionRequestMessage && m.requestId == requestId,
    );
    if (idx >= 0) {
      agent.messages[idx] =
          (agent.messages[idx] as PermissionRequestMessage).copyWith(status: status);
      _notify();
    }
  }

  void updateLastScreenshot(String agentId, String image) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.lastScreenshot = image;
    _notify();
  }

  void incrementComputerIteration(String agentId) {
    final agent = state.agents[agentId];
    if (agent == null) return;
    agent.computerIteration++;
    _notify();
  }

  /// Force state rebuild.
  void _notify() {
    state = state.copyWith(agents: Map.from(state.agents));
  }
}

final agentProvider =
    StateNotifierProvider<AgentNotifier, AgentState>((ref) {
  return AgentNotifier();
});
