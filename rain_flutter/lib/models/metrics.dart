class MetricsTotals {
  final double cost;
  final int sessions;
  final double avgDurationMs;
  final double avgCost;
  final int totalTurns;
  final int totalInputTokens;
  final int totalOutputTokens;

  const MetricsTotals({
    this.cost = 0,
    this.sessions = 0,
    this.avgDurationMs = 0,
    this.avgCost = 0,
    this.totalTurns = 0,
    this.totalInputTokens = 0,
    this.totalOutputTokens = 0,
  });

  factory MetricsTotals.fromJson(Map<String, dynamic> json) => MetricsTotals(
        cost: (json['cost'] ?? 0).toDouble(),
        sessions: (json['sessions'] ?? 0).toInt(),
        avgDurationMs: (json['avg_duration_ms'] ?? 0).toDouble(),
        avgCost: (json['avg_cost'] ?? 0).toDouble(),
        totalTurns: (json['total_turns'] ?? 0).toInt(),
        totalInputTokens: (json['total_input_tokens'] ?? 0).toInt(),
        totalOutputTokens: (json['total_output_tokens'] ?? 0).toInt(),
      );
}

class MetricsData {
  final MetricsTotals allTime;
  final MetricsTotals today;
  final MetricsTotals thisWeek;
  final MetricsTotals thisMonth;
  final List<Map<String, dynamic>> byHour;
  final List<Map<String, dynamic>> byDow;
  final List<Map<String, dynamic>> byDay;
  final List<Map<String, dynamic>> byMonth;

  const MetricsData({
    this.allTime = const MetricsTotals(),
    this.today = const MetricsTotals(),
    this.thisWeek = const MetricsTotals(),
    this.thisMonth = const MetricsTotals(),
    this.byHour = const [],
    this.byDow = const [],
    this.byDay = const [],
    this.byMonth = const [],
  });

  factory MetricsData.fromJson(Map<String, dynamic> json) {
    final totals = json['totals'] as Map<String, dynamic>? ?? {};
    return MetricsData(
      allTime: MetricsTotals.fromJson(
          totals['all_time'] as Map<String, dynamic>? ?? {}),
      today:
          MetricsTotals.fromJson(totals['today'] as Map<String, dynamic>? ?? {}),
      thisWeek: MetricsTotals.fromJson(
          totals['this_week'] as Map<String, dynamic>? ?? {}),
      thisMonth: MetricsTotals.fromJson(
          totals['this_month'] as Map<String, dynamic>? ?? {}),
      byHour: List<Map<String, dynamic>>.from(json['by_hour'] ?? []),
      byDow: List<Map<String, dynamic>>.from(json['by_dow'] ?? []),
      byDay: List<Map<String, dynamic>>.from(json['by_day'] ?? []),
      byMonth: List<Map<String, dynamic>>.from(json['by_month'] ?? []),
    );
  }
}
