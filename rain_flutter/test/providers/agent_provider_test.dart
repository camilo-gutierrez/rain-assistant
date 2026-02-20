import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/providers/agent_provider.dart';
import 'package:rain_flutter/models/agent.dart';
import 'package:rain_flutter/models/message.dart';

void main() {
  group('AgentState', () {
    test('default constructor has empty agents and no active agent', () {
      const state = AgentState();
      expect(state.agents, isEmpty);
      expect(state.activeAgentId, '');
      expect(state.activeAgent, isNull);
    });

    test('activeAgent returns the correct agent', () {
      final agent = Agent(id: 'a1', label: 'Test');
      final state = AgentState(
        agents: {'a1': agent},
        activeAgentId: 'a1',
      );
      expect(state.activeAgent, isNotNull);
      expect(state.activeAgent!.id, 'a1');
      expect(state.activeAgent!.label, 'Test');
    });

    test('activeAgent returns null for non-existent id', () {
      final state = AgentState(
        agents: {'a1': Agent(id: 'a1')},
        activeAgentId: 'nonexistent',
      );
      expect(state.activeAgent, isNull);
    });

    test('copyWith creates new state with updated agents', () {
      const original = AgentState();
      final newAgents = {'a1': Agent(id: 'a1')};
      final updated = original.copyWith(agents: newAgents);
      expect(updated.agents.length, 1);
      expect(original.agents, isEmpty);
    });

    test('copyWith creates new state with updated activeAgentId', () {
      const original = AgentState(activeAgentId: 'old');
      final updated = original.copyWith(activeAgentId: 'new');
      expect(updated.activeAgentId, 'new');
      expect(original.activeAgentId, 'old');
    });
  });

  group('AgentNotifier — creation', () {
    late AgentNotifier notifier;

    setUp(() {
      notifier = AgentNotifier();
    });

    test('initial state is empty', () {
      expect(notifier.state.agents, isEmpty);
      expect(notifier.state.activeAgentId, '');
    });

    test('createAgent adds agent and sets it as active', () {
      final id = notifier.createAgent(label: 'First Agent');
      expect(notifier.state.agents.length, 1);
      expect(notifier.state.activeAgentId, id);
      expect(notifier.state.agents[id]!.label, 'First Agent');
    });

    test('createAgent generates unique ids', () {
      final id1 = notifier.createAgent(label: 'A');
      final id2 = notifier.createAgent(label: 'B');
      expect(id1, isNot(id2));
    });

    test('createAgent ids start with "agent_"', () {
      final id = notifier.createAgent();
      expect(id, startsWith('agent_'));
    });

    test('createAgent with no label auto-generates label', () {
      notifier.createAgent(); // Agent 1
      notifier.createAgent(); // Agent 2
      // Second agent should have label "Agent 2"
      final agents = notifier.state.agents.values.toList();
      expect(agents.last.label, 'Agent 2');
    });

    test('createAgent sets new agent as active (replaces previous)', () {
      final id1 = notifier.createAgent(label: 'First');
      expect(notifier.state.activeAgentId, id1);

      final id2 = notifier.createAgent(label: 'Second');
      expect(notifier.state.activeAgentId, id2);
    });

    test('multiple agents coexist in the map', () {
      notifier.createAgent(label: 'A');
      notifier.createAgent(label: 'B');
      notifier.createAgent(label: 'C');
      expect(notifier.state.agents.length, 3);
    });
  });

  group('AgentNotifier — ensureDefaultAgent', () {
    late AgentNotifier notifier;

    setUp(() {
      notifier = AgentNotifier();
    });

    test('creates default agent when empty', () {
      final id = notifier.ensureDefaultAgent();
      expect(notifier.state.agents.length, 1);
      expect(notifier.state.agents[id]!.label, 'Rain');
      expect(notifier.state.activeAgentId, id);
    });

    test('returns existing active agent id when not empty', () {
      final originalId = notifier.createAgent(label: 'Existing');
      final returnedId = notifier.ensureDefaultAgent();
      expect(returnedId, originalId);
      expect(notifier.state.agents.length, 1); // no new agent created
    });
  });

  group('AgentNotifier — setActiveAgent', () {
    late AgentNotifier notifier;

    setUp(() {
      notifier = AgentNotifier();
    });

    test('switches active agent', () {
      final id1 = notifier.createAgent(label: 'First');
      final id2 = notifier.createAgent(label: 'Second');
      expect(notifier.state.activeAgentId, id2); // newest is active

      notifier.setActiveAgent(id1);
      expect(notifier.state.activeAgentId, id1);
    });

    test('resets unread count when activating agent', () {
      final id1 = notifier.createAgent(label: 'First');
      notifier.createAgent(label: 'Second'); // switches active to second

      // Simulate unread on first agent
      notifier.state.agents[id1]!.unread = 5;
      notifier.setActiveAgent(id1);
      expect(notifier.state.agents[id1]!.unread, 0);
    });

    test('does nothing for non-existent agent id', () {
      final id1 = notifier.createAgent(label: 'Only');
      notifier.setActiveAgent('nonexistent');
      expect(notifier.state.activeAgentId, id1); // unchanged
    });
  });

  group('AgentNotifier — removeAgent', () {
    late AgentNotifier notifier;

    setUp(() {
      notifier = AgentNotifier();
    });

    test('removes the specified agent', () {
      final id1 = notifier.createAgent(label: 'First');
      notifier.createAgent(label: 'Second');

      notifier.removeAgent(id1);
      expect(notifier.state.agents.length, 1);
      expect(notifier.state.agents.containsKey(id1), false);
    });

    test('switches active to remaining agent when active is removed', () {
      final id1 = notifier.createAgent(label: 'First');
      final id2 = notifier.createAgent(label: 'Second');
      expect(notifier.state.activeAgentId, id2);

      notifier.removeAgent(id2);
      expect(notifier.state.activeAgentId, id1);
    });

    test('active becomes empty string when last agent is removed', () {
      final id = notifier.createAgent(label: 'Only');
      notifier.removeAgent(id);
      expect(notifier.state.agents, isEmpty);
      expect(notifier.state.activeAgentId, '');
    });

    test('does not affect active if non-active agent is removed', () {
      notifier.createAgent(label: 'First');
      final id2 = notifier.createAgent(label: 'Second');
      final id3 = notifier.createAgent(label: 'Third');
      expect(notifier.state.activeAgentId, id3);

      notifier.removeAgent(id2);
      expect(notifier.state.activeAgentId, id3); // still active
      expect(notifier.state.agents.length, 2);
    });
  });

  group('AgentNotifier — agent property setters', () {
    late AgentNotifier notifier;
    late String agentId;

    setUp(() {
      notifier = AgentNotifier();
      agentId = notifier.createAgent(label: 'Test');
    });

    test('setAgentCwd updates working directory', () {
      notifier.setAgentCwd(agentId, '/home/user/project');
      expect(notifier.state.agents[agentId]!.cwd, '/home/user/project');
    });

    test('setAgentCwd does nothing for unknown agent', () {
      notifier.setAgentCwd('unknown', '/tmp');
      // No error thrown, agent unchanged
      expect(notifier.state.agents[agentId]!.cwd, isNull);
    });

    test('setAgentStatus updates status', () {
      notifier.setAgentStatus(agentId, AgentStatus.working);
      expect(notifier.state.agents[agentId]!.status, AgentStatus.working);

      notifier.setAgentStatus(agentId, AgentStatus.error);
      expect(notifier.state.agents[agentId]!.status, AgentStatus.error);

      notifier.setAgentStatus(agentId, AgentStatus.done);
      expect(notifier.state.agents[agentId]!.status, AgentStatus.done);
    });

    test('setProcessing updates isProcessing flag', () {
      notifier.setProcessing(agentId, true);
      expect(notifier.state.agents[agentId]!.isProcessing, true);

      notifier.setProcessing(agentId, false);
      expect(notifier.state.agents[agentId]!.isProcessing, false);
    });

    test('setInterruptPending updates interrupt flag', () {
      notifier.setInterruptPending(agentId, true);
      expect(notifier.state.agents[agentId]!.interruptPending, true);
    });

    test('setAgentSessionId updates session id', () {
      notifier.setAgentSessionId(agentId, 'session-xyz');
      expect(notifier.state.agents[agentId]!.sessionId, 'session-xyz');
    });

    test('setHistoryLoaded updates history loaded flag', () {
      notifier.setHistoryLoaded(agentId, true);
      expect(notifier.state.agents[agentId]!.historyLoaded, true);
    });

    test('setAgentMode switches mode', () {
      notifier.setAgentMode(agentId, AgentMode.computerUse);
      expect(notifier.state.agents[agentId]!.mode, AgentMode.computerUse);

      notifier.setAgentMode(agentId, AgentMode.coding);
      expect(notifier.state.agents[agentId]!.mode, AgentMode.coding);
    });

    test('setDisplayInfo updates display info', () {
      final info = DisplayInfo.fromJson({
        'screen_width': 1920,
        'screen_height': 1080,
        'scaled_width': 1280,
        'scaled_height': 720,
        'scale_factor': 1.5,
      });
      notifier.setDisplayInfo(agentId, info);
      expect(notifier.state.agents[agentId]!.displayInfo, isNotNull);
      expect(notifier.state.agents[agentId]!.displayInfo!.screenWidth, 1920);
    });
  });

  group('AgentNotifier — message management', () {
    late AgentNotifier notifier;
    late String agentId;

    setUp(() {
      notifier = AgentNotifier();
      agentId = notifier.createAgent(label: 'Test');
    });

    test('appendMessage adds message to agent', () {
      final msg = UserMessage.create('Hello');
      notifier.appendMessage(agentId, msg);
      expect(notifier.state.agents[agentId]!.messages.length, 1);
      expect(
          (notifier.state.agents[agentId]!.messages[0] as UserMessage).text,
          'Hello');
    });

    test('appendMessage adds multiple messages in order', () {
      notifier.appendMessage(agentId, UserMessage.create('First'));
      notifier.appendMessage(agentId, UserMessage.create('Second'));
      notifier.appendMessage(agentId, UserMessage.create('Third'));
      final messages = notifier.state.agents[agentId]!.messages;
      expect(messages.length, 3);
      expect((messages[0] as UserMessage).text, 'First');
      expect((messages[1] as UserMessage).text, 'Second');
      expect((messages[2] as UserMessage).text, 'Third');
    });

    test('appendMessage does nothing for unknown agent', () {
      notifier.appendMessage('unknown', UserMessage.create('Lost'));
      expect(notifier.state.agents[agentId]!.messages, isEmpty);
    });

    test('setMessages replaces all messages', () {
      notifier.appendMessage(agentId, UserMessage.create('Old'));
      final newMessages = [
        UserMessage.create('New 1'),
        UserMessage.create('New 2'),
      ];
      notifier.setMessages(agentId, newMessages);
      expect(notifier.state.agents[agentId]!.messages.length, 2);
      expect(
          (notifier.state.agents[agentId]!.messages[0] as UserMessage).text,
          'New 1');
    });

    test('incrementUnread increments for non-active agent', () {
      final id2 = notifier.createAgent(label: 'Other');
      // id2 is now active; agentId is inactive
      notifier.incrementUnread(agentId);
      notifier.incrementUnread(agentId);
      expect(notifier.state.agents[agentId]!.unread, 2);
      // Active agent should not have unread incremented
      notifier.incrementUnread(id2);
      expect(notifier.state.agents[id2]!.unread, 0);
    });

    test('can add different message types to same agent', () {
      notifier.appendMessage(agentId, UserMessage.create('Question'));
      notifier.appendMessage(
          agentId,
          AssistantMessage(
            id: 'a1',
            text: 'Answer',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ));
      notifier.appendMessage(agentId, SystemMessage.create('System note'));
      notifier.appendMessage(
          agentId,
          ToolUseMessage(
            id: 'tu1',
            tool: 'bash',
            input: {'cmd': 'ls'},
            toolUseId: 'tu-001',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ));

      final messages = notifier.state.agents[agentId]!.messages;
      expect(messages.length, 4);
      expect(messages[0], isA<UserMessage>());
      expect(messages[1], isA<AssistantMessage>());
      expect(messages[2], isA<SystemMessage>());
      expect(messages[3], isA<ToolUseMessage>());
    });
  });

  group('AgentNotifier — streaming', () {
    late AgentNotifier notifier;
    late String agentId;

    setUp(() {
      notifier = AgentNotifier();
      agentId = notifier.createAgent(label: 'Test');
    });

    test('updateStreamingMessage creates new message on first chunk', () {
      notifier.updateStreamingMessage(agentId, 'Hello ');
      final agent = notifier.state.agents[agentId]!;
      expect(agent.messages.length, 1);
      expect(agent.messages[0], isA<AssistantMessage>());
      expect((agent.messages[0] as AssistantMessage).text, 'Hello ');
      expect((agent.messages[0] as AssistantMessage).isStreaming, true);
      expect(agent.streamMessageId, isNotNull);
      expect(agent.streamText, 'Hello ');
    });

    test('updateStreamingMessage accumulates text across chunks', () {
      notifier.updateStreamingMessage(agentId, 'Hello ');
      notifier.updateStreamingMessage(agentId, 'World');
      notifier.updateStreamingMessage(agentId, '!');

      final agent = notifier.state.agents[agentId]!;
      expect(agent.messages.length, 1); // still one message
      expect(agent.streamText, 'Hello World!');
      expect((agent.messages[0] as AssistantMessage).text, 'Hello World!');
    });

    test('finalizeStreaming marks message as not streaming', () {
      notifier.updateStreamingMessage(agentId, 'Complete text');
      notifier.finalizeStreaming(agentId);

      final agent = notifier.state.agents[agentId]!;
      expect(agent.messages.length, 1);
      expect((agent.messages[0] as AssistantMessage).isStreaming, false);
      expect((agent.messages[0] as AssistantMessage).text, 'Complete text');
      expect(agent.streamText, '');
      expect(agent.streamMessageId, isNull);
    });

    test('finalizeStreaming does nothing if no streaming is active', () {
      notifier.finalizeStreaming(agentId);
      final agent = notifier.state.agents[agentId]!;
      expect(agent.messages, isEmpty);
    });

    test('streaming after finalize starts a new message', () {
      notifier.updateStreamingMessage(agentId, 'First response');
      notifier.finalizeStreaming(agentId);
      notifier.updateStreamingMessage(agentId, 'Second response');

      final agent = notifier.state.agents[agentId]!;
      expect(agent.messages.length, 2);
      expect((agent.messages[0] as AssistantMessage).isStreaming, false);
      expect((agent.messages[1] as AssistantMessage).isStreaming, true);
    });
  });

  group('AgentNotifier — permission management', () {
    late AgentNotifier notifier;
    late String agentId;

    setUp(() {
      notifier = AgentNotifier();
      agentId = notifier.createAgent(label: 'Test');
    });

    test('updatePermissionStatus changes pending to approved', () {
      final permMsg = PermissionRequestMessage(
        id: 'p1',
        requestId: 'req-001',
        tool: 'bash',
        input: {'cmd': 'rm -rf /tmp'},
        level: PermissionLevel.red,
        reason: 'Dangerous',
        status: PermissionStatus.pending,
        timestamp: DateTime.now().millisecondsSinceEpoch,
      );
      notifier.appendMessage(agentId, permMsg);
      notifier.updatePermissionStatus(
          agentId, 'req-001', PermissionStatus.approved);

      final updated = notifier.state.agents[agentId]!.messages[0]
          as PermissionRequestMessage;
      expect(updated.status, PermissionStatus.approved);
    });

    test('updatePermissionStatus changes pending to denied', () {
      final permMsg = PermissionRequestMessage(
        id: 'p2',
        requestId: 'req-002',
        tool: 'write_file',
        input: {},
        level: PermissionLevel.yellow,
        reason: 'Write',
        status: PermissionStatus.pending,
        timestamp: DateTime.now().millisecondsSinceEpoch,
      );
      notifier.appendMessage(agentId, permMsg);
      notifier.updatePermissionStatus(
          agentId, 'req-002', PermissionStatus.denied);

      final updated = notifier.state.agents[agentId]!.messages[0]
          as PermissionRequestMessage;
      expect(updated.status, PermissionStatus.denied);
    });

    test('updatePermissionStatus ignores non-matching requestId', () {
      final permMsg = PermissionRequestMessage(
        id: 'p3',
        requestId: 'req-003',
        tool: 'bash',
        input: {},
        level: PermissionLevel.yellow,
        reason: 'Test',
        status: PermissionStatus.pending,
        timestamp: DateTime.now().millisecondsSinceEpoch,
      );
      notifier.appendMessage(agentId, permMsg);
      notifier.updatePermissionStatus(
          agentId, 'wrong-id', PermissionStatus.approved);

      final unchanged = notifier.state.agents[agentId]!.messages[0]
          as PermissionRequestMessage;
      expect(unchanged.status, PermissionStatus.pending);
    });
  });

  group('AgentNotifier — computer use', () {
    late AgentNotifier notifier;
    late String agentId;

    setUp(() {
      notifier = AgentNotifier();
      agentId = notifier.createAgent(label: 'Test');
    });

    test('updateLastScreenshot stores screenshot data', () {
      notifier.updateLastScreenshot(agentId, 'base64screenshot...');
      expect(notifier.state.agents[agentId]!.lastScreenshot,
          'base64screenshot...');
    });

    test('incrementComputerIteration increments counter', () {
      expect(notifier.state.agents[agentId]!.computerIteration, 0);
      notifier.incrementComputerIteration(agentId);
      expect(notifier.state.agents[agentId]!.computerIteration, 1);
      notifier.incrementComputerIteration(agentId);
      expect(notifier.state.agents[agentId]!.computerIteration, 2);
    });
  });

  group('AgentNotifier — state immutability', () {
    late AgentNotifier notifier;

    setUp(() {
      notifier = AgentNotifier();
    });

    test('state reference changes after mutation methods', () {
      final stateBefore = notifier.state;
      notifier.createAgent(label: 'New');
      final stateAfter = notifier.state;
      expect(identical(stateBefore, stateAfter), false);
    });

    test('agents map reference changes after property update', () {
      final id = notifier.createAgent(label: 'Test');
      final agentsBefore = notifier.state.agents;
      notifier.setAgentStatus(id, AgentStatus.working);
      final agentsAfter = notifier.state.agents;
      // The _notify() method creates a new Map via Map.from
      expect(identical(agentsBefore, agentsAfter), false);
    });
  });
}
