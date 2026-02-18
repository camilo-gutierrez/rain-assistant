import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/metrics_provider.dart';

/// Compact badge showing current rate limit status.
/// Taps can navigate to the metrics screen.
class RateLimitBadge extends ConsumerWidget {
  final VoidCallback? onTap;
  const RateLimitBadge({super.key, this.onTap});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final limits = ref.watch(rateLimitsProvider);
    if (!limits.hasData) return const SizedBox.shrink();

    final cs = Theme.of(context).colorScheme;
    final pct = limits.requestsPercent;
    final color = pct < 0.2
        ? cs.error
        : pct < 0.5
            ? Colors.orange
            : Colors.green;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.speed, size: 14, color: color),
            const SizedBox(width: 4),
            Text(
              '${limits.requestsRemaining ?? '?'}/${limits.requestsLimit ?? '?'}',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: color,
                fontFamily: 'monospace',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
