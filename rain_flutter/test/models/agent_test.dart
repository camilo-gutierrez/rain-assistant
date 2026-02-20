import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/models/agent.dart';
import 'package:rain_flutter/models/message.dart';

void main() {
  group('AgentStatus enum', () {
    test('has exactly 4 values', () {
      expect(AgentStatus.values.length, 4);
    });

    test('contains idle, working, done, error', () {
      expect(AgentStatus.values, contains(AgentStatus.idle));
      expect(AgentStatus.values, contains(AgentStatus.working));
      expect(AgentStatus.values, contains(AgentStatus.done));
      expect(AgentStatus.values, contains(AgentStatus.error));
    });
  });

  group('AgentMode enum', () {
    test('has exactly 2 values', () {
      expect(AgentMode.values.length, 2);
    });

    test('contains coding and computerUse', () {
      expect(AgentMode.values, contains(AgentMode.coding));
      expect(AgentMode.values, contains(AgentMode.computerUse));
    });
  });

  group('AgentPanel enum', () {
    test('has exactly 2 values', () {
      expect(AgentPanel.values.length, 2);
    });

    test('contains fileBrowser and chat', () {
      expect(AgentPanel.values, contains(AgentPanel.fileBrowser));
      expect(AgentPanel.values, contains(AgentPanel.chat));
    });
  });

  group('Agent', () {
    test('creation with required id only uses correct defaults', () {
      final agent = Agent(id: 'test-1');
      expect(agent.id, 'test-1');
      expect(agent.cwd, isNull);
      expect(agent.currentBrowsePath, '~');
      expect(agent.label, 'Agent');
      expect(agent.status, AgentStatus.idle);
      expect(agent.unread, 0);
      expect(agent.messages, isEmpty);
      expect(agent.scrollPos, 0);
      expect(agent.streamText, '');
      expect(agent.streamMessageId, isNull);
      expect(agent.isProcessing, false);
      expect(agent.interruptPending, false);
      expect(agent.historyLoaded, false);
      expect(agent.sessionId, isNull);
      expect(agent.activePanel, AgentPanel.chat);
      expect(agent.mode, AgentMode.coding);
      expect(agent.displayInfo, isNull);
      expect(agent.lastScreenshot, isNull);
      expect(agent.computerIteration, 0);
    });

    test('creation with all custom parameters', () {
      final messages = [UserMessage.create('Hello')];
      final agent = Agent(
        id: 'custom-1',
        cwd: '/home/user/project',
        currentBrowsePath: '/home/user',
        label: 'My Agent',
        status: AgentStatus.working,
        unread: 5,
        messages: messages,
        scrollPos: 100.5,
        streamText: 'partial...',
        streamMessageId: 'stream-1',
        isProcessing: true,
        interruptPending: true,
        historyLoaded: true,
        sessionId: 'session-abc',
        activePanel: AgentPanel.fileBrowser,
        mode: AgentMode.computerUse,
        lastScreenshot: 'base64...',
        computerIteration: 3,
      );
      expect(agent.id, 'custom-1');
      expect(agent.cwd, '/home/user/project');
      expect(agent.currentBrowsePath, '/home/user');
      expect(agent.label, 'My Agent');
      expect(agent.status, AgentStatus.working);
      expect(agent.unread, 5);
      expect(agent.messages.length, 1);
      expect(agent.scrollPos, 100.5);
      expect(agent.streamText, 'partial...');
      expect(agent.streamMessageId, 'stream-1');
      expect(agent.isProcessing, true);
      expect(agent.interruptPending, true);
      expect(agent.historyLoaded, true);
      expect(agent.sessionId, 'session-abc');
      expect(agent.activePanel, AgentPanel.fileBrowser);
      expect(agent.mode, AgentMode.computerUse);
      expect(agent.lastScreenshot, 'base64...');
      expect(agent.computerIteration, 3);
    });

    test('messages list is mutable', () {
      final agent = Agent(id: 'mut-1');
      expect(agent.messages, isEmpty);
      agent.messages.add(UserMessage.create('Test'));
      expect(agent.messages.length, 1);
    });

    test('null messages parameter creates empty list', () {
      final agent = Agent(id: 'null-msg', messages: null);
      expect(agent.messages, isA<List<Message>>());
      expect(agent.messages, isEmpty);
    });

    test('mutable fields can be updated directly', () {
      final agent = Agent(id: 'mut-2');

      agent.status = AgentStatus.error;
      expect(agent.status, AgentStatus.error);

      agent.unread = 10;
      expect(agent.unread, 10);

      agent.cwd = '/new/path';
      expect(agent.cwd, '/new/path');

      agent.isProcessing = true;
      expect(agent.isProcessing, true);

      agent.mode = AgentMode.computerUse;
      expect(agent.mode, AgentMode.computerUse);

      agent.computerIteration = 7;
      expect(agent.computerIteration, 7);
    });

    test('each agent has independent messages list', () {
      final agent1 = Agent(id: 'a1');
      final agent2 = Agent(id: 'a2');
      agent1.messages.add(UserMessage.create('Only in agent1'));
      expect(agent1.messages.length, 1);
      expect(agent2.messages, isEmpty);
    });
  });

  group('DisplayInfo', () {
    test('fromJson parses all fields correctly', () {
      final json = {
        'screen_width': 1920,
        'screen_height': 1080,
        'scaled_width': 1280,
        'scaled_height': 720,
        'scale_factor': 1.5,
      };
      final info = DisplayInfo.fromJson(json);
      expect(info.screenWidth, 1920);
      expect(info.screenHeight, 1080);
      expect(info.scaledWidth, 1280);
      expect(info.scaledHeight, 720);
      expect(info.scaleFactor, 1.5);
    });

    test('fromJson uses defaults for missing fields', () {
      final info = DisplayInfo.fromJson({});
      expect(info.screenWidth, 0);
      expect(info.screenHeight, 0);
      expect(info.scaledWidth, 0);
      expect(info.scaledHeight, 0);
      expect(info.scaleFactor, 1.0);
    });

    test('scaleFactor converts int to double', () {
      final info = DisplayInfo.fromJson({'scale_factor': 2});
      expect(info.scaleFactor, 2.0);
      expect(info.scaleFactor, isA<double>());
    });
  });
}
