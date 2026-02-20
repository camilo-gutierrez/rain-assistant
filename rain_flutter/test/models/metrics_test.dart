import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/models/metrics.dart';

void main() {
  group('MetricsTotals', () {
    test('default constructor has zeroed values', () {
      const totals = MetricsTotals();
      expect(totals.cost, 0);
      expect(totals.sessions, 0);
      expect(totals.avgDurationMs, 0);
      expect(totals.avgCost, 0);
      expect(totals.totalTurns, 0);
      expect(totals.totalInputTokens, 0);
      expect(totals.totalOutputTokens, 0);
    });

    test('fromJson parses all fields correctly', () {
      final json = {
        'cost': 12.50,
        'sessions': 5,
        'avg_duration_ms': 45000.0,
        'avg_cost': 2.50,
        'total_turns': 100,
        'total_input_tokens': 50000,
        'total_output_tokens': 30000,
      };
      final totals = MetricsTotals.fromJson(json);
      expect(totals.cost, 12.50);
      expect(totals.sessions, 5);
      expect(totals.avgDurationMs, 45000.0);
      expect(totals.avgCost, 2.50);
      expect(totals.totalTurns, 100);
      expect(totals.totalInputTokens, 50000);
      expect(totals.totalOutputTokens, 30000);
    });

    test('fromJson handles missing fields with defaults', () {
      final totals = MetricsTotals.fromJson({});
      expect(totals.cost, 0.0);
      expect(totals.sessions, 0);
      expect(totals.avgDurationMs, 0.0);
      expect(totals.avgCost, 0.0);
      expect(totals.totalTurns, 0);
      expect(totals.totalInputTokens, 0);
      expect(totals.totalOutputTokens, 0);
    });

    test('fromJson converts int cost to double', () {
      final totals = MetricsTotals.fromJson({'cost': 10});
      expect(totals.cost, 10.0);
      expect(totals.cost, isA<double>());
    });

    test('fromJson converts int avg_duration_ms to double', () {
      final totals = MetricsTotals.fromJson({'avg_duration_ms': 5000});
      expect(totals.avgDurationMs, 5000.0);
      expect(totals.avgDurationMs, isA<double>());
    });
  });

  group('MetricsData', () {
    test('default constructor has empty collections', () {
      const data = MetricsData();
      expect(data.allTime.cost, 0);
      expect(data.today.cost, 0);
      expect(data.thisWeek.cost, 0);
      expect(data.thisMonth.cost, 0);
      expect(data.byHour, isEmpty);
      expect(data.byDow, isEmpty);
      expect(data.byDay, isEmpty);
      expect(data.byMonth, isEmpty);
    });

    test('fromJson parses nested totals structure', () {
      final json = {
        'totals': {
          'all_time': {
            'cost': 100.0,
            'sessions': 50,
            'total_turns': 500,
            'total_input_tokens': 250000,
            'total_output_tokens': 150000,
          },
          'today': {
            'cost': 5.0,
            'sessions': 3,
          },
          'this_week': {
            'cost': 25.0,
            'sessions': 15,
          },
          'this_month': {
            'cost': 80.0,
            'sessions': 40,
          },
        },
        'by_hour': [
          {'hour': 9, 'count': 10},
          {'hour': 14, 'count': 20},
        ],
        'by_dow': [
          {'dow': 'Monday', 'count': 15},
        ],
        'by_day': [
          {'date': '2024-01-15', 'cost': 3.50},
        ],
        'by_month': [
          {'month': '2024-01', 'cost': 80.0},
        ],
      };
      final data = MetricsData.fromJson(json);
      expect(data.allTime.cost, 100.0);
      expect(data.allTime.sessions, 50);
      expect(data.allTime.totalTurns, 500);
      expect(data.today.cost, 5.0);
      expect(data.today.sessions, 3);
      expect(data.thisWeek.cost, 25.0);
      expect(data.thisMonth.cost, 80.0);
      expect(data.byHour.length, 2);
      expect(data.byHour[0]['hour'], 9);
      expect(data.byDow.length, 1);
      expect(data.byDay.length, 1);
      expect(data.byMonth.length, 1);
    });

    test('fromJson handles missing totals key', () {
      final data = MetricsData.fromJson({});
      expect(data.allTime.cost, 0);
      expect(data.today.cost, 0);
      expect(data.thisWeek.cost, 0);
      expect(data.thisMonth.cost, 0);
    });

    test('fromJson handles null time series arrays', () {
      final data = MetricsData.fromJson({'totals': {}});
      expect(data.byHour, isEmpty);
      expect(data.byDow, isEmpty);
      expect(data.byDay, isEmpty);
      expect(data.byMonth, isEmpty);
    });

    test('fromJson handles empty totals sub-keys', () {
      final data = MetricsData.fromJson({
        'totals': {
          'all_time': null,
          'today': null,
          'this_week': null,
          'this_month': null,
        },
      });
      // Should use empty map fallback, resulting in zero defaults
      expect(data.allTime.cost, 0);
      expect(data.today.sessions, 0);
    });
  });
}
