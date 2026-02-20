import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../providers/agent_provider.dart';
import 'screenshot_fullscreen.dart';

/// Persistent live display panel showing the last screenshot when in
/// computer_use mode. Sits above the message list and includes display
/// info (resolution, iteration).
class ComputerLiveDisplay extends ConsumerWidget {
  final String lang;
  const ComputerLiveDisplay({super.key, required this.lang});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final agent = ref.watch(agentProvider).activeAgent;
    if (agent == null || agent.mode != AgentMode.computerUse) {
      return const SizedBox.shrink();
    }

    final hasScreenshot =
        agent.lastScreenshot != null && agent.lastScreenshot!.isNotEmpty;
    final displayInfo = agent.displayInfo;

    return Container(
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(
          bottom: BorderSide(
            color: cs.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Info bar: resolution + iteration
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Row(
              children: [
                Icon(Icons.monitor, size: 16, color: cs.primary),
                const SizedBox(width: 6),
                Text(
                  L10n.t('cu.liveDisplay', lang),
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: cs.onSurface,
                  ),
                ),
                const Spacer(),
                if (displayInfo != null) ...[
                  _InfoChip(
                    icon: Icons.aspect_ratio,
                    label:
                        '${displayInfo.screenWidth}x${displayInfo.screenHeight}',
                    cs: cs,
                  ),
                  const SizedBox(width: 8),
                ],
                _InfoChip(
                  icon: Icons.repeat,
                  label: L10n.t('cu.iterationProgress', lang,
                      {'current': '${agent.computerIteration}'}),
                  cs: cs,
                ),
              ],
            ),
          ),
          // Screenshot preview
          if (hasScreenshot)
            GestureDetector(
              onTap: () => ScreenshotFullscreen.show(
                context,
                agent.lastScreenshot!,
                title: L10n.t('cu.liveDisplay', lang),
              ),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 220),
                child: Stack(
                  alignment: Alignment.bottomRight,
                  children: [
                    ClipRRect(
                      child: Image.memory(
                        base64Decode(agent.lastScreenshot!),
                        fit: BoxFit.contain,
                        width: double.infinity,
                        errorBuilder: (_, __, ___) => SizedBox(
                          height: 100,
                          child: Center(
                            child: Icon(Icons.broken_image,
                                size: 32, color: cs.onSurfaceVariant),
                          ),
                        ),
                      ),
                    ),
                    // Expand hint
                    Container(
                      margin: const EdgeInsets.all(8),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black54,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.fullscreen,
                              size: 14, color: Colors.white70),
                          const SizedBox(width: 4),
                          Text(
                            L10n.t('cu.tapToExpand', lang),
                            style: const TextStyle(
                              fontSize: 10,
                              color: Colors.white70,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                L10n.t('cu.noScreenshot', lang),
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
              ),
            ),
        ],
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final ColorScheme cs;

  const _InfoChip({
    required this.icon,
    required this.label,
    required this.cs,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: cs.primaryContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: cs.onPrimaryContainer),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: cs.onPrimaryContainer,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }
}
