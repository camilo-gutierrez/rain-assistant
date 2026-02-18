import 'dart:convert';
import 'package:flutter/material.dart';
import '../app/l10n.dart';
import '../models/message.dart';

/// Displays a computer use action (click, type, scroll, etc.).
class ComputerActionBlock extends StatelessWidget {
  final ComputerActionMessage message;
  final String lang;
  const ComputerActionBlock({
    super.key,
    required this.message,
    required this.lang,
  });

  IconData _actionIcon(String action) {
    return switch (action) {
      'left_click' || 'right_click' || 'double_click' => Icons.mouse,
      'type' => Icons.keyboard,
      'scroll' => Icons.swap_vert,
      'key' => Icons.keyboard_alt_outlined,
      'screenshot' => Icons.screenshot_monitor,
      _ => Icons.computer,
    };
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final inputJson =
        const JsonEncoder.withIndent('  ').convert(message.input);

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.85,
        ),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: cs.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          dense: true,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading: Icon(
            _actionIcon(message.action),
            size: 18,
            color: cs.tertiary,
          ),
          title: Text(
            '${L10n.t('cu.iteration', lang)} ${message.iteration}: ${message.action}',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: cs.onSurface,
            ),
          ),
          subtitle: message.description.isNotEmpty
              ? Text(
                  message.description,
                  style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                )
              : null,
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: cs.surfaceContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                inputJson,
                style: TextStyle(
                  fontSize: 12,
                  fontFamily: 'monospace',
                  color: cs.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
