import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/provider_info.dart';

class SettingsState {
  final bool darkMode;
  final String language; // "en" | "es"
  final AIProvider aiProvider;
  final String aiModel;
  final bool ttsEnabled;
  final bool ttsAutoPlay;
  final String ttsVoice;

  const SettingsState({
    this.darkMode = true,
    this.language = 'es',
    this.aiProvider = AIProvider.claude,
    this.aiModel = 'auto',
    this.ttsEnabled = false,
    this.ttsAutoPlay = false,
    this.ttsVoice = 'es-MX-DaliaNeural',
  });

  SettingsState copyWith({
    bool? darkMode,
    String? language,
    AIProvider? aiProvider,
    String? aiModel,
    bool? ttsEnabled,
    bool? ttsAutoPlay,
    String? ttsVoice,
  }) =>
      SettingsState(
        darkMode: darkMode ?? this.darkMode,
        language: language ?? this.language,
        aiProvider: aiProvider ?? this.aiProvider,
        aiModel: aiModel ?? this.aiModel,
        ttsEnabled: ttsEnabled ?? this.ttsEnabled,
        ttsAutoPlay: ttsAutoPlay ?? this.ttsAutoPlay,
        ttsVoice: ttsVoice ?? this.ttsVoice,
      );
}

class SettingsNotifier extends StateNotifier<SettingsState> {
  SettingsNotifier() : super(const SettingsState());

  Future<void> loadFromPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    state = SettingsState(
      darkMode: prefs.getBool('darkMode') ?? true,
      language: prefs.getString('language') ?? 'es',
      aiProvider: AIProvider.values.firstWhere(
        (e) => e.name == (prefs.getString('aiProvider') ?? 'claude'),
        orElse: () => AIProvider.claude,
      ),
      aiModel: prefs.getString('aiModel') ?? 'auto',
      ttsEnabled: prefs.getBool('ttsEnabled') ?? false,
      ttsAutoPlay: prefs.getBool('ttsAutoPlay') ?? false,
      ttsVoice: prefs.getString('ttsVoice') ?? 'es-MX-DaliaNeural',
    );
  }

  Future<void> _save(String key, dynamic value) async {
    final prefs = await SharedPreferences.getInstance();
    if (value is bool) {
      await prefs.setBool(key, value);
    } else if (value is String) {
      await prefs.setString(key, value);
    }
  }

  void setDarkMode(bool v) {
    state = state.copyWith(darkMode: v);
    _save('darkMode', v);
  }

  void setLanguage(String v) {
    state = state.copyWith(language: v);
    _save('language', v);
  }

  void setAIProvider(AIProvider v) {
    // Reset model to first available when switching provider
    final models = providerModels[v] ?? [];
    final model = models.isNotEmpty ? models.first.id : 'auto';
    state = state.copyWith(aiProvider: v, aiModel: model);
    _save('aiProvider', v.name);
    _save('aiModel', model);
  }

  void setAIModel(String v) {
    state = state.copyWith(aiModel: v);
    _save('aiModel', v);
  }

  void setTtsEnabled(bool v) {
    state = state.copyWith(ttsEnabled: v);
    _save('ttsEnabled', v);
  }

  void setTtsAutoPlay(bool v) {
    state = state.copyWith(ttsAutoPlay: v);
    _save('ttsAutoPlay', v);
  }

  void setTtsVoice(String v) {
    state = state.copyWith(ttsVoice: v);
    _save('ttsVoice', v);
  }
}

final settingsProvider =
    StateNotifierProvider<SettingsNotifier, SettingsState>((ref) {
  return SettingsNotifier();
});
