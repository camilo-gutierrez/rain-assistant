import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/auth_service.dart';
import '../services/websocket_service.dart';

/// Global singleton for AuthService.
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService();
});

/// Global singleton for WebSocketService.
final webSocketServiceProvider = Provider<WebSocketService>((ref) {
  final ws = WebSocketService();
  ref.onDispose(() => ws.dispose());
  return ws;
});

/// Reactive connection status.
final connectionStatusProvider =
    StreamProvider<ConnectionStatus>((ref) {
  return ref.watch(webSocketServiceProvider).statusStream;
});

/// Stream of parsed WebSocket messages.
final wsMessageProvider =
    StreamProvider<Map<String, dynamic>>((ref) {
  return ref.watch(webSocketServiceProvider).messageStream;
});

/// Whether the user has a server URL configured.
final hasServerUrlProvider = StateProvider<bool>((ref) => false);

/// Whether the user is authenticated (has valid token).
final isAuthenticatedProvider = StateProvider<bool>((ref) => false);

/// Whether the server sent api_key_loaded (skip API key screen).
final apiKeyLoadedProvider = StateProvider<bool>((ref) => false);

/// Status text from the server.
final statusTextProvider = StateProvider<String>((ref) => '');

/// Current AI provider name set by server.
final currentProviderProvider = StateProvider<String>((ref) => 'claude');
