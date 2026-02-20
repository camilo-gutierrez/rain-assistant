import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:rain_flutter/providers/settings_provider.dart';
import 'package:rain_flutter/models/provider_info.dart';

void main() {
  // SharedPreferences must be mocked before any notifier that calls _save().
  setUp(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    SharedPreferences.setMockInitialValues({});
  });

  group('SettingsState', () {
    test('default constructor has correct defaults', () {
      const state = SettingsState();
      expect(state.darkMode, true);
      expect(state.language, 'es');
      expect(state.aiProvider, AIProvider.claude);
      expect(state.aiModel, 'auto');
      expect(state.ttsEnabled, false);
      expect(state.ttsAutoPlay, false);
      expect(state.ttsVoice, 'es-MX-DaliaNeural');
    });

    test('copyWith creates new instance with updated darkMode', () {
      const original = SettingsState();
      final updated = original.copyWith(darkMode: false);
      expect(updated.darkMode, false);
      expect(updated.language, 'es'); // unchanged
      expect(updated.aiProvider, AIProvider.claude); // unchanged
    });

    test('copyWith creates new instance with updated language', () {
      const original = SettingsState();
      final updated = original.copyWith(language: 'en');
      expect(updated.language, 'en');
      expect(updated.darkMode, true); // unchanged
    });

    test('copyWith creates new instance with updated aiProvider', () {
      const original = SettingsState();
      final updated = original.copyWith(aiProvider: AIProvider.openai);
      expect(updated.aiProvider, AIProvider.openai);
      expect(updated.aiModel, 'auto'); // unchanged (copyWith doesn't auto-reset)
    });

    test('copyWith creates new instance with updated aiModel', () {
      const original = SettingsState();
      final updated = original.copyWith(aiModel: 'gpt-4o');
      expect(updated.aiModel, 'gpt-4o');
    });

    test('copyWith creates new instance with updated ttsEnabled', () {
      const original = SettingsState();
      final updated = original.copyWith(ttsEnabled: true);
      expect(updated.ttsEnabled, true);
      expect(updated.ttsAutoPlay, false); // unchanged
    });

    test('copyWith creates new instance with updated ttsAutoPlay', () {
      const original = SettingsState();
      final updated = original.copyWith(ttsAutoPlay: true);
      expect(updated.ttsAutoPlay, true);
    });

    test('copyWith creates new instance with updated ttsVoice', () {
      const original = SettingsState();
      final updated = original.copyWith(ttsVoice: 'en-US-JennyNeural');
      expect(updated.ttsVoice, 'en-US-JennyNeural');
    });

    test('copyWith with no arguments returns equivalent state', () {
      const original = SettingsState(
        darkMode: false,
        language: 'en',
        aiProvider: AIProvider.openai,
        aiModel: 'gpt-4o',
        ttsEnabled: true,
        ttsAutoPlay: true,
        ttsVoice: 'en-US-GuyNeural',
      );
      final copy = original.copyWith();
      expect(copy.darkMode, original.darkMode);
      expect(copy.language, original.language);
      expect(copy.aiProvider, original.aiProvider);
      expect(copy.aiModel, original.aiModel);
      expect(copy.ttsEnabled, original.ttsEnabled);
      expect(copy.ttsAutoPlay, original.ttsAutoPlay);
      expect(copy.ttsVoice, original.ttsVoice);
    });

    test('copyWith can update multiple fields at once', () {
      const original = SettingsState();
      final updated = original.copyWith(
        darkMode: false,
        language: 'en',
        ttsEnabled: true,
      );
      expect(updated.darkMode, false);
      expect(updated.language, 'en');
      expect(updated.ttsEnabled, true);
      expect(updated.aiProvider, AIProvider.claude); // unchanged
    });
  });

  group('SettingsNotifier', () {
    late SettingsNotifier notifier;

    setUp(() {
      notifier = SettingsNotifier();
    });

    test('initial state has correct defaults', () {
      expect(notifier.state.darkMode, true);
      expect(notifier.state.language, 'es');
      expect(notifier.state.aiProvider, AIProvider.claude);
      expect(notifier.state.aiModel, 'auto');
      expect(notifier.state.ttsEnabled, false);
    });

    test('setDarkMode toggles dark mode', () {
      notifier.setDarkMode(false);
      expect(notifier.state.darkMode, false);

      notifier.setDarkMode(true);
      expect(notifier.state.darkMode, true);
    });

    test('setLanguage switches language', () {
      notifier.setLanguage('en');
      expect(notifier.state.language, 'en');

      notifier.setLanguage('es');
      expect(notifier.state.language, 'es');
    });

    test('setAIProvider switches provider and resets model', () {
      notifier.setAIProvider(AIProvider.openai);
      expect(notifier.state.aiProvider, AIProvider.openai);
      // Model should be reset to first available model for the new provider
      final openaiModels = providerModels[AIProvider.openai]!;
      expect(notifier.state.aiModel, openaiModels.first.id);
    });

    test('setAIProvider to gemini resets model to first gemini model', () {
      notifier.setAIProvider(AIProvider.gemini);
      expect(notifier.state.aiProvider, AIProvider.gemini);
      final geminiModels = providerModels[AIProvider.gemini]!;
      expect(notifier.state.aiModel, geminiModels.first.id);
    });

    test('setAIProvider to claude resets model to auto', () {
      // First switch away from claude
      notifier.setAIProvider(AIProvider.openai);
      // Then switch back
      notifier.setAIProvider(AIProvider.claude);
      expect(notifier.state.aiProvider, AIProvider.claude);
      expect(notifier.state.aiModel, 'auto'); // First Claude model is 'auto'
    });

    test('setAIModel sets specific model', () {
      notifier.setAIModel('claude-opus-4-6');
      expect(notifier.state.aiModel, 'claude-opus-4-6');
    });

    test('setTtsEnabled toggles TTS', () {
      notifier.setTtsEnabled(true);
      expect(notifier.state.ttsEnabled, true);

      notifier.setTtsEnabled(false);
      expect(notifier.state.ttsEnabled, false);
    });

    test('setTtsAutoPlay toggles auto-play', () {
      notifier.setTtsAutoPlay(true);
      expect(notifier.state.ttsAutoPlay, true);
    });

    test('setTtsVoice changes voice', () {
      notifier.setTtsVoice('en-US-GuyNeural');
      expect(notifier.state.ttsVoice, 'en-US-GuyNeural');
    });

    test('multiple sequential state changes accumulate correctly', () {
      notifier.setDarkMode(false);
      notifier.setLanguage('en');
      notifier.setTtsEnabled(true);
      notifier.setTtsVoice('en-US-JennyNeural');

      expect(notifier.state.darkMode, false);
      expect(notifier.state.language, 'en');
      expect(notifier.state.ttsEnabled, true);
      expect(notifier.state.ttsVoice, 'en-US-JennyNeural');
      // Other fields remain at defaults
      expect(notifier.state.aiProvider, AIProvider.claude);
      expect(notifier.state.aiModel, 'auto');
    });

    test('state updates are immutable (old state is not modified)', () {
      final oldState = notifier.state;
      notifier.setDarkMode(false);
      final newState = notifier.state;

      expect(oldState.darkMode, true); // old state unchanged
      expect(newState.darkMode, false);
      expect(identical(oldState, newState), false);
    });
  });
}
