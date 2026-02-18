import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../providers/agent_provider.dart';
import '../providers/connection_provider.dart';

/// Toggle between coding and computer_use mode for the active agent.
class ModeSwitcher extends ConsumerWidget {
  final String lang;
  const ModeSwitcher({super.key, required this.lang});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final agentState = ref.watch(agentProvider);
    final agent = agentState.activeAgent;
    if (agent == null) return const SizedBox.shrink();

    final isCoding = agent.mode == AgentMode.coding;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SegmentedButton<AgentMode>(
          segments: [
            ButtonSegment(
              value: AgentMode.coding,
              label: Text(L10n.t('cu.modeCoding', lang)),
              icon: const Icon(Icons.code, size: 16),
            ),
            ButtonSegment(
              value: AgentMode.computerUse,
              label: Text(L10n.t('cu.modeComputer', lang)),
              icon: const Icon(Icons.computer, size: 16),
            ),
          ],
          selected: {agent.mode},
          onSelectionChanged: (s) {
            final mode = s.first;
            final ws = ref.read(webSocketServiceProvider);
            ws.send({
              'type': 'set_mode',
              'agent_id': agent.id,
              'mode': mode == AgentMode.computerUse ? 'computer_use' : 'coding',
            });
          },
          style: SegmentedButton.styleFrom(
            visualDensity: VisualDensity.compact,
            textStyle: const TextStyle(fontSize: 12),
          ),
        ),
        // Emergency stop button (only in computer_use mode while processing)
        if (!isCoding && agent.isProcessing) ...[
          const SizedBox(width: 8),
          FilledButton.icon(
            onPressed: () {
              final ws = ref.read(webSocketServiceProvider);
              ws.send({
                'type': 'emergency_stop',
                'agent_id': agent.id,
              });
            },
            icon: const Icon(Icons.emergency, size: 16),
            label: Text(L10n.t('cu.emergencyStop', lang),
                style: const TextStyle(fontSize: 11)),
            style: FilledButton.styleFrom(
              backgroundColor: cs.error,
              foregroundColor: cs.onError,
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              minimumSize: Size.zero,
            ),
          ),
        ],
      ],
    );
  }
}
