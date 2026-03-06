import 'dart:async';
import 'dart:typed_data';

import 'package:audio_session/audio_session.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import 'crash_reporting_service.dart';

enum TtsPlaybackState { idle, loading, playing, error }

class AudioService {
  final Dio _dio;
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  String? _recordingPath;

  /// Observable playback state for UI feedback.
  final ValueNotifier<TtsPlaybackState> playbackState =
      ValueNotifier(TtsPlaybackState.idle);

  AudioService(this._dio) {
    _player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        playbackState.value = TtsPlaybackState.idle;
      }
    });
  }

  /// Configure the audio session for background playback and recording.
  /// Call once during app startup.
  Future<void> initAudioSession() async {
    final session = await AudioSession.instance;
    await session.configure(AudioSessionConfiguration(
      avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
      avAudioSessionCategoryOptions:
          AVAudioSessionCategoryOptions.defaultToSpeaker |
          AVAudioSessionCategoryOptions.allowBluetooth,
      avAudioSessionMode: AVAudioSessionMode.spokenAudio,
      androidAudioAttributes: const AndroidAudioAttributes(
        contentType: AndroidAudioContentType.speech,
        usage: AndroidAudioUsage.assistant,
      ),
      androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
    ));
  }

  /// Start recording audio to a temporary .m4a file.
  Future<void> startRecording() async {
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) return;

    final dir = await getTemporaryDirectory();
    _recordingPath =
        '${dir.path}/rain_recording_${DateTime.now().millisecondsSinceEpoch}.m4a';

    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.aacLc,
        sampleRate: 44100,
        bitRate: 128000,
      ),
      path: _recordingPath!,
    );
  }

  /// Stop recording and upload to /api/upload-audio.
  /// Returns the transcribed text, or null on failure.
  Future<String?> stopAndUpload() async {
    final path = await _recorder.stop();
    if (path == null) return null;

    try {
      final formData = FormData.fromMap({
        'audio': await MultipartFile.fromFile(path, filename: 'audio.m4a'),
      });

      final response = await _dio.post(
        '/upload-audio',
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 120),
        ),
      );

      if (response.statusCode == 200 && response.data is Map) {
        return response.data['text'] as String?;
      }
    } catch (e, stack) {
      debugPrint('[Audio] Transcription upload failed: $e');
      CrashReportingService.instance.captureException(
        e,
        stackTrace: stack,
        context: 'audio_transcription',
      );
    }

    return null;
  }

  /// Stop any currently playing TTS audio.
  Future<void> stop() async {
    await _player.stop();
    playbackState.value = TtsPlaybackState.idle;
  }

  /// Call /api/synthesize and play the returned MP3 audio.
  Future<void> synthesize(String text, String voice,
      {String rate = '+0%'}) async {
    if (text.trim().isEmpty) {
      debugPrint('[TTS] Empty text, skipping');
      return;
    }

    // Stop any current playback first
    await _player.stop();

    // Limit to 5000 chars as per spec
    final truncated = text.length > 5000 ? text.substring(0, 5000) : text;

    playbackState.value = TtsPlaybackState.loading;
    debugPrint('[TTS] Synthesizing ${truncated.length} chars with voice=$voice');

    try {
      final response = await _dio.post(
        '/synthesize',
        data: {'text': truncated, 'voice': voice, 'rate': rate},
        options: Options(
          responseType: ResponseType.bytes,
          receiveTimeout: const Duration(seconds: 60),
        ),
      );

      if (response.statusCode == 204) {
        debugPrint('[TTS] Server returned 204 (nothing to synthesize)');
        playbackState.value = TtsPlaybackState.idle;
        return;
      }

      final bytes = response.data as Uint8List;
      if (bytes.isEmpty) {
        debugPrint('[TTS] Server returned empty bytes');
        playbackState.value = TtsPlaybackState.idle;
        return;
      }

      debugPrint('[TTS] Received ${bytes.length} bytes, playing...');

      // Play from bytes in memory
      await _player.setAudioSource(_BytesAudioSource(bytes));
      playbackState.value = TtsPlaybackState.playing;
      await _player.play();
    } catch (e) {
      debugPrint('[TTS] Error: $e');
      playbackState.value = TtsPlaybackState.error;
      // Reset to idle after a moment so UI can recover
      Future.delayed(const Duration(seconds: 2), () {
        if (playbackState.value == TtsPlaybackState.error) {
          playbackState.value = TtsPlaybackState.idle;
        }
      });
    }
  }

  void dispose() {
    _recorder.dispose();
    _player.dispose();
    playbackState.dispose();
  }
}

/// AudioSource that plays from in-memory bytes.
class _BytesAudioSource extends StreamAudioSource {
  final Uint8List _bytes;
  _BytesAudioSource(this._bytes);

