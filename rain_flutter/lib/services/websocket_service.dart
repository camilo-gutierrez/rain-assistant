import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

enum ConnectionStatus { disconnected, connecting, connected, error }

/// Manages the WebSocket connection lifecycle, heartbeat, and auto-reconnect.
class WebSocketService {
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;

  ConnectionStatus _status = ConnectionStatus.disconnected;
  int _consecutiveFailures = 0;

  String? _wsUrl;
  String? _token;

  final _statusController = StreamController<ConnectionStatus>.broadcast();
  final _messageController = StreamController<Map<String, dynamic>>.broadcast();

  /// Stream of connection status changes.
  /// Emits the current status immediately on subscription, then future changes.
  Stream<ConnectionStatus> get statusStream async* {
    yield _status;
    yield* _statusController.stream;
  }

  /// Stream of parsed JSON messages from the server.
  Stream<Map<String, dynamic>> get messageStream => _messageController.stream;

  ConnectionStatus get status => _status;
  bool get isConnected => _status == ConnectionStatus.connected;

  /// Connect to the WebSocket server.
  void connect(String wsUrl, String token) {
    // Cancel any pending reconnect from a previous connection
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _consecutiveFailures = 0;
    _wsUrl = wsUrl;
    _token = token;
    _doConnect();
  }

  Future<void> _doConnect() async {
    if (_wsUrl == null || _token == null) return;

    _setStatus(ConnectionStatus.connecting);
    _cleanup();

    final uri = Uri.parse('$_wsUrl?token=${Uri.encodeComponent(_token!)}');

    try {
      _channel = WebSocketChannel.connect(uri);

      // Wait for the actual WebSocket handshake to complete
      await _channel!.ready;

      _subscription = _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
      );

      _setStatus(ConnectionStatus.connected);
      _consecutiveFailures = 0;
    } catch (e) {
      print('[WS] Connection failed: $e');
      _setStatus(ConnectionStatus.error);
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic raw) {
    if (raw is! String) return;
    try {
      final msg = jsonDecode(raw) as Map<String, dynamic>;

      // Handle ping/pong internally
      if (msg['type'] == 'ping') {
        send({'type': 'pong'});
        return;
      }

      _messageController.add(msg);
    } catch (e) {
      // Surface JSON parse errors (e.g. oversized messages) instead of swallowing
      final preview = raw.length > 200 ? '${raw.substring(0, 200)}...' : raw;
      _messageController.add({
        'type': 'error',
        'text': 'Failed to decode message (${raw.length} bytes): $e\n$preview',
      });
    }
  }

  void _onError(Object error) {
    _setStatus(ConnectionStatus.error);
    _scheduleReconnect();
  }

  void _onDone() {
    final closeCode = _channel?.closeCode;

    if (closeCode == 4001 || closeCode == 4003) {
      // Unauthorized or device revoked — don't reconnect, emit special status
      _setStatus(ConnectionStatus.disconnected);
      _messageController.add({'type': '_unauthorized'});
      return;
    }

    _setStatus(ConnectionStatus.disconnected);

    if (closeCode == 4002) {
      // Idle timeout — quick reconnect
      _reconnectTimer = Timer(const Duration(seconds: 1), _doConnect);
    } else {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _consecutiveFailures++;
    if (_consecutiveFailures > 8) {
      // Too many failures — signal unauthorized to force re-auth
      _messageController.add({'type': '_unauthorized'});
      return;
    }
    // Exponential backoff: 2s, 4s, 6s, 8s, 10s... capped at 15s
    final delay = (_consecutiveFailures * 2).clamp(2, 15);
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: delay), _doConnect);
    // Notify UI about reconnect attempts
    if (_consecutiveFailures >= 3) {
      _messageController.add({
        'type': '_reconnecting',
        'attempt': _consecutiveFailures,
      });
    }
  }

  /// Send a JSON message to the server.
  void send(Map<String, dynamic> message) {
    if (_channel == null) return;
    try {
      _channel!.sink.add(jsonEncode(message));
    } catch (_) {}
  }

  /// Gracefully disconnect.
  void disconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _cleanup();
    _setStatus(ConnectionStatus.disconnected);
  }

  void _cleanup() {
    final sub = _subscription;
    final ch = _channel;
    _subscription = null;
    _channel = null;
    sub?.cancel();
    try {
      ch?.sink.close();
    } catch (_) {}
  }

  void _setStatus(ConnectionStatus s) {
    if (_status == s) return;
    _status = s;
    _statusController.add(s);
  }

  void dispose() {
    disconnect();
    _statusController.close();
    _messageController.close();
  }
}
