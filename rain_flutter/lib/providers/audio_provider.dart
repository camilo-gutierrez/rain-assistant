import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/audio_service.dart';
import 'connection_provider.dart';

final audioServiceProvider = Provider<AudioService>((ref) {
  final auth = ref.read(authServiceProvider);
  final service = AudioService(auth.authenticatedDio);
  ref.onDispose(() => service.dispose());
  return service;
});

final isRecordingProvider = StateProvider<bool>((ref) => false);
