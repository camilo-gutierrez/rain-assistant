import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/conversation.dart';
import '../models/message.dart';
import '../providers/agent_provider.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  List<ConversationMeta>? _conversations;
  bool _loading = true;
  String? _error;
  String? _confirmDeleteId;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/history');
      if (!mounted) return;
      final list = (res.data['conversations'] as List? ?? [])
          .map((e) => ConversationMeta.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() {
        _conversations = list;
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

  Future<void> _saveConversation() async {
    final agentState = ref.read(agentProvider);
    final agent = agentState.activeAgent;
    if (agent == null || agent.messages.isEmpty) return;

    setState(() => _saving = true);

    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final now = DateTime.now().millisecondsSinceEpoch;
      final firstUserMsg = agent.messages
          .whereType<UserMessage>()
          .firstOrNull;
      final preview = firstUserMsg?.text ?? '';
      final label = preview.length > 50
          ? '${preview.substring(0, 50)}...'
          : preview.isEmpty
              ? 'Conversation'
              : preview;

      // Calculate total cost from SystemMessage metrics
      double totalCost = 0;
      for (final m in agent.messages) {
        if (m is SystemMessage) {
          // TODO(audit#7): Parse cost from structured data instead of fragile regex on message text
          final match = RegExp(r'\$(\d+\.\d+)').firstMatch(m.text);
          if (match != null) {
            totalCost += double.tryParse(match.group(1)!) ?? 0;
          }
        }
      }

      await dio.post('/history', data: {
        'id': 'conv_$now',
        'createdAt': now,
        'updatedAt': now,
        'label': label,
        'cwd': agent.cwd ?? '',
        'messageCount': agent.messages.length,
        'preview': preview,
        'totalCost': totalCost,
        'version': 1,
        'agentId': agent.id,
        'sessionId': agent.sessionId ?? '',
        'messages': agent.messages.map((m) => m.toJson()).toList(),
      });

      if (!mounted) return;
      final lang = ref.read(settingsProvider).language;
      showToast(context, L10n.t('toast.saveSuccess', lang),
          type: ToastType.success);
      await _loadHistory();
    } catch (_) {
      if (!mounted) return;
      final lang = ref.read(settingsProvider).language;
      showToast(context, L10n.t('toast.saveFailed', lang),
          type: ToastType.error);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _deleteConversation(String id) async {
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      await dio.delete('/history/$id');
      if (!mounted) return;
      final lang = ref.read(settingsProvider).language;
      showToast(context, L10n.t('toast.deletedConversation', lang),
          type: ToastType.info);
      await _loadHistory();
    } catch (_) {}
  }

  Future<void> _loadConversation(ConversationMeta conv) async {
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/history/${conv.id}');
      if (!mounted) return;

      final data = res.data as Map<String, dynamic>;
      final rawMessages = data['messages'] as List? ?? [];
      final messages =
          rawMessages.map((m) => Message.fromJson(m as Map<String, dynamic>)).toList();

      final agentNotifier = ref.read(agentProvider.notifier);
      final agentId = ref.read(agentProvider).activeAgentId;

      if (agentId.isNotEmpty) {
        agentNotifier.setMessages(agentId, messages);
        agentNotifier.setHistoryLoaded(agentId, true);

        // Set session_id and cwd if available
        final sessionId = data['sessionId'] as String?;
        if (sessionId != null && sessionId.isNotEmpty) {
          agentNotifier.setAgentSessionId(agentId, sessionId);
          // Re-send set_cwd with session_id to resume on backend
          final ws = ref.read(webSocketServiceProvider);
          ws.send({
            'type': 'set_cwd',
            'path': conv.cwd,
            'agent_id': agentId,
            'session_id': sessionId,
          });
        }
      }

      if (mounted) Navigator.of(context).pop();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('history.title', lang)),
        actions: [
          IconButton(
            onPressed: _loadHistory,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _saving ? null : _saveConversation,
        icon: _saving
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.save),
        label: Text(_saving
            ? L10n.t('history.saving', lang)
            : L10n.t('history.saveBtn', lang)),
      ),
      body: _loading
          ? Center(child: Text(L10n.t('history.loading', lang)))
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.error_outline, size: 48, color: cs.error),
                      const SizedBox(height: 16),
                      Text(_error!),
                    ],
                  ),
                )
              : _conversations == null || _conversations!.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.history,
                              size: 48,
                              color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
                          const SizedBox(height: 16),
                          Text(L10n.t('history.empty', lang),
                              style: TextStyle(color: cs.onSurfaceVariant)),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.only(bottom: 80),
                      itemCount: _conversations!.length,
                      itemBuilder: (context, index) {
                        final conv = _conversations![index];
                        return _ConversationTile(
                          conversation: conv,
                          lang: lang,
                          confirmDelete: _confirmDeleteId == conv.id,
                          onTap: () => _loadConversation(conv),
                          onDelete: () {
                            if (_confirmDeleteId == conv.id) {
                              _deleteConversation(conv.id);
                              setState(() => _confirmDeleteId = null);
                            } else {
                              setState(() => _confirmDeleteId = conv.id);
                            }
                          },
                        );
                      },
                    ),
    );
  }
}

class _ConversationTile extends StatelessWidget {
  final ConversationMeta conversation;
  final String lang;
  final bool confirmDelete;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  const _ConversationTile({
    required this.conversation,
    required this.lang,
    required this.confirmDelete,
    required this.onTap,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final date = DateTime.fromMillisecondsSinceEpoch(conversation.updatedAt);
    final dateStr =
        '${date.day}/${date.month}/${date.year} ${date.hour}:${date.minute.toString().padLeft(2, '0')}';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      conversation.label,
                      style: const TextStyle(
                          fontWeight: FontWeight.w600, fontSize: 14),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  TextButton(
                    onPressed: onDelete,
                    style: TextButton.styleFrom(
                      foregroundColor: confirmDelete ? cs.error : cs.onSurfaceVariant,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: Text(
                      confirmDelete
                          ? L10n.t('history.confirmDelete', lang)
                          : L10n.t('history.delete', lang),
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                conversation.preview,
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.folder_outlined,
                      size: 14, color: cs.onSurfaceVariant),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      conversation.cwd,
                      style: TextStyle(
                        fontSize: 11,
                        color: cs.onSurfaceVariant,
                        fontFamily: 'monospace',
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    dateStr,
                    style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '\$${conversation.totalCost.toStringAsFixed(4)}',
                    style: TextStyle(
                      fontSize: 11,
                      color: cs.primary,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
