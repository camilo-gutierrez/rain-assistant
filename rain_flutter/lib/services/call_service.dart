import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:record/record.dart';

import 'audio_service.dart';
import 'voice_mode_service.dart';
import 'websocket_service.dart';

/// Phase of a call lifecycle.
enum CallPhase { idle, connecting, active, ending }

/// Manages the full voice call lifecycle:
/// - PCM audio streaming to backend via WebSocket
/// - Voice state tracking (listening/recording/transcribing/processing/speaking)
/// - Auto-TTS playback of assistant responses
/// - Call duration timer
/// - Mute/unmute control
/// - Audio level metering for visualizer
class CallService {
  final WebSocketService _ws;
  final AudioService _audioService;
  final VoiceModeService voiceService;

  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _audioStreamSub;
  StreamSubscription<Map<String, dynamic>>? _wsMsgSub;
  Timer? _durationTimer;

  // ── Observable state ──
  final ValueNotifier<CallPhase> phase = ValueNotifier(CallPhase.idle);
  final ValueNotifier<Duration> duration = ValueNotifier(Duration.zero);
  final ValueNotifier<bool> isMuted = ValueNotifier(false);
  final ValueNotifier<double> audioLevel = ValueNotifier(0.0);

  /// The ID of the agent this call is for.
  String? _agentId;

  /// TTS voice to use during call (from settings).
  String _ttsVoice = 'es-MX-DaliaNeural';

  /// Callback when assistant sends a final response during call.
  /// The ChatScreen hooks this to auto-send transcriptions.
  void Function(String text)? onTranscriptionReady;

  /// Callback when assistant message is fully received (for auto-TTS).
  void Function(String text)? onAssistantResponse;

  /// Whether TTS should auto-play during calls.
  bool autoTts = true;

  /// Track if we're currently speaking TTS.
  bool _isSpeakingTts = false;

  CallService(this._ws, this._audioService, this.voiceService);

  bool get isActive => phase.value == CallPhase.active;
  bool get isInCall => phase.value != CallPhase.idle;

  /// Start a voice call.
  Future<void> startCall({
    required String agentId,
    required String voiceMode,
    required double vadSensitivity,
    required int silenceTimeout,
    required String ttsVoice,
    required bool ttsEnabled,
  }) async {
    if (isInCall) return;

    _agentId = agentId;
    _ttsVoice = ttsVoice;
    autoTts = ttsEnabled;
    phase.value = CallPhase.connecting;

    // Haptic feedback
    HapticFeedback.mediumImpact();

    // 1. Check microphone permission
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      phase.value = CallPhase.idle;
      return;
    }

    // 2. Send voice mode setup to backend
    _ws.send({
      'type': 'voice_mode_set',
      'mode': 'talk-mode',
      'agent_id': agentId,
      'vad_threshold': vadSensitivity,
      'silence_timeout': silenceTimeout,
    });

    _ws.send({
      'type': 'talk_mode_start',
      'agent_id': agentId,
    });

    // 3. Activate voice state machine
    voiceService.activate(VoiceMode.talkMode);

    // 4. Start listening to WebSocket for voice events
    _startWsListener();

    // 5. Start PCM audio streaming
    await _startAudioStreaming();

