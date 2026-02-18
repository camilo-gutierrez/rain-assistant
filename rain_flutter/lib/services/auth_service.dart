import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/auth.dart';

class AuthService {
  static const _tokenKey = 'rain_auth_token';
  static const _serverUrlKey = 'rain_server_url';

  final _secureStorage = const FlutterSecureStorage();
  late final Dio _dio;

  String? _serverUrl;
  String? _token;

  String? get serverUrl => _serverUrl;
  String? get token => _token;
  bool get isAuthenticated => _token != null;

  String get apiUrl => '$_serverUrl/api';
  String get wsUrl {
    if (_serverUrl == null) return '';
    final uri = Uri.parse(_serverUrl!);
    final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
    return '$scheme://${uri.host}:${uri.port}/ws';
  }

  AuthService() {
    _dio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ));
  }

  /// Load persisted server URL and token on app start.
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _serverUrl = prefs.getString(_serverUrlKey);
    _token = await _secureStorage.read(key: _tokenKey);
  }

  /// Persist the server URL.
  Future<void> setServerUrl(String url) async {
    // Normalize: remove trailing slash
    _serverUrl = url.endsWith('/') ? url.substring(0, url.length - 1) : url;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_serverUrlKey, _serverUrl!);
  }

  /// Check if the server is reachable.
  Future<bool> pingServer() async {
    if (_serverUrl == null) return false;
    try {
      final res = await _dio.get('$_serverUrl/');
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Authenticate with PIN. Returns AuthResponse.
  Future<AuthResponse> authenticate(String pin) async {
    try {
      final res = await _dio.post(
        '$apiUrl/auth',
        data: {'pin': pin},
        options: Options(
          contentType: 'application/json',
          validateStatus: (s) => s != null && s < 500,
        ),
      );
      final auth = AuthResponse.fromJson(res.data);
      if (auth.success) {
        _token = auth.token;
        await _secureStorage.write(key: _tokenKey, value: _token);
      }
      return auth;
    } on DioException catch (e) {
      return AuthResponse(error: e.message ?? 'Connection error');
    }
  }

  /// Logout: revoke current token.
  Future<void> logout() async {
    if (_token == null) return;
    try {
      await _dio.post(
        '$apiUrl/logout',
        options: Options(headers: _authHeaders()),
      );
    } catch (_) {}
    await clearToken();
  }

  /// Clear stored token without server call.
  Future<void> clearToken() async {
    _token = null;
    await _secureStorage.delete(key: _tokenKey);
  }

  /// Clear everything (server URL + token).
  Future<void> clearAll() async {
    await clearToken();
    _serverUrl = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_serverUrlKey);
  }

  Map<String, String> _authHeaders() => {
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  /// Convenience: create a Dio instance configured for authenticated requests.
  Dio get authenticatedDio {
    final dio = Dio(BaseOptions(
      baseUrl: apiUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
    ));
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        // Auto-handle 429 with Retry-After
        if (error.response?.statusCode == 429) {
          final retryAfter =
              int.tryParse(error.response?.headers.value('Retry-After') ?? '2') ?? 2;
          final wait = retryAfter.clamp(1, 30);
          await Future.delayed(Duration(seconds: wait));
          try {
            final res = await dio.fetch(error.requestOptions);
            handler.resolve(res);
            return;
          } catch (_) {}
        }
        handler.next(error);
      },
    ));
    return dio;
  }
}
