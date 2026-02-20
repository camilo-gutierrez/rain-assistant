import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../models/message.dart';
import '../providers/agent_provider.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';

/// Shows a modal dialog for permission requests when the user is in
/// the foreground but viewing a different agent tab.
Future<void> showPermissionAlertDialog(
  BuildContext context,
  WidgetRef ref, {
  required String agentId,
  required String agentLabel,
  required String tool,
  required String requestId,
  required PermissionLevel level,
}) async {
  final lang = ref.read(settingsProvider).language;
  final isRed = level == PermissionLevel.red;
  final pinController = TextEditingController();

  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) {
      final cs = Theme.of(ctx).colorScheme;
      return AlertDialog(
        icon: Icon(
          isRed ? Icons.gpp_bad : Icons.shield_outlined,
          color: isRed ? cs.error : cs.tertiary,
          size: 40,
        ),
        title: Text('$agentLabel: ${L10n.t('perm.requestTitle', lang)}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              tool,
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontFamily: 'monospace',
                color: cs.onSurfaceVariant,
              ),
            ),
            if (isRed) ...[
              const SizedBox(height: 16),
              TextField(
                controller: pinController,
                obscureText: true,
                decoration: InputDecoration(
                  hintText: L10n.t('perm.enterPin', lang),
                  prefixIcon: Icon(Icons.lock_outline, color: cs.error),
                ),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(L10n.t('perm.deny', lang)),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: isRed ? cs.error : cs.primary,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(L10n.t('perm.approve', lang)),
          ),
        ],
      );
    },
  );

  if (result == null) return;

  final ws = ref.read(webSocketServiceProvider);
  final payload = <String, dynamic>{
    'type': 'permission_response',
    'request_id': requestId,
    'agent_id': agentId,
    'approved': result,
  };

  if (isRed && result) {
    payload['pin'] = pinController.text;
  }

  ws.send(payload);

  final agentNotifier = ref.read(agentProvider.notifier);
  agentNotifier.updatePermissionStatus(
    agentId,
    requestId,
    result ? PermissionStatus.approved : PermissionStatus.denied,
  );

  if (result) {
    agentNotifier.setProcessing(agentId, true);
    agentNotifier.setAgentStatus(agentId, AgentStatus.working);
  }

  pinController.dispose();
}
