import 'dart:async' show unawaited;

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
  final String voiceMode; // "push-to-talk" | "vad" | "talk-mode" | "wake-word"
  final double vadSensitivity;
  final int silenceTimeout; // ms

  const SettingsState({
    this.darkMode = true,
    this.language = 'es',
    this.aiProvider = AIProvider.claude,
    this.aiModel = 'auto',
    this.ttsEnabled = false,
    this.ttsAutoPlay = false,
    this.ttsVoice = 'es-MX-DaliaNeural',
    this.voiceMode = 'push-to-talk',
    this.vadSensitivity = 0.5,
    this.silenceTimeout = 800,
  });

  SettingsState copyWith({
    bool? darkMode,
    String? language,
    AIProvider? aiProvider,
    String? aiModel,
    bool? ttsEnabled,
    bool? ttsAutoPlay,
    String? ttsVoice,
    String? voiceMode,
    double? vadSensitivity,
    int? silenceTimeout,
  }) =>
      SettingsState(
        darkMode: darkMode ?? this.darkMode,
        language: language ?? this.language,
        aiProvider: aiProvider ?? this.aiProvider,
        aiModel: aiModel ?? this.aiModel,
        ttsEnabled: ttsEnabled ?? this.ttsEnabled,
        ttsAutoPlay: ttsAutoPlay ?? this.ttsAutoPlay,
        ttsVoice: ttsVoice ?? this.ttsVoice,
        voiceMode: voiceMode ?? this.voiceMode,
        vadSensitivity: vadSensitivity ?? this.vadSensitivity,
        silenceTimeout: silenceTimeout ?? this.silenceTimeout,
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
      voiceMode: prefs.getString('voiceMode') ?? 'push-to-talk',
      vadSensitivity: prefs.getDouble('vadSensitivity') ?? 0.5,
      silenceTimeout: prefs.getInt('silenceTimeout') ?? 800,
    );
  }

  Future<void> _save(String key, dynamic value) async {
    final prefs = await SharedPreferences.getInstance();
    if (value is bool) {
      await prefs.setBool(key, value);
    } else if (value is String) {
      await prefs.setString(key, value);
    } else if (value is double) {
      await prefs.setDouble(key, value);
    } else if (value is int) {
      await prefs.setInt(key, value);
    }
  }

  void setDarkMode(bool v) {
    state = state.copyWith(darkMode: v);
    unawaited(_save('darkMode', v));
  }

  void setLanguage(String v) {
    state = state.copyWith(language: v);
    unawaited(_save('language', v));
  }

  void setAIProvider(AIProvider v) {
    // Reset model to first available when switching provider
    final models = providerModels[v] ?? [];
    final model = models.isNotEmpty ? models.first.id : 'auto';
    state = state.copyWith(aiProvider: v, aiModel: model);
    unawaited(_save('aiProvider', v.name));
    unawaited(_save('aiModel', model));
  }

  void setAIModel(String v) {
    state = state.copyWith(aiModel: v);
    unawaited(_save('aiModel', v));
  }

  void setTtsEnabled(bool v) {
    // When enabling TTS, also enable autoPlay by default
    if (v && !state.ttsAutoPlay) {
      state = state.copyWith(ttsEnabled: v, ttsAutoPlay: true);
      unawaited(_save('ttsAutoPlay', true));
    } else {
      state = state.copyWith(ttsEnabled: v);
    }
    unawaited(_save('ttsEnabled', v));
  }

  void setTtsAutoPlay(bool v) {
    state = state.copyWith(ttsAutoPlay: v);
    unawaited(_save('ttsAutoPlay', v));
  }

  void setTtsVoice(String v) {
    state = state.copyWith(ttsVoice: v);
    unawaited(_save('ttsVoice', v));
  }

  void setVoiceMode(String v) {
    state = state.copyWith(voiceMode: v);
    unawaited(_save('voiceMode', v));
  }

  void setVadSensitivity(double v) {
    state = state.copyWith(vadSensitivity: v);
    unawaited(_save('vadSensitivity', v));
  }

  void setSilenceTimeout(int v) {
    state = state.copyWith(silenceTimeout: v);
    unawaited(_save('silenceTimeout', v));
  }
}

final settingsProvider =
    StateNotifierProvider<SettingsNotifier, SettingsState>((ref) {
  return SettingsNotifier();
});
