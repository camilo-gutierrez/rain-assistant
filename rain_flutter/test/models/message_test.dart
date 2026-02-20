import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/models/message.dart';

void main() {
  group('UserMessage', () {
    test('create() generates a valid message with unique id and timestamp', () {
      final msg = UserMessage.create('Hello world');
      expect(msg.text, 'Hello world');
      expect(msg.type, 'user');
      expect(msg.id, isNotEmpty);
      expect(msg.timestamp, greaterThan(0));
      expect(msg.animate, true); // default from create()
    });

    test('create() generates unique ids for different messages', () {
      final msg1 = UserMessage.create('First');
      final msg2 = UserMessage.create('Second');
      expect(msg1.id, isNot(msg2.id));
    });

    test('toJson produces correct map', () {
      final msg = UserMessage(
        id: 'test-id',
        text: 'Test text',
        timestamp: 1000,
        animate: false,
      );
      final json = msg.toJson();
      expect(json['id'], 'test-id');
      expect(json['type'], 'user');
      expect(json['text'], 'Test text');
      expect(json['timestamp'], 1000);
      expect(json['animate'], false);
    });

    test('fromJson parses all fields correctly', () {
      final json = {
        'id': 'u1',
        'type': 'user',
        'text': 'Hello from JSON',
        'timestamp': 5000,
        'animate': true,
      };
      final msg = UserMessage.fromJson(json);
      expect(msg.id, 'u1');
      expect(msg.text, 'Hello from JSON');
      expect(msg.timestamp, 5000);
      expect(msg.animate, true);
      expect(msg.type, 'user');
    });

    test('fromJson handles missing optional fields with defaults', () {
      final msg = UserMessage.fromJson({});
      expect(msg.id, isNotEmpty); // auto-generated UUID
      expect(msg.text, '');
      expect(msg.animate, false);
    });

    test('roundtrip: toJson -> fromJson preserves data', () {
      final original = UserMessage.create('Roundtrip test');
      final json = original.toJson();
      final restored = UserMessage.fromJson(json);
      expect(restored.id, original.id);
      expect(restored.text, original.text);
      expect(restored.timestamp, original.timestamp);
    });

    test('handles empty content', () {
      final msg = UserMessage.create('');
      expect(msg.text, '');
    });

    test('handles special characters and unicode', () {
      const text = 'Hello <b>world</b> & "quotes" \u00e1\u00e9\u00ed\u00f3\u00fa \u{1F600}';
      final msg = UserMessage.create(text);
      expect(msg.text, text);
      final restored = UserMessage.fromJson(msg.toJson());
      expect(restored.text, text);
    });

    test('handles very long content', () {
      final longText = 'A' * 100000;
      final msg = UserMessage.create(longText);
      expect(msg.text.length, 100000);
    });
  });

  group('AssistantMessage', () {
    test('fromJson parses correctly with streaming flag', () {
      final json = {
        'id': 'a1',
        'type': 'assistant',
        'text': 'AI response',
        'isStreaming': true,
        'timestamp': 2000,
      };
      final msg = AssistantMessage.fromJson(json);
      expect(msg.text, 'AI response');
      expect(msg.isStreaming, true);
      expect(msg.type, 'assistant');
    });

    test('isStreaming defaults to false', () {
      final msg = AssistantMessage.fromJson({'type': 'assistant'});
      expect(msg.isStreaming, false);
    });

    test('copyWith updates text only', () {
      final msg = AssistantMessage(
        id: 'a1',
        text: 'Original',
        isStreaming: true,
        timestamp: 1000,
      );
      final updated = msg.copyWith(text: 'Updated');
      expect(updated.text, 'Updated');
      expect(updated.isStreaming, true); // unchanged
      expect(updated.id, 'a1'); // unchanged
      expect(updated.timestamp, 1000); // unchanged
    });

    test('copyWith updates isStreaming only', () {
      final msg = AssistantMessage(
        id: 'a1',
        text: 'Hello',
        isStreaming: true,
        timestamp: 1000,
      );
      final updated = msg.copyWith(isStreaming: false);
      expect(updated.text, 'Hello'); // unchanged
      expect(updated.isStreaming, false);
    });

    test('copyWith with no arguments returns equivalent message', () {
      final msg = AssistantMessage(
        id: 'a1',
        text: 'Hello',
        isStreaming: false,
        timestamp: 1000,
        animate: true,
      );
      final copy = msg.copyWith();
      expect(copy.id, msg.id);
      expect(copy.text, msg.text);
      expect(copy.isStreaming, msg.isStreaming);
      expect(copy.timestamp, msg.timestamp);
    });

    test('toJson includes isStreaming', () {
      final msg = AssistantMessage(
        id: 'a1',
        text: 'Test',
        isStreaming: true,
        timestamp: 1000,
      );
      final json = msg.toJson();
      expect(json['isStreaming'], true);
      expect(json['type'], 'assistant');
    });

    test('roundtrip preserves all fields', () {
      final original = AssistantMessage(
        id: 'a1',
        text: 'Roundtrip',
        isStreaming: true,
        timestamp: 3000,
        animate: true,
      );
      final restored = AssistantMessage.fromJson(original.toJson());
      expect(restored.id, original.id);
      expect(restored.text, original.text);
      expect(restored.isStreaming, original.isStreaming);
      expect(restored.timestamp, original.timestamp);
    });
  });

  group('SystemMessage', () {
    test('create() produces valid system message', () {
      final msg = SystemMessage.create('System info');
      expect(msg.text, 'System info');
      expect(msg.type, 'system');
      expect(msg.id, isNotEmpty);
    });

    test('fromJson parses correctly', () {
      final msg = SystemMessage.fromJson({
        'id': 's1',
        'text': 'Error occurred',
        'timestamp': 9000,
      });
      expect(msg.id, 's1');
      expect(msg.text, 'Error occurred');
      expect(msg.type, 'system');
    });

    test('roundtrip preserves data', () {
      final original = SystemMessage.create('Roundtrip system');
      final restored = SystemMessage.fromJson(original.toJson());
      expect(restored.text, original.text);
      expect(restored.id, original.id);
    });
  });

  group('ToolUseMessage', () {
    test('fromJson parses tool name, input, and toolUseId', () {
      final json = {
        'id': 't1',
        'type': 'tool_use',
        'tool': 'read_file',
        'input': {'path': '/tmp/test.txt'},
        'toolUseId': 'tu-123',
        'timestamp': 4000,
      };
      final msg = ToolUseMessage.fromJson(json);
      expect(msg.tool, 'read_file');
      expect(msg.input['path'], '/tmp/test.txt');
      expect(msg.toolUseId, 'tu-123');
      expect(msg.type, 'tool_use');
    });

    test('fromJson handles empty input map', () {
      final msg = ToolUseMessage.fromJson({'type': 'tool_use'});
      expect(msg.tool, '');
      expect(msg.input, isEmpty);
      expect(msg.toolUseId, '');
    });

    test('toJson produces correct map with nested input', () {
      final msg = ToolUseMessage(
        id: 't1',
        tool: 'bash',
        input: {'command': 'ls -la', 'cwd': '/home'},
        toolUseId: 'tu-456',
        timestamp: 5000,
      );
      final json = msg.toJson();
      expect(json['tool'], 'bash');
      expect(json['input']['command'], 'ls -la');
      expect(json['input']['cwd'], '/home');
      expect(json['toolUseId'], 'tu-456');
    });

    test('roundtrip preserves nested input data', () {
      final original = ToolUseMessage(
        id: 't1',
        tool: 'write_file',
        input: {
          'path': '/tmp/out.txt',
          'content': 'line1\nline2',
          'nested': {'key': 'value'},
        },
        toolUseId: 'tu-789',
        timestamp: 6000,
      );
      final restored = ToolUseMessage.fromJson(original.toJson());
      expect(restored.tool, original.tool);
      expect(restored.input['path'], '/tmp/out.txt');
      expect(restored.input['nested'], isA<Map>());
    });
  });

  group('ToolResultMessage', () {
    test('fromJson parses content and isError', () {
      final json = {
        'id': 'tr1',
        'type': 'tool_result',
        'content': 'file contents here',
        'isError': false,
        'toolUseId': 'tu-123',
        'timestamp': 7000,
      };
      final msg = ToolResultMessage.fromJson(json);
      expect(msg.content, 'file contents here');
      expect(msg.isError, false);
      expect(msg.toolUseId, 'tu-123');
      expect(msg.type, 'tool_result');
    });

    test('isError defaults to false', () {
      final msg = ToolResultMessage.fromJson({});
      expect(msg.isError, false);
    });

    test('error result has isError true', () {
      final msg = ToolResultMessage(
        id: 'tr2',
        content: 'Permission denied',
        isError: true,
        toolUseId: 'tu-err',
        timestamp: 8000,
      );
      expect(msg.isError, true);
      final json = msg.toJson();
      expect(json['isError'], true);
    });

    test('roundtrip preserves error state', () {
      final original = ToolResultMessage(
        id: 'tr3',
        content: 'Error details',
        isError: true,
        toolUseId: 'tu-999',
        timestamp: 9000,
      );
      final restored = ToolResultMessage.fromJson(original.toJson());
      expect(restored.isError, true);
      expect(restored.content, 'Error details');
    });
  });

  group('PermissionRequestMessage', () {
    test('fromJson parses all permission fields', () {
      final json = {
        'id': 'p1',
        'type': 'permission_request',
        'requestId': 'req-001',
        'tool': 'bash',
        'input': {'command': 'rm -rf /tmp/test'},
        'level': 'red',
        'reason': 'Dangerous operation',
        'status': 'pending',
        'timestamp': 10000,
      };
      final msg = PermissionRequestMessage.fromJson(json);
      expect(msg.requestId, 'req-001');
      expect(msg.tool, 'bash');
      expect(msg.level, PermissionLevel.red);
      expect(msg.reason, 'Dangerous operation');
      expect(msg.status, PermissionStatus.pending);
      expect(msg.type, 'permission_request');
    });

    test('level defaults to yellow for unknown values', () {
      final msg = PermissionRequestMessage.fromJson({
        'level': 'unknown_level',
      });
      expect(msg.level, PermissionLevel.yellow);
    });

    test('status defaults to pending for unknown values', () {
      final msg = PermissionRequestMessage.fromJson({
        'status': 'bogus_status',
      });
      expect(msg.status, PermissionStatus.pending);
    });

    test('copyWith updates status only', () {
      final msg = PermissionRequestMessage(
        id: 'p2',
        requestId: 'req-002',
        tool: 'write_file',
        input: {'path': '/etc/hosts'},
        level: PermissionLevel.red,
        reason: 'System file',
        status: PermissionStatus.pending,
        timestamp: 11000,
      );
      final approved = msg.copyWith(status: PermissionStatus.approved);
      expect(approved.status, PermissionStatus.approved);
      expect(approved.requestId, 'req-002'); // unchanged
      expect(approved.tool, 'write_file'); // unchanged
      expect(approved.level, PermissionLevel.red); // unchanged
    });

    test('all PermissionLevel values are parseable', () {
      for (final level in PermissionLevel.values) {
        final msg = PermissionRequestMessage.fromJson({
          'level': level.name,
        });
        expect(msg.level, level);
      }
    });

    test('all PermissionStatus values are parseable', () {
      for (final status in PermissionStatus.values) {
        final msg = PermissionRequestMessage.fromJson({
          'status': status.name,
        });
        expect(msg.status, status);
      }
    });

    test('toJson serializes enums as strings', () {
      final msg = PermissionRequestMessage(
        id: 'p3',
        requestId: 'req-003',
        tool: 'test',
        input: {},
        level: PermissionLevel.computer,
        reason: 'Test',
        status: PermissionStatus.denied,
        timestamp: 12000,
      );
      final json = msg.toJson();
      expect(json['level'], 'computer');
      expect(json['status'], 'denied');
    });

    test('roundtrip preserves all permission data', () {
      final original = PermissionRequestMessage(
        id: 'p4',
        requestId: 'req-004',
        tool: 'bash',
        input: {'cmd': 'echo hi'},
        level: PermissionLevel.yellow,
        reason: 'Safe command',
        status: PermissionStatus.approved,
        timestamp: 13000,
        animate: true,
      );
      final restored = PermissionRequestMessage.fromJson(original.toJson());
      expect(restored.requestId, original.requestId);
      expect(restored.level, original.level);
      expect(restored.status, original.status);
      expect(restored.reason, original.reason);
    });
  });

  group('ComputerScreenshotMessage', () {
    test('fromJson parses image, action, description, iteration', () {
      final json = {
        'id': 'cs1',
        'type': 'computer_screenshot',
        'image': 'base64data...',
        'action': 'screenshot',
        'description': 'Desktop screenshot',
        'iteration': 3,
        'timestamp': 14000,
      };
      final msg = ComputerScreenshotMessage.fromJson(json);
      expect(msg.image, 'base64data...');
      expect(msg.action, 'screenshot');
      expect(msg.description, 'Desktop screenshot');
      expect(msg.iteration, 3);
      expect(msg.type, 'computer_screenshot');
    });

    test('defaults for missing fields', () {
      final msg = ComputerScreenshotMessage.fromJson({});
      expect(msg.image, '');
      expect(msg.action, '');
      expect(msg.description, '');
      expect(msg.iteration, 0);
    });

    test('roundtrip preserves all fields', () {
      final original = ComputerScreenshotMessage(
        id: 'cs2',
        image: 'abc123',
        action: 'click',
        description: 'Clicked button',
        iteration: 5,
        timestamp: 15000,
      );
      final restored = ComputerScreenshotMessage.fromJson(original.toJson());
      expect(restored.image, original.image);
      expect(restored.action, original.action);
      expect(restored.description, original.description);
      expect(restored.iteration, original.iteration);
    });
  });

  group('ComputerActionMessage', () {
    test('fromJson parses tool, action, input, description, iteration', () {
      final json = {
        'id': 'ca1',
        'type': 'computer_action',
        'tool': 'computer',
        'action': 'click',
        'input': {'x': 100, 'y': 200},
        'description': 'Click at coordinates',
        'iteration': 2,
        'timestamp': 16000,
      };
      final msg = ComputerActionMessage.fromJson(json);
      expect(msg.tool, 'computer');
      expect(msg.action, 'click');
      expect(msg.input['x'], 100);
      expect(msg.input['y'], 200);
      expect(msg.description, 'Click at coordinates');
      expect(msg.iteration, 2);
      expect(msg.type, 'computer_action');
    });

    test('defaults for missing fields', () {
      final msg = ComputerActionMessage.fromJson({});
      expect(msg.tool, '');
      expect(msg.action, '');
      expect(msg.input, isEmpty);
      expect(msg.description, '');
      expect(msg.iteration, 0);
    });

    test('roundtrip preserves nested input', () {
      final original = ComputerActionMessage(
        id: 'ca2',
        tool: 'computer',
        action: 'type',
        input: {'text': 'Hello World', 'delay': 50},
        description: 'Type text',
        iteration: 1,
        timestamp: 17000,
      );
      final restored = ComputerActionMessage.fromJson(original.toJson());
      expect(restored.input['text'], 'Hello World');
      expect(restored.input['delay'], 50);
    });
  });

  group('Message.fromJson (polymorphic dispatch)', () {
    test('dispatches to UserMessage for type "user"', () {
      final msg = Message.fromJson({
        'type': 'user',
        'text': 'Hello',
        'timestamp': 1000,
      });
      expect(msg, isA<UserMessage>());
      expect((msg as UserMessage).text, 'Hello');
    });

    test('dispatches to AssistantMessage for type "assistant"', () {
      final msg = Message.fromJson({
        'type': 'assistant',
        'text': 'Reply',
        'timestamp': 1000,
      });
      expect(msg, isA<AssistantMessage>());
    });

    test('dispatches to SystemMessage for type "system"', () {
      final msg = Message.fromJson({
        'type': 'system',
        'text': 'Info',
        'timestamp': 1000,
      });
      expect(msg, isA<SystemMessage>());
    });

    test('dispatches to ToolUseMessage for type "tool_use"', () {
      final msg = Message.fromJson({
        'type': 'tool_use',
        'tool': 'bash',
        'input': {},
        'toolUseId': 'tu-1',
        'timestamp': 1000,
      });
      expect(msg, isA<ToolUseMessage>());
    });

    test('dispatches to ToolResultMessage for type "tool_result"', () {
      final msg = Message.fromJson({
        'type': 'tool_result',
        'content': 'ok',
        'isError': false,
        'toolUseId': 'tu-1',
        'timestamp': 1000,
      });
      expect(msg, isA<ToolResultMessage>());
    });

    test('dispatches to PermissionRequestMessage for type "permission_request"',
        () {
      final msg = Message.fromJson({
        'type': 'permission_request',
        'requestId': 'r1',
        'tool': 'bash',
        'input': {},
        'level': 'yellow',
        'reason': 'test',
        'timestamp': 1000,
      });
      expect(msg, isA<PermissionRequestMessage>());
    });

    test('dispatches to ComputerScreenshotMessage for type "computer_screenshot"',
        () {
      final msg = Message.fromJson({
        'type': 'computer_screenshot',
        'image': '',
        'action': '',
        'description': '',
        'iteration': 0,
        'timestamp': 1000,
      });
      expect(msg, isA<ComputerScreenshotMessage>());
    });

    test('dispatches to ComputerActionMessage for type "computer_action"', () {
      final msg = Message.fromJson({
        'type': 'computer_action',
        'tool': 'computer',
        'action': 'click',
        'input': {},
        'description': '',
        'iteration': 0,
        'timestamp': 1000,
      });
      expect(msg, isA<ComputerActionMessage>());
    });

    test('returns SystemMessage for unknown type', () {
      final msg = Message.fromJson({
        'type': 'some_unknown_type',
        'timestamp': 1000,
      });
      expect(msg, isA<SystemMessage>());
      expect((msg as SystemMessage).text, contains('Unknown message type'));
      expect(msg.text, contains('some_unknown_type'));
    });

    test('returns SystemMessage for null type', () {
      final msg = Message.fromJson({'timestamp': 1000});
      expect(msg, isA<SystemMessage>());
    });
  });

  group('PermissionLevel enum', () {
    test('has exactly 3 values', () {
      expect(PermissionLevel.values.length, 3);
    });

    test('contains expected values', () {
      expect(PermissionLevel.values, contains(PermissionLevel.yellow));
      expect(PermissionLevel.values, contains(PermissionLevel.red));
      expect(PermissionLevel.values, contains(PermissionLevel.computer));
    });
  });

  group('PermissionStatus enum', () {
    test('has exactly 4 values', () {
      expect(PermissionStatus.values.length, 4);
    });

    test('contains expected values', () {
      expect(PermissionStatus.values, contains(PermissionStatus.pending));
      expect(PermissionStatus.values, contains(PermissionStatus.approved));
      expect(PermissionStatus.values, contains(PermissionStatus.denied));
      expect(PermissionStatus.values, contains(PermissionStatus.expired));
    });
  });
}
