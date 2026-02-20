import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

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
        options: Options(contentType: 'multipart/form-data'),
      );

      if (response.statusCode == 200 && response.data is Map) {
        return response.data['text'] as String?;
      }
    } catch (_) {} // TODO(audit#6): Log or surface transcription errors instead of silently swallowing

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
