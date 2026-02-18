import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

class AudioService {
  final Dio _dio;
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  String? _recordingPath;

  AudioService(this._dio);

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
    } catch (_) {}

    return null;
  }

  /// Call /api/synthesize and play the returned MP3 audio.
  Future<void> synthesize(String text, String voice,
      {String rate = '+0%'}) async {
    if (text.trim().isEmpty) return;

    // Limit to 5000 chars as per spec
    final truncated = text.length > 5000 ? text.substring(0, 5000) : text;

    try {
      final response = await _dio.post(
        '/synthesize',
        data: {'text': truncated, 'voice': voice, 'rate': rate},
        options: Options(responseType: ResponseType.bytes),
      );

      if (response.statusCode == 204) return; // mostly code, no speech

      final bytes = response.data as Uint8List;
      if (bytes.isEmpty) return;

      // Play from bytes in memory
      await _player.setAudioSource(
        _BytesAudioSource(bytes),
      );
      await _player.play();
    } catch (_) {}
  }

  void dispose() {
    _recorder.dispose();
    _player.dispose();
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
