class AuthResponse {
  final String? token;
  final String? error;
  final int? remainingAttempts;
  final bool locked;
  final int? remainingSeconds;
  final int? maxDevices;
  final List<DeviceInfo>? devices;

  const AuthResponse({
    this.token,
    this.error,
    this.remainingAttempts,
    this.locked = false,
    this.remainingSeconds,
    this.maxDevices,
    this.devices,
  });

  bool get success => token != null && error == null;
  bool get deviceLimitReached => error == 'device_limit_reached';

  factory AuthResponse.fromJson(Map<String, dynamic> json) => AuthResponse(
        token: json['token'],
        error: json['error'],
        remainingAttempts: json['remaining_attempts'],
        locked: json['locked'] ?? false,
        remainingSeconds: json['remaining_seconds'],
        maxDevices: json['max_devices'],
      );
}

class DeviceInfo {
  final String deviceId;
  final String deviceName;
  final String clientIp;
  final double createdAt;
  final double lastActivity;
  final bool isCurrent;

  const DeviceInfo({
    required this.deviceId,
    required this.deviceName,
    required this.clientIp,
    required this.createdAt,
    required this.lastActivity,
    required this.isCurrent,
  });

  factory DeviceInfo.fromJson(Map<String, dynamic> json) => DeviceInfo(
        deviceId: json['device_id'] ?? '',
        deviceName: json['device_name'] ?? '',
        clientIp: json['client_ip'] ?? '',
        createdAt: (json['created_at'] ?? 0).toDouble(),
        lastActivity: (json['last_activity'] ?? 0).toDouble(),
        isCurrent: json['is_current'] ?? false,
      );
}