    // 6. Start duration timer
    duration.value = Duration.zero;
    _durationTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      duration.value += const Duration(seconds: 1);
    });

    // 7. Transition to active
    phase.value = CallPhase.active;
    HapticFeedback.lightImpact();
  }

  /// End the voice call gracefully.
  Future<void> endCall() async {
    if (phase.value == CallPhase.idle) return;
    phase.value = CallPhase.ending;
    HapticFeedback.mediumImpact();

    // Stop audio streaming
    await _stopAudioStreaming();

    // Stop TTS if playing
    await _audioService.stop();
    _isSpeakingTts = false;

    // Tell backend to stop
    if (_agentId != null) {
      _ws.send({'type': 'talk_mode_stop', 'agent_id': _agentId});
      _ws.send({
        'type': 'voice_mode_set',
        'mode': 'push-to-talk',
        'agent_id': _agentId,
      });
    }

    // Stop listening
    _wsMsgSub?.cancel();
    _wsMsgSub = null;

    // Stop timer
    _durationTimer?.cancel();
    _durationTimer = null;

    // Reset state
    voiceService.deactivate();
    isMuted.value = false;
    audioLevel.value = 0.0;
    _agentId = null;
    phase.value = CallPhase.idle;
  }

  /// Toggle mute (stops sending audio but keeps call alive).
  void toggleMute() {
    isMuted.value = !isMuted.value;
    HapticFeedback.selectionClick();
  }

  /// Play TTS for an assistant response during a call.
  Future<void> speakResponse(String text) async {
    if (!isActive || !autoTts) return;

    _isSpeakingTts = true;
    voiceService.voiceState.value = VoiceState.speaking;

    await _audioService.synthesize(text, _ttsVoice);

    // Wait for playback to finish
    await _waitForTtsComplete();

    _isSpeakingTts = false;

    // Return to listening after TTS completes
    if (isActive) {
      voiceService.voiceState.value = VoiceState.listening;
    }
  }

  /// Handle interruption (user starts speaking during TTS).
  Future<void> _handleInterruption() async {
    if (_isSpeakingTts) {
      await _audioService.stop();
      _isSpeakingTts = false;
      if (_agentId != null) {
        _ws.send({'type': 'talk_interruption', 'agent_id': _agentId});
      }
    }
  }

  // ── Private ──

  Future<void> _startAudioStreaming() async {
    try {
      // Configure for 16kHz mono PCM16 (what the backend expects)
      final stream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
        ),
      );

      _audioStreamSub = stream.listen(
        (Uint8List chunk) {
          if (isMuted.value || !isActive) return;

          // Calculate audio level for visualizer (RMS of PCM16 samples)
          _updateAudioLevel(chunk);

          // Send to backend as base64-encoded PCM
          _ws.send({
            'type': 'audio_chunk',
            'agent_id': _agentId,
            'data': base64Encode(chunk),
          });
        },
        onError: (e) {
          debugPrint('[Call] Audio stream error: $e');
        },
      );
    } catch (e) {
      debugPrint('[Call] Failed to start audio stream: $e');
      // Fallback: end the call if we can't stream audio
      await endCall();
    }
  }

  Future<void> _stopAudioStreaming() async {
    await _audioStreamSub?.cancel();
    _audioStreamSub = null;
    try {
      await _recorder.stop();
    } catch (_) {}
    audioLevel.value = 0.0;
  }

  void _startWsListener() {
    _wsMsgSub?.cancel();
    _wsMsgSub = _ws.messageStream.listen((msg) {
      if (!isActive) return;

      final handled = voiceService.handleMessage(msg);
      if (!handled) return;

      final type = msg['type'] as String?;

      // Auto-send transcription as chat message
      if (type == 'voice_transcription' && msg['is_final'] == true) {
        final text = voiceService.lastTranscription.value;
        if (text.isNotEmpty) {
          onTranscriptionReady?.call(text);
          voiceService.lastTranscription.value = '';
        }
      }

      // Handle interruption: user speaks during TTS
      if (type == 'vad_event' && msg['event'] == 'speech_start') {
        _handleInterruption();
      }
    });
  }

  /// Compute RMS audio level from PCM16 samples (0.0 to 1.0).
  void _updateAudioLevel(Uint8List chunk) {
    if (chunk.length < 4) return;
    final samples = chunk.buffer.asInt16List(chunk.offsetInBytes, chunk.length ~/ 2);
    double sum = 0;
    for (final s in samples) {
      sum += s * s;
    }
    final rms = (sum / samples.length).clamp(0, 32768 * 32768);
    // Normalize: max PCM16 amplitude is 32768
    final normalized = (rms / (32768 * 32768));
    // Apply sqrt for perceptual scaling
    final level = normalized > 0 ? (normalized * 4).clamp(0.0, 1.0) : 0.0;
    audioLevel.value = level;
  }

  /// Wait for TTS playback to complete.
  Future<void> _waitForTtsComplete() async {
    // Wait for audio to start playing, then wait for it to finish
    final completer = Completer<void>();
    void listener() {
      final state = _audioService.playbackState.value;
      if (state == TtsPlaybackState.idle || state == TtsPlaybackState.error) {
        if (!completer.isCompleted) completer.complete();
      }
    }

    _audioService.playbackState.addListener(listener);

    // If already idle (failed to start), resolve immediately
    if (_audioService.playbackState.value == TtsPlaybackState.idle ||
        _audioService.playbackState.value == TtsPlaybackState.error) {
      // Give a moment for synthesis to start
      await Future.delayed(const Duration(milliseconds: 500));
      if (_audioService.playbackState.value == TtsPlaybackState.idle ||
          _audioService.playbackState.value == TtsPlaybackState.error) {
        _audioService.playbackState.removeListener(listener);
        return;
      }
    }

    // Timeout after 2 minutes max
    await completer.future.timeout(
      const Duration(minutes: 2),
      onTimeout: () {},
    );
    _audioService.playbackState.removeListener(listener);
  }

  void dispose() {
    _audioStreamSub?.cancel();
    _wsMsgSub?.cancel();
    _durationTimer?.cancel();
    _recorder.dispose();
    phase.dispose();
    duration.dispose();
    isMuted.dispose();
    audioLevel.dispose();
  }
}
