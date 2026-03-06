import 'package:flutter/material.dart';
import '../app/l10n.dart';

/// Visual data for a permission level.
class _PermLevelInfo {
  final String id;
  final String labelKey;
  final String descKey;
  final IconData icon;
  final Color color;
  final Color bgColor;

  const _PermLevelInfo({
    required this.id,
    required this.labelKey,
    required this.descKey,
    required this.icon,
    required this.color,
    required this.bgColor,
  });
}

const _levels = [
  _PermLevelInfo(
    id: 'green',
    labelKey: 'directors.permGreen',
    descKey: 'directors.permGreenDesc',
    icon: Icons.check_circle_outline,
    color: Color(0xFF43A047),
    bgColor: Color(0x1A43A047),
  ),
  _PermLevelInfo(
    id: 'yellow',
    labelKey: 'directors.permYellow',
    descKey: 'directors.permYellowDesc',
    icon: Icons.warning_amber_rounded,
    color: Color(0xFFF9A825),
    bgColor: Color(0x1AF9A825),
  ),
  _PermLevelInfo(
    id: 'red',
    labelKey: 'directors.permRed',
    descKey: 'directors.permRedDesc',
    icon: Icons.shield_outlined,
    color: Color(0xFFE53935),
    bgColor: Color(0x1AE53935),
  ),
];

/// Returns the color for a permission level string.
Color permissionLevelColor(String level) {
  return switch (level) {
    'green' => const Color(0xFF43A047),
    'yellow' => const Color(0xFFF9A825),
    'red' => const Color(0xFFE53935),
    _ => const Color(0xFF43A047),
  };
}

/// Returns the icon for a permission level string.
IconData permissionLevelIcon(String level) {
  return switch (level) {
    'green' => Icons.check_circle_outline,
    'yellow' => Icons.warning_amber_rounded,
    'red' => Icons.shield_outlined,
    _ => Icons.check_circle_outline,
  };
}

// ──────────────────────────────────────────────────────────────────────────────
// Compact badge — for director cards and info chips
// ──────────────────────────────────────────────────────────────────────────────

class PermissionLevelBadge extends StatelessWidget {
  final String level;
  final String lang;
  final double fontSize;

  const PermissionLevelBadge({
    super.key,
    required this.level,
    required this.lang,
    this.fontSize = 10,
  });

  @override
  Widget build(BuildContext context) {
    final color = permissionLevelColor(level);
    final icon = permissionLevelIcon(level);
    final label = L10n.t('directors.perm${level[0].toUpperCase()}${level.substring(1)}', lang);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3), width: 0.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: fontSize + 2, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: fontSize,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// Full selector — segmented pill selector for director detail / edit
// ──────────────────────────────────────────────────────────────────────────────

class PermissionLevelSelector extends StatelessWidget {
  final String currentLevel;
  final String lang;
  final ValueChanged<String> onChanged;
  final bool enabled;

  const PermissionLevelSelector({
    super.key,
    required this.currentLevel,
    required this.lang,
    required this.onChanged,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Label
        Text(
          L10n.t('directors.permLevelLabel', lang),
          style: TextStyle(
            fontWeight: FontWeight.w600,
            fontSize: 14,
            color: cs.onSurface,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          L10n.t('directors.permLevelHint', lang),
          style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
        ),
        const SizedBox(height: 12),

        // Selector cards
        ..._levels.map((info) {
          final selected = currentLevel == info.id;
          final color = info.color;
          final label = L10n.t(info.labelKey, lang);
          final desc = L10n.t(info.descKey, lang);

          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Material(
              color: selected
                  ? color.withValues(alpha: 0.10)
                  : cs.surfaceContainerHighest.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(14),
              child: InkWell(
                onTap: enabled ? () => onChanged(info.id) : null,
                borderRadius: BorderRadius.circular(14),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  curve: Curves.easeInOut,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: selected
                          ? color.withValues(alpha: 0.6)
                          : cs.outlineVariant.withValues(alpha: 0.3),
                      width: selected ? 1.5 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      // Radio-style indicator
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        width: 22,
                        height: 22,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: selected ? color : cs.outlineVariant,
                            width: selected ? 2 : 1.5,
                          ),
                          color: selected
                              ? color.withValues(alpha: 0.15)
                              : Colors.transparent,
                        ),
                        child: selected
                            ? Center(
                                child: Container(
                                  width: 10,
                                  height: 10,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: color,
                                  ),
                                ),
                              )
                            : null,
                      ),
                      const SizedBox(width: 12),

                      // Icon
                      Icon(info.icon, size: 22, color: selected ? color : cs.onSurfaceVariant),
                      const SizedBox(width: 12),

                      // Text
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              label,
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 14,
                                color: selected ? color : cs.onSurface,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              desc,
                              style: TextStyle(
                                fontSize: 12,
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        }),
      ],
    );
  }
}
