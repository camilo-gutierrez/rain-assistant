import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/models/conversation.dart';

void main() {
  group('ConversationMeta', () {
    test('fromJson parses all fields correctly', () {
      final json = {
        'id': 'conv-001',
        'createdAt': 1700000000000,
        'updatedAt': 1700001000000,
        'label': 'Fix login bug',
        'cwd': '/home/user/project',
        'messageCount': 42,
        'preview': 'Let me fix the authentication...',
        'totalCost': 0.0523,
      };
      final meta = ConversationMeta.fromJson(json);
      expect(meta.id, 'conv-001');
      expect(meta.createdAt, 1700000000000);
      expect(meta.updatedAt, 1700001000000);
      expect(meta.label, 'Fix login bug');
      expect(meta.cwd, '/home/user/project');
      expect(meta.messageCount, 42);
      expect(meta.preview, 'Let me fix the authentication...');
      expect(meta.totalCost, closeTo(0.0523, 0.0001));
    });

    test('fromJson uses defaults for missing fields', () {
      final meta = ConversationMeta.fromJson({});
      expect(meta.id, '');
      expect(meta.createdAt, 0);
      expect(meta.updatedAt, 0);
      expect(meta.label, '');
      expect(meta.cwd, '');
      expect(meta.messageCount, 0);
      expect(meta.preview, '');
      expect(meta.totalCost, 0.0);
    });

    test('totalCost converts int to double', () {
      final meta = ConversationMeta.fromJson({'totalCost': 5});
      expect(meta.totalCost, 5.0);
      expect(meta.totalCost, isA<double>());
    });

    test('handles zero cost', () {
      final meta = ConversationMeta.fromJson({'totalCost': 0});
      expect(meta.totalCost, 0.0);
    });

    test('preserves unicode in label and preview', () {
      final json = {
        'label': 'Correcci\u00f3n de errores \u{1F41B}',
        'preview': '\u00bfC\u00f3mo puedo ayudarte?',
      };
      final meta = ConversationMeta.fromJson(json);
      expect(meta.label, contains('\u00f3'));
      expect(meta.preview, startsWith('\u00bf'));
    });
  });
}
