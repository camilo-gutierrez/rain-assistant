import 'package:flutter/foundation.dart';

/// Voice mode states matching the backend protocol.
enum VoiceState {
  idle,
  wakeListening,
  listening,
  recording,
  transcribing,
  processing,
  speaking,
}

/// Voice mode options.
enum VoiceMode {
  pushToTalk,
  vad,
  talkMode,
  wakeWord,
}

extension VoiceModeExtension on VoiceMode {
  String get wireValue {
    switch (this) {
      case VoiceMode.pushToTalk:
        return 'push-to-talk';
      case VoiceMode.vad:
        return 'vad';
      case VoiceMode.talkMode:
        return 'talk-mode';
      case VoiceMode.wakeWord:
        return 'wake-word';
    }
  }
}

/// Manages voice mode state and audio streaming to the backend.
///
/// Captures PCM audio from the microphone and streams it via WebSocket
/// as base64-encoded chunks. Listens for VAD events, wake word detection,
/// and transcription results from the backend.
class VoiceModeService {
  final ValueNotifier<VoiceState> voiceState =
      ValueNotifier(VoiceState.idle);
  final ValueNotifier<String> partialTranscription =
      ValueNotifier('');
  final ValueNotifier<String> lastTranscription =
      ValueNotifier('');
  final ValueNotifier<double> wakeWordConfidence =
      ValueNotifier(0.0);

  bool _isActive = false;

  bool get isActive => _isActive;

  /// Handle incoming voice-related WebSocket messages.
  /// Returns true if the message was handled.
  bool handleMessage(Map<String, dynamic> msg) {
    final type = msg['type'] as String?;
    if (type == null) return false;

    switch (type) {
      case 'vad_event':
        final event = msg['event'] as String?;
        if (event == 'speech_start') {
          voiceState.value = VoiceState.recording;
        } else if (event == 'speech_end') {
          voiceState.value = VoiceState.transcribing;
        } else if (event == 'no_speech') {
          voiceState.value = VoiceState.listening;
        }
        return true;

      case 'wake_word_detected':
        wakeWordConfidence.value = (msg['confidence'] as num?)?.toDouble() ?? 0.0;
        voiceState.value = VoiceState.listening;
        return true;

      case 'talk_state_changed':
        final state = msg['state'] as String?;
        voiceState.value = _parseState(state);
        return true;

      case 'voice_transcription':
        final text = msg['text'] as String? ?? '';
        final isFinal = msg['is_final'] as bool? ?? false;
        if (isFinal && text.isNotEmpty) {
          lastTranscription.value = text;
          partialTranscription.value = '';
          voiceState.value = VoiceState.processing;
        }
        return true;

      case 'partial_transcription':
        partialTranscription.value = msg['text'] as String? ?? '';
        if (msg['is_final'] == true) {
          lastTranscription.value = partialTranscription.value;
          partialTranscription.value = '';
        }
        return true;

      case 'voice_mode_changed':
        return true;

      default:
        return false;
    }
  }

  /// Activate voice mode.
  void activate(VoiceMode mode) {
    _isActive = true;
    voiceState.value = mode == VoiceMode.wakeWord
        ? VoiceState.wakeListening
        : VoiceState.listening;
  }

  /// Deactivate voice mode.
  void deactivate() {
    _isActive = false;
    reset();
  }

  /// Reset all state.
  void reset() {
    voiceState.value = VoiceState.idle;
    partialTranscription.value = '';
    lastTranscription.value = '';
    wakeWordConfidence.value = 0.0;
  }

  void dispose() {
    voiceState.dispose();
    partialTranscription.dispose();
    lastTranscription.dispose();
    wakeWordConfidence.dispose();
  }

  VoiceState _parseState(String? state) {
    switch (state) {
      case 'idle':
        return VoiceState.idle;
      case 'wake_listening':
        return VoiceState.wakeListening;
      case 'listening':
        return VoiceState.listening;
      case 'recording':
        return VoiceState.recording;
      case 'transcribing':
        return VoiceState.transcribing;
      case 'processing':
        return VoiceState.processing;
      case 'speaking':
        return VoiceState.speaking;
      default:
        return VoiceState.idle;
    }
  }
}
