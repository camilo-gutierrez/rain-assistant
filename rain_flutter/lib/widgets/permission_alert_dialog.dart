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

/// Shows a modal dialog for AskUserQuestion when the user is viewing
/// a different agent tab (foreground, different agent).
Future<void> showAskQuestionAlertDialog(
  BuildContext context,
  WidgetRef ref, {
  required String agentId,
  required String agentLabel,
  required String requestId,
  required List<Map<String, dynamic>> questions,
}) async {
  final lang = ref.read(settingsProvider).language;

  // For the dialog, show first question with single-select options
  final firstQ = questions.isNotEmpty ? questions[0] : <String, dynamic>{};
  final questionText = (firstQ['question'] ?? '') as String;
  final options = (firstQ['options'] as List?)
          ?.map((o) => Map<String, dynamic>.from(o))
          .toList() ??
      [];

  final otherController = TextEditingController();
  String? selectedLabel;

  final result = await showDialog<String?>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) {
      final cs = Theme.of(ctx).colorScheme;
      return StatefulBuilder(
        builder: (ctx, setDialogState) {
          return AlertDialog(
            icon: Icon(
              Icons.help_outline,
              color: cs.primary,
              size: 40,
            ),
            title: Text('$agentLabel: ${L10n.t('ask.title', lang)}'),
            content: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 340),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(questionText, style: const TextStyle(fontSize: 14)),
                  if (options.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    ...options.map((opt) {
                      final label = (opt['label'] ?? '') as String;
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: ChoiceChip(
                          label: Text(label),
                          selected: selectedLabel == label,
                          onSelected: (_) {
                            setDialogState(() {
                              selectedLabel = label;
                              otherController.clear();
                            });
                          },
                        ),
                      );
                    }),
                  ],
                  const SizedBox(height: 8),
                  TextField(
                    controller: otherController,
                    decoration: InputDecoration(
                      hintText: L10n.t('ask.otherPlaceholder', lang),
                      isDense: true,
                    ),
                    onChanged: (_) {
                      setDialogState(() => selectedLabel = null);
                    },
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(null),
                child: Text(L10n.t('ask.skip', lang)),
              ),
              FilledButton(
                onPressed: () {
                  final answer = otherController.text.isNotEmpty
                      ? otherController.text
                      : selectedLabel;
                  Navigator.of(ctx).pop(answer);
                },
                child: Text(L10n.t('ask.respond', lang)),
              ),
            ],
          );
        },
      );
    },
  );

  final ws = ref.read(webSocketServiceProvider);
  final agentNotifier = ref.read(agentProvider.notifier);

  if (result == null) {
    // Skipped
    ws.send({
      'type': 'ask_question_response',
      'request_id': requestId,
      'agent_id': agentId,
      'answers': <String, String>{},
    });
    agentNotifier.updateQuestionStatus(
        agentId, requestId, QuestionStatus.skipped);
  } else {
    final answers = {questionText: result};
    ws.send({
      'type': 'ask_question_response',
      'request_id': requestId,
      'agent_id': agentId,
      'answers': answers,
    });
    agentNotifier.updateQuestionStatus(
        agentId, requestId, QuestionStatus.answered, answers);
    agentNotifier.setProcessing(agentId, true);
    agentNotifier.setAgentStatus(agentId, AgentStatus.working);
  }

  otherController.dispose();
}
