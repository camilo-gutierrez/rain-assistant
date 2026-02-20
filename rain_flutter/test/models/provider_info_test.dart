import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/models/provider_info.dart';

void main() {
  group('AIProvider enum', () {
    test('has exactly 3 values', () {
      expect(AIProvider.values.length, 3);
    });

    test('contains claude, openai, gemini', () {
      expect(AIProvider.values, contains(AIProvider.claude));
      expect(AIProvider.values, contains(AIProvider.openai));
      expect(AIProvider.values, contains(AIProvider.gemini));
    });
  });

  group('providerModels', () {
    test('every AIProvider has a model list', () {
      for (final provider in AIProvider.values) {
        expect(providerModels.containsKey(provider), true,
            reason: '${provider.name} should have models');
        expect(providerModels[provider], isNotEmpty,
            reason: '${provider.name} should have at least one model');
      }
    });

    test('Claude models contain auto as first option', () {
      final claudeModels = providerModels[AIProvider.claude]!;
      expect(claudeModels.first.id, 'auto');
    });

    test('all models have non-empty id and name', () {
      for (final entry in providerModels.entries) {
        for (final model in entry.value) {
          expect(model.id, isNotEmpty,
              reason: 'Model id should not be empty for ${entry.key.name}');
          expect(model.name, isNotEmpty,
              reason: 'Model name should not be empty for ${model.id}');
        }
      }
    });

    test('model ids are unique within each provider', () {
      for (final entry in providerModels.entries) {
        final ids = entry.value.map((m) => m.id).toList();
        expect(ids.toSet().length, ids.length,
            reason:
                '${entry.key.name} has duplicate model ids');
      }
    });
  });

  group('providerInfo', () {
    test('every AIProvider has display info', () {
      for (final provider in AIProvider.values) {
        expect(providerInfo.containsKey(provider), true,
            reason: '${provider.name} should have display info');
      }
    });

    test('all display info has non-empty fields', () {
      for (final entry in providerInfo.entries) {
        expect(entry.value.name, isNotEmpty);
        expect(entry.value.keyPlaceholder, isNotEmpty);
        expect(entry.value.consoleUrl, isNotEmpty);
        expect(entry.value.consoleUrl, startsWith('https://'));
      }
    });
  });

  group('formatModelName', () {
    test('returns short name for known model', () {
      expect(formatModelName('claude-sonnet-4-5-20250929'), 'Sonnet 4.5');
      expect(formatModelName('claude-opus-4-6'), 'Opus 4.6');
    });

    test('matches prefix for versioned model names', () {
      // The function strips the date suffix from keys and checks prefix match
      expect(formatModelName('claude-sonnet-4-5-20250929'), 'Sonnet 4.5');
    });

    test('returns raw name for unknown short model', () {
      expect(formatModelName('gpt-4o'), 'gpt-4o');
    });

    test('truncates long unknown model names', () {
      final longName = 'a' * 30;
      final result = formatModelName(longName);
      expect(result.length, lessThanOrEqualTo(25)); // 22 + '...'
      expect(result, endsWith('...'));
    });

    test('does not truncate short unknown model names', () {
      expect(formatModelName('gpt-4o-mini'), 'gpt-4o-mini');
    });
  });

  group('ProviderModelInfo', () {
    test('stores id and name', () {
      const model = ProviderModelInfo('test-id', 'Test Name');
      expect(model.id, 'test-id');
      expect(model.name, 'Test Name');
    });
  });

  group('ProviderDisplay', () {
    test('stores all display fields', () {
      const display = ProviderDisplay(
        name: 'TestProvider',
        keyPlaceholder: 'tk-...',
        consoleUrl: 'https://example.com',
      );
      expect(display.name, 'TestProvider');
      expect(display.keyPlaceholder, 'tk-...');
      expect(display.consoleUrl, 'https://example.com');
    });
  });
}