  @override
  Future<StreamAudioResponse> request([int? start, int? end]) async {
    final s = start ?? 0;
    final e = end ?? _bytes.length;
    return StreamAudioResponse(
      sourceLength: _bytes.length,
      contentLength: e - s,
      offset: s,
      stream: Stream.value(_bytes.sublist(s, e)),
      contentType: 'audio/mpeg',
    );
  }
}

/// Plays sentence-level TTS audio streamed from the backend via WebSocket.
///
/// The backend sends multiple small audio chunks per sentence (streaming=true),
/// followed by a `tts_sentence_end` event. This player accumulates chunks for
/// each sentence and plays them sequentially. For minimum latency, the first
/// sentence starts playing as soon as enough data arrives (without waiting for
/// sentence_end).
class StreamingTtsPlayer {
  final AudioPlayer _player = AudioPlayer();

  /// Completed sentences ready to play.
  final List<Uint8List> _readyQueue = [];

  /// Chunks being accumulated for the current sentence.
  final List<Uint8List> _pendingChunks = [];
  int _pendingBytes = 0;

  bool _isPlaying = false;
  bool _cancelled = false;

  /// Minimum bytes before starting playback of the first sentence
  /// (to avoid choppy start). ~8KB ≈ ~0.5s of MP3 audio.
  static const int _earlyPlayThreshold = 8192;
  bool _firstSentencePlayed = false;

  /// Called when all queued sentences have finished playing.
  VoidCallback? onAllDone;

  /// Called when playback starts (first sentence begins).
  VoidCallback? onPlaybackStarted;

  StreamingTtsPlayer() {
    _player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        _playNext();
      }
    });
  }

  /// Add a streaming audio chunk (part of a sentence).
  void addChunk(Uint8List audioBytes) {
    if (_cancelled) return;
    _pendingChunks.add(audioBytes);
    _pendingBytes += audioBytes.length;

    // For the very first sentence: start playing early for minimum latency
    if (!_firstSentencePlayed &&
        !_isPlaying &&
        _pendingBytes >= _earlyPlayThreshold) {
      _flushPendingAndPlay();
    }
  }

  /// Mark the current sentence as complete.
  void sentenceEnd() {
    if (_cancelled) return;
    if (_pendingChunks.isEmpty) return;

    final combined = _combinePending();
    _readyQueue.add(combined);

    if (!_isPlaying) {
      _playNext();
    }
  }

  /// Legacy: enqueue a complete sentence's audio (backward-compatible).
  void enqueue(Uint8List audioBytes) {
    if (_cancelled) return;
    _readyQueue.add(audioBytes);
    if (!_isPlaying) {
      _playNext();
    }
  }

  /// Cancel all pending playback and clear the queue.
  Future<void> cancel() async {
    _cancelled = true;
    _readyQueue.clear();
    _pendingChunks.clear();
    _pendingBytes = 0;
    _isPlaying = false;
    _firstSentencePlayed = false;
    await _player.stop();
  }

  /// Reset state for a new response cycle.
  void reset() {
    _cancelled = false;
    _readyQueue.clear();
    _pendingChunks.clear();
    _pendingBytes = 0;
    _isPlaying = false;
    _firstSentencePlayed = false;
  }

  Uint8List _combinePending() {
    if (_pendingChunks.length == 1) {
      final result = _pendingChunks.first;
      _pendingChunks.clear();
      _pendingBytes = 0;
      return result;
    }
    final builder = BytesBuilder(copy: false);
    for (final c in _pendingChunks) {
      builder.add(c);
    }
    _pendingChunks.clear();
    _pendingBytes = 0;
    return builder.takeBytes();
  }

  /// Flush pending chunks into ready queue and start playback immediately.
  void _flushPendingAndPlay() {
    if (_pendingChunks.isEmpty) return;
    final combined = _combinePending();
    _readyQueue.add(combined);
    _firstSentencePlayed = true;
    _playNext();
  }

  void _playNext() {
    if (_cancelled || _readyQueue.isEmpty) {
      _isPlaying = false;
      if (!_cancelled) {
        onAllDone?.call();
      }
      return;
    }

    final bytes = _readyQueue.removeAt(0);
    _isPlaying = true;
    _firstSentencePlayed = true;

    if (!_cancelled) {
      onPlaybackStarted?.call();
    }

    _player.setAudioSource(_BytesAudioSource(bytes)).then((_) {
      if (!_cancelled) {
        _player.play();
      }
    }).catchError((e) {
      debugPrint('[StreamingTTS] Playback error: $e');
      _playNext(); // Skip failed sentence, try next
    });
  }

  void dispose() {
    _cancelled = true;
    _readyQueue.clear();
    _pendingChunks.clear();
    _player.dispose();
  }
}
