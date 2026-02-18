import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/metrics.dart';
import '../models/provider_info.dart';
import '../models/rate_limits.dart';
import '../providers/connection_provider.dart';
import '../providers/metrics_provider.dart';
import '../providers/settings_provider.dart';

class MetricsScreen extends ConsumerStatefulWidget {
  const MetricsScreen({super.key});

  @override
  ConsumerState<MetricsScreen> createState() => _MetricsScreenState();
}

class _MetricsScreenState extends ConsumerState<MetricsScreen> {
  MetricsData? _metrics;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadMetrics();
  }

  Future<void> _loadMetrics() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/metrics');
      if (!mounted) return;
      setState(() {
        _metrics = MetricsData.fromJson(res.data);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
    final rateLimits = ref.watch(rateLimitsProvider);
    final currentModel = ref.watch(currentModelProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('metrics.title', lang)),
        actions: [
          IconButton(
            onPressed: _loadMetrics,
            icon: const Icon(Icons.refresh),
            tooltip: L10n.t('metrics.refresh', lang),
          ),
        ],
      ),
      body: _loading
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const CircularProgressIndicator(),
                  const SizedBox(height: 16),
                  Text(L10n.t('metrics.loading', lang)),
                ],
              ),
            )
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.error_outline, size: 48, color: cs.error),
                      const SizedBox(height: 16),
                      Text(_error!, style: TextStyle(color: cs.error)),
                      const SizedBox(height: 16),
                      FilledButton.tonal(
                        onPressed: _loadMetrics,
                        child: Text(L10n.t('metrics.refresh', lang)),
                      ),
                    ],
                  ),
                )
              : _metrics == null
                  ? Center(child: Text(L10n.t('metrics.noData', lang)))
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        // ── Summary cards ──
                        _buildSummaryCards(cs, lang),
                        const SizedBox(height: 16),

                        // ── Period tabs ──
                        _PeriodTabs(metrics: _metrics!, lang: lang),
                        const SizedBox(height: 16),

                        // ── Rate limits ──
                        if (rateLimits.hasData) ...[
                          _buildRateLimitsSection(cs, lang, rateLimits, currentModel),
                          const SizedBox(height: 16),
                        ],

                        // ── By hour ──
                        if (_metrics!.byHour.isNotEmpty) ...[
                          _buildBarSection(
                            cs,
                            L10n.t('metrics.usageByHour', lang),
                            _metrics!.byHour,
                            (e) => '${e['hour']}h',
                            (e) => (e['cost'] ?? 0).toDouble(),
                          ),
                          const SizedBox(height: 16),
                        ],

                        // ── By day of week ──
                        if (_metrics!.byDow.isNotEmpty) ...[
                          _buildBarSection(
                            cs,
                            L10n.t('metrics.usageByDow', lang),
                            _metrics!.byDow,
                            (e) => L10n.t('dow.${e['name']}', lang),
                            (e) => (e['cost'] ?? 0).toDouble(),
                          ),
                          const SizedBox(height: 16),
                        ],

                        // ── Daily spend ──
                        if (_metrics!.byDay.isNotEmpty) ...[
                          _buildBarSection(
                            cs,
                            L10n.t('metrics.dailySpend', lang),
                            _metrics!.byDay.reversed.take(30).toList().reversed.toList(),
                            (e) {
                              final day = e['day'] as String? ?? '';
                              return day.length >= 10 ? day.substring(5) : day;
                            },
                            (e) => (e['cost'] ?? 0).toDouble(),
                          ),
                          const SizedBox(height: 16),
                        ],

                        // ── Monthly spend ──
                        if (_metrics!.byMonth.isNotEmpty) ...[
                          _buildBarSection(
                            cs,
                            L10n.t('metrics.monthlySpend', lang),
                            _metrics!.byMonth,
                            (e) {
                              final m = e['month'] as String? ?? '';
                              if (m.length >= 7) {
                                final monthIdx = int.tryParse(m.substring(5)) ?? 1;
                                return L10n.t('month.${monthIdx - 1}', lang);
                              }
                              return m;
                            },
                            (e) => (e['cost'] ?? 0).toDouble(),
                          ),
                        ],

                        const SizedBox(height: 32),
                      ],
                    ),
    );
  }

  Widget _buildSummaryCards(ColorScheme cs, String lang) {
    final t = _metrics!.allTime;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        _StatCard(
          icon: Icons.attach_money,
          label: L10n.t('metrics.totalSpent', lang),
          value: '\$${t.cost.toStringAsFixed(2)}',
          color: cs.primary,
        ),
        _StatCard(
          icon: Icons.chat_bubble_outline,
          label: L10n.t('metrics.sessions', lang),
          value: '${t.sessions}',
          color: cs.tertiary,
        ),
        _StatCard(
          icon: Icons.timer_outlined,
          label: L10n.t('metrics.avgDuration', lang),
          value: '${(t.avgDurationMs / 1000).toStringAsFixed(1)}s',
          color: cs.secondary,
        ),
        _StatCard(
          icon: Icons.repeat,
          label: L10n.t('metrics.totalTurns', lang),
          value: '${t.totalTurns}',
          color: Colors.orange,
        ),
      ],
    );
  }

  Widget _buildRateLimitsSection(
    ColorScheme cs,
    String lang,
    RateLimits limits,
    String currentModel,
  ) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.speed, size: 18, color: cs.primary),
                const SizedBox(width: 8),
                Text(
                  L10n.t('metrics.rateLimits', lang),
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 14),
                ),
              ],
            ),
            if (currentModel.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                '${L10n.t('metrics.model', lang)}: ${formatModelName(currentModel)}',
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
              ),
            ],
            const SizedBox(height: 12),
            _RateLimitBar(
              label: 'Requests',
              remaining: limits.requestsRemaining,
              total: limits.requestsLimit,
              color: cs.primary,
            ),
            const SizedBox(height: 8),
            _RateLimitBar(
              label: L10n.t('metrics.inputTokens', lang),
              remaining: limits.inputTokensRemaining,
              total: limits.inputTokensLimit,
              color: cs.tertiary,
            ),
            const SizedBox(height: 8),
            _RateLimitBar(
              label: L10n.t('metrics.outputTokens', lang),
              remaining: limits.outputTokensRemaining,
              total: limits.outputTokensLimit,
              color: cs.secondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBarSection(
    ColorScheme cs,
    String title,
    List<Map<String, dynamic>> data,
    String Function(Map<String, dynamic>) labelFn,
    double Function(Map<String, dynamic>) valueFn,
  ) {
    final maxVal = data.fold<double>(
      0,
      (prev, e) => valueFn(e) > prev ? valueFn(e) : prev,
    );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style:
                    const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 12),
            ...data.map((e) {
              final val = valueFn(e);
              final ratio = maxVal > 0 ? val / maxVal : 0.0;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    SizedBox(
                      width: 48,
                      child: Text(
                        labelFn(e),
                        style: TextStyle(
                            fontSize: 11, color: cs.onSurfaceVariant),
                      ),
                    ),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: LinearProgressIndicator(
                          value: ratio,
                          minHeight: 14,
                          backgroundColor:
                              cs.surfaceContainerHighest,
                          color: cs.primary,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 52,
                      child: Text(
                        '\$${val.toStringAsFixed(2)}',
                        style: TextStyle(
                            fontSize: 11,
                            color: cs.onSurfaceVariant,
                            fontFamily: 'monospace'),
                        textAlign: TextAlign.right,
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}

// ── Period tabs (Today / Week / Month) ──

class _PeriodTabs extends StatefulWidget {
  final MetricsData metrics;
  final String lang;
  const _PeriodTabs({required this.metrics, required this.lang});

  @override
  State<_PeriodTabs> createState() => _PeriodTabsState();
}

class _PeriodTabsState extends State<_PeriodTabs> {
  int _selected = 0;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final labels = [
      L10n.t('metrics.today', widget.lang),
      L10n.t('metrics.week', widget.lang),
      L10n.t('metrics.month', widget.lang),
    ];
    final totals = [
      widget.metrics.today,
      widget.metrics.thisWeek,
      widget.metrics.thisMonth,
    ];
    final t = totals[_selected];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            SegmentedButton<int>(
              segments: List.generate(
                3,
                (i) => ButtonSegment(value: i, label: Text(labels[i])),
              ),
              selected: {_selected},
              onSelectionChanged: (s) => setState(() => _selected = s.first),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _MiniStat(
                    label: L10n.t('metrics.totalSpent', widget.lang),
                    value: '\$${t.cost.toStringAsFixed(2)}',
                    color: cs.primary,
                  ),
                ),
                Expanded(
                  child: _MiniStat(
                    label: L10n.t('metrics.sessions', widget.lang),
                    value: '${t.sessions}',
                    color: cs.tertiary,
                  ),
                ),
                Expanded(
                  child: _MiniStat(
                    label: L10n.t('metrics.avgCost', widget.lang),
                    value: '\$${t.avgCost.toStringAsFixed(4)}',
                    color: cs.secondary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _MiniStat(
                    label: L10n.t('metrics.inputTokens', widget.lang),
                    value: _formatTokens(t.totalInputTokens),
                    color: Colors.blue,
                  ),
                ),
                Expanded(
                  child: _MiniStat(
                    label: L10n.t('metrics.outputTokens', widget.lang),
                    value: _formatTokens(t.totalOutputTokens),
                    color: Colors.orange,
                  ),
                ),
                Expanded(
                  child: _MiniStat(
                    label: L10n.t('metrics.totalTurns', widget.lang),
                    value: '${t.totalTurns}',
                    color: Colors.green,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _formatTokens(int tokens) {
    if (tokens >= 1000000) return '${(tokens / 1000000).toStringAsFixed(1)}M';
    if (tokens >= 1000) return '${(tokens / 1000).toStringAsFixed(1)}K';
    return '$tokens';
  }
}

// ── Small stat widget ──

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _MiniStat(
      {required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
            fontFamily: 'monospace',
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}

// ── Stat card ──

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return SizedBox(
      width: (MediaQuery.of(context).size.width - 48) / 2,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 20, color: color),
              const SizedBox(height: 8),
              Text(
                value,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: cs.onSurface,
                  fontFamily: 'monospace',
                ),
              ),
              Text(
                label,
                style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Rate limit bar ──

class _RateLimitBar extends StatelessWidget {
  final String label;
  final int? remaining;
  final int? total;
  final Color color;
  const _RateLimitBar({
    required this.label,
    required this.remaining,
    required this.total,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ratio =
        (total != null && total! > 0 && remaining != null)
            ? remaining! / total!
            : 1.0;
    final barColor = ratio < 0.2
        ? cs.error
        : ratio < 0.5
            ? Colors.orange
            : color;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label,
                style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant)),
            Text(
              '${remaining ?? '?'} / ${total ?? '?'}',
              style: TextStyle(
                  fontSize: 11,
                  color: cs.onSurfaceVariant,
                  fontFamily: 'monospace'),
            ),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: ratio,
            minHeight: 8,
            backgroundColor: cs.surfaceContainerHighest,
            color: barColor,
          ),
        ),
      ],
    );
  }
}
