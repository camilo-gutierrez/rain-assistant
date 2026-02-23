import 'dart:io' show Platform;

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/auth.dart';

class AuthService {
  static const _tokenKey = 'rain_auth_token';
  static const _serverUrlKey = 'rain_server_url';
  static const _deviceIdKey = 'rain_device_id';

  final _secureStorage = const FlutterSecureStorage();
  late final Dio _dio;

  String? _serverUrl;
  String? _token;
  String _deviceId = '';
  String _deviceName = '';

  String? get serverUrl => _serverUrl;
  String? get token => _token;
  bool get isAuthenticated => _token != null;
  String get deviceId => _deviceId;

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

  /// Load persisted server URL, token, and device ID on app start.
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _serverUrl = prefs.getString(_serverUrlKey);
    _token = await _secureStorage.read(key: _tokenKey);

    // Device ID — generate once and persist
    _deviceId = prefs.getString(_deviceIdKey) ?? '';
    if (_deviceId.isEmpty) {
      _deviceId = const Uuid().v4();
      await prefs.setString(_deviceIdKey, _deviceId);
    }

    _deviceName = _detectDeviceName();
  }

  String _detectDeviceName() {
    try {
      final os = Platform.operatingSystem;
      if (os == 'android') return 'Android';
      if (os == 'ios') return 'iPhone';
      if (os == 'windows') return 'Windows PC';
      if (os == 'macos') return 'Mac';
      if (os == 'linux') return 'Linux PC';
      return 'Mobile App';
    } catch (_) {
      return 'Mobile App';
    }
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

  /// Authenticate with PIN. Optionally replace an existing device.
  Future<AuthResponse> authenticate(String pin, {String? replaceDeviceId}) async {
    try {
      final data = <String, dynamic>{
        'pin': pin,
        'device_id': _deviceId,
        'device_name': _deviceName,
      };
      if (replaceDeviceId != null && replaceDeviceId.isNotEmpty) {
        data['replace_device_id'] = replaceDeviceId;
      }
      final res = await _dio.post(
        '$apiUrl/auth',
        data: data,
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

  /// Fetch active devices using PIN (no token required).
  /// Used when device limit is reached and user needs to pick one to replace.
  Future<({List<DeviceInfo> devices, int maxDevices})?> fetchDevicesWithPin(String pin) async {
    try {
      final res = await _dio.post(
        '$apiUrl/auth/devices',
        data: {'pin': pin},
        options: Options(
          contentType: 'application/json',
          validateStatus: (s) => s != null && s < 500,
        ),
      );
      if (res.statusCode != 200) return null;
      final list = (res.data['devices'] as List)
          .map((d) => DeviceInfo.fromJson(d))
          .toList();
      final max = res.data['max_devices'] ?? 2;
      return (devices: list, maxDevices: max as int);
    } catch (_) {
      return null;
    }
  }

  /// Revoke a single device session using PIN (no token required).
  Future<bool> revokeDeviceWithPin(String pin, String deviceId) async {
    try {
      final res = await _dio.post(
        '$apiUrl/auth/revoke-device',
        data: {'pin': pin, 'device_id': deviceId},
        options: Options(
          contentType: 'application/json',
          validateStatus: (s) => s != null && s < 500,
        ),
      );
      return res.statusCode == 200 && res.data['revoked'] == true;
    } catch (_) {
      return false;
    }
  }

  /// Revoke ALL active sessions using PIN (no token required).
  Future<bool> revokeAllWithPin(String pin) async {
    try {
      final res = await _dio.post(
        '$apiUrl/auth/revoke-all',
        data: {'pin': pin},
        options: Options(
          contentType: 'application/json',
          validateStatus: (s) => s != null && s < 500,
        ),
      );
      return res.statusCode == 200 && res.data['revoked_all'] == true;
    } catch (_) {
      return false;
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

  // === Device Management ===

  /// Fetch all active devices.
  Future<({List<DeviceInfo> devices, int maxDevices})> fetchDevices() async {
    try {
      final res = await _dio.get(
        '$apiUrl/devices',
        options: Options(headers: _authHeaders()),
      );
      final list = (res.data['devices'] as List)
          .map((d) => DeviceInfo.fromJson(d))
          .toList();
      final max = res.data['max_devices'] ?? 2;
      return (devices: list, maxDevices: max as int);
    } catch (_) {
      return (devices: <DeviceInfo>[], maxDevices: 2);
    }
  }

  /// Revoke a device by its device_id.
  Future<bool> revokeDevice(String deviceId) async {
    try {
      final res = await _dio.delete(
        '$apiUrl/devices/${Uri.encodeComponent(deviceId)}',
        options: Options(headers: _authHeaders()),
      );
      return res.data['revoked'] == true;
    } catch (_) {
      return false;
    }
  }

  /// Rename a device.
  Future<bool> renameDevice(String deviceId, String name) async {
    try {
      final res = await _dio.patch(
        '$apiUrl/devices/${Uri.encodeComponent(deviceId)}',
        data: {'name': name},
        options: Options(
          headers: _authHeaders(),
          contentType: 'application/json',
        ),
      );
      return res.data['renamed'] == true;
    } catch (_) {
      return false;
    }
  }

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
