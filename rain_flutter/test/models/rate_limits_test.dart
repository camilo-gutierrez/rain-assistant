import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/models/rate_limits.dart';

void main() {
  group('RateLimits', () {
    test('default constructor has all null fields', () {
      const limits = RateLimits();
      expect(limits.requestsLimit, isNull);
      expect(limits.requestsRemaining, isNull);
      expect(limits.requestsReset, isNull);
      expect(limits.inputTokensLimit, isNull);
      expect(limits.inputTokensRemaining, isNull);
      expect(limits.inputTokensReset, isNull);
      expect(limits.outputTokensLimit, isNull);
      expect(limits.outputTokensRemaining, isNull);
      expect(limits.outputTokensReset, isNull);
    });

    test('hasData returns false when requestsLimit is null', () {
      const limits = RateLimits();
      expect(limits.hasData, false);
    });

    test('hasData returns true when requestsLimit is set', () {
      const limits = RateLimits(requestsLimit: 1000);
      expect(limits.hasData, true);
    });

    group('requestsPercent', () {
      test('returns 1.0 when no data', () {
        const limits = RateLimits();
        expect(limits.requestsPercent, 1.0);
      });

      test('returns correct ratio', () {
        const limits = RateLimits(
          requestsLimit: 1000,
          requestsRemaining: 750,
        );
        expect(limits.requestsPercent, 0.75);
      });

      test('returns 0.0 when remaining is 0', () {
        const limits = RateLimits(
          requestsLimit: 1000,
          requestsRemaining: 0,
        );
        expect(limits.requestsPercent, 0.0);
      });

      test('returns 1.0 when limit is 0 (avoid division by zero)', () {
        const limits = RateLimits(
          requestsLimit: 0,
          requestsRemaining: 0,
        );
        expect(limits.requestsPercent, 1.0);
      });

      test('returns 1.0 when remaining is null', () {
        const limits = RateLimits(requestsLimit: 1000);
        expect(limits.requestsPercent, 1.0);
      });
    });

    group('inputTokensPercent', () {
      test('returns 1.0 when no data', () {
        const limits = RateLimits();
        expect(limits.inputTokensPercent, 1.0);
      });

      test('returns correct ratio', () {
        const limits = RateLimits(
          inputTokensLimit: 100000,
          inputTokensRemaining: 80000,
        );
        expect(limits.inputTokensPercent, 0.8);
      });

      test('returns 1.0 when limit is 0', () {
        const limits = RateLimits(
          inputTokensLimit: 0,
          inputTokensRemaining: 0,
        );
        expect(limits.inputTokensPercent, 1.0);
      });
    });

    group('outputTokensPercent', () {
      test('returns 1.0 when no data', () {
        const limits = RateLimits();
        expect(limits.outputTokensPercent, 1.0);
      });

      test('returns correct ratio', () {
        const limits = RateLimits(
          outputTokensLimit: 50000,
          outputTokensRemaining: 25000,
        );
        expect(limits.outputTokensPercent, 0.5);
      });

      test('returns 1.0 when limit is 0', () {
        const limits = RateLimits(
          outputTokensLimit: 0,
          outputTokensRemaining: 0,
        );
        expect(limits.outputTokensPercent, 1.0);
      });
    });

    test('fromJson parses all fields correctly', () {
      final json = {
        'requests-limit': 1000,
        'requests-remaining': 950,
        'requests-reset': '2024-01-15T12:00:00Z',
        'input-tokens-limit': 100000,
        'input-tokens-remaining': 90000,
        'input-tokens-reset': '2024-01-15T12:00:00Z',
        'output-tokens-limit': 50000,
        'output-tokens-remaining': 45000,
        'output-tokens-reset': '2024-01-15T12:00:00Z',
      };
      final limits = RateLimits.fromJson(json);
      expect(limits.requestsLimit, 1000);
      expect(limits.requestsRemaining, 950);
      expect(limits.requestsReset, '2024-01-15T12:00:00Z');
      expect(limits.inputTokensLimit, 100000);
      expect(limits.inputTokensRemaining, 90000);
      expect(limits.inputTokensReset, '2024-01-15T12:00:00Z');
      expect(limits.outputTokensLimit, 50000);
      expect(limits.outputTokensRemaining, 45000);
      expect(limits.outputTokensReset, '2024-01-15T12:00:00Z');
    });

    test('fromJson handles empty JSON', () {
      final limits = RateLimits.fromJson({});
      expect(limits.requestsLimit, isNull);
      expect(limits.requestsRemaining, isNull);
      expect(limits.hasData, false);
    });

    test('fromJson handles partial data', () {
      final limits = RateLimits.fromJson({
        'requests-limit': 500,
        // All others missing
      });
      expect(limits.requestsLimit, 500);
      expect(limits.requestsRemaining, isNull);
      expect(limits.hasData, true);
      expect(limits.requestsPercent, 1.0); // remaining is null
    });
  });
}
