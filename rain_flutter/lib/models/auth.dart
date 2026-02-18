class AuthResponse {
  final String? token;
  final String? error;
  final int? remainingAttempts;
  final bool locked;
  final int? remainingSeconds;

  const AuthResponse({
    this.token,
    this.error,
    this.remainingAttempts,
    this.locked = false,
    this.remainingSeconds,
  });

  bool get success => token != null && error == null;

  factory AuthResponse.fromJson(Map<String, dynamic> json) => AuthResponse(
        token: json['token'],
        error: json['error'],
        remainingAttempts: json['remaining_attempts'],
        locked: json['locked'] ?? false,
        remainingSeconds: json['remaining_seconds'],
      );
}
