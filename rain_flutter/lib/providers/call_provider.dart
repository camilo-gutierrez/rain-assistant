import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/call_service.dart';
import '../services/voice_mode_service.dart';
import 'audio_provider.dart';
import 'connection_provider.dart';

/// Global singleton for CallService.
final callServiceProvider = Provider<CallService>((ref) {
  final ws = ref.read(webSocketServiceProvider);
  final audio = ref.read(audioServiceProvider);
  final voice = VoiceModeService();
  final service = CallService(ws, audio, voice);
  ref.onDispose(() => service.dispose());
  return service;
});
