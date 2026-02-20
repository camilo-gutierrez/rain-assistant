import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/models/auth.dart';

void main() {
  group('AuthResponse', () {
    test('success is true when token is present and error is null', () {
      const auth = AuthResponse(token: 'jwt-token-123');
      expect(auth.success, true);
      expect(auth.token, 'jwt-token-123');
      expect(auth.error, isNull);
    });

    test('success is false when error is present', () {
      const auth = AuthResponse(error: 'Invalid PIN');
      expect(auth.success, false);
      expect(auth.token, isNull);
    });

    test('success is false when both token and error are present', () {
      const auth = AuthResponse(token: 'tok', error: 'err');
      expect(auth.success, false);
    });

    test('success is false when both are null', () {
      const auth = AuthResponse();
      expect(auth.success, false);
    });

    test('locked defaults to false', () {
      const auth = AuthResponse();
      expect(auth.locked, false);
    });

    test('fromJson parses successful auth response', () {
      final json = {
        'token': 'my-token-456',
      };
      final auth = AuthResponse.fromJson(json);
      expect(auth.success, true);
      expect(auth.token, 'my-token-456');
      expect(auth.error, isNull);
      expect(auth.locked, false);
    });

    test('fromJson parses error response', () {
      final json = {
        'error': 'Incorrect PIN',
        'remaining_attempts': 2,
      };
      final auth = AuthResponse.fromJson(json);
      expect(auth.success, false);
      expect(auth.error, 'Incorrect PIN');
      expect(auth.remainingAttempts, 2);
    });

    test('fromJson parses locked response', () {
      final json = {
        'error': 'Too many attempts',
        'locked': true,
        'remaining_seconds': 300,
      };
      final auth = AuthResponse.fromJson(json);
      expect(auth.success, false);
      expect(auth.locked, true);
      expect(auth.remainingSeconds, 300);
    });

    test('fromJson handles empty JSON', () {
      final auth = AuthResponse.fromJson({});
      expect(auth.token, isNull);
      expect(auth.error, isNull);
      expect(auth.remainingAttempts, isNull);
      expect(auth.locked, false);
      expect(auth.remainingSeconds, isNull);
      expect(auth.success, false);
    });
  });
}
