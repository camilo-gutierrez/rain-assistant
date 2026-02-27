import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/directors_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class DirectorDetailScreen extends ConsumerStatefulWidget {
  final String directorId;

  const DirectorDetailScreen({super.key, required this.directorId});

  @override
  ConsumerState<DirectorDetailScreen> createState() =>
      _DirectorDetailScreenState();
}

class _DirectorDetailScreenState extends ConsumerState<DirectorDetailScreen> {
  List<InboxItem>? _relatedInbox;

  @override
  void initState() {
    super.initState();
    _loadRelatedInbox();
  }

  Future<void> _loadRelatedInbox() async {
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.get('/directors/inbox',
          queryParameters: {'director_id': widget.directorId, 'limit': '5'});
      if (!mounted) return;
      final list = (res.data['items'] as List? ?? [])
          .map((e) => InboxItem.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() => _relatedInbox = list);
    } catch (_) {}
  }

  Future<void> _runNow(Director d) async {
    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final ok = await ref.read(directorsProvider.notifier).runNow(dio, d);
    if (mounted && ok) {
      showToast(context, L10n.t('directors.running', lang),
          type: ToastType.success);
    }
  }

  Future<void> _toggleEnabled(Director d) async {
    final dio = ref.read(authServiceProvider).authenticatedDio;
    await ref.read(directorsProvider.notifier).toggleEnabled(dio, d);
  }

  Future<void> _deleteDirector(Director d) async {
    final lang = ref.read(settingsProvider).language;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(L10n.t('directors.delete', lang)),
        content: Text(
            L10n.t('directors.deleteConfirm', lang, {'name': d.name})),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(L10n.t('agent.cancel', lang)),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(L10n.t('directors.delete', lang)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final dio = ref.read(authServiceProvider).authenticatedDio;
    final ok =
        await ref.read(directorsProvider.notifier).deleteDirector(dio, d);
    if (ok && mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
    final s = ref.watch(directorsProvider);

    final director =
        s.directors.where((d) => d.id == widget.directorId).firstOrNull;

    if (director == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final d = director;

    return Scaffold(
      appBar: AppBar(
        title: Text('${d.emoji} ${d.name}'),
        actions: [
          Switch(value: d.enabled, onChanged: (_) => _toggleEnabled(d)),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Info section ──
          if (d.description.isNotEmpty) ...[
            Text(d.description,
                style: TextStyle(fontSize: 14, color: cs.onSurfaceVariant)),
            const SizedBox(height: 12),
          ],

          // Info chips
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _InfoChip(
                icon: Icons.schedule,
                label: d.schedule ?? L10n.t('directors.manual', lang),
                cs: cs,
              ),
              _InfoChip(
                icon: Icons.shield_outlined,
                label:
                    '${L10n.t('directors.permLevel', lang)}: ${d.permissionLevel}',
                cs: cs,
              ),
              if (d.canDelegate)
                _InfoChip(
                  icon: Icons.call_split,
                  label: L10n.t('directors.canDelegate', lang),
                  cs: cs,
                ),
              if (d.nextRun != null)
                _InfoChip(
                  icon: Icons.update,
                  label:
                      '${L10n.t('directors.nextRun', lang)}: ${_formatTimestamp(d.nextRun!)}',
                  cs: cs,
                ),
            ],
          ),
          const SizedBox(height: 16),

          // ── Stats row ──
          Row(
            children: [
              _StatTile(
                label: L10n.t('directors.runs', lang, {'n': '${d.runCount}'}),
                icon: Icons.play_arrow,
                cs: cs,
              ),
              const SizedBox(width: 16),
              _StatTile(
                label: '\$${d.totalCost.toStringAsFixed(4)}',
                icon: Icons.attach_money,
                cs: cs,
              ),
            ],
          ),
          const SizedBox(height: 16),

          // ── Role prompt ──
          Text(L10n.t('directors.rolePrompt', lang),
              style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                  color: cs.onSurface)),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            constraints: const BoxConstraints(maxHeight: 200),
            decoration: BoxDecoration(
              color: cs.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(12),
            ),
            child: SingleChildScrollView(
              child: Text(d.rolePrompt,
                  style: TextStyle(
                    fontSize: 12,
                    fontFamily: 'monospace',
                    color: cs.onSurfaceVariant,
                  )),
            ),
          ),
          const SizedBox(height: 20),

          // ── Last run result ──
          Text(L10n.t('directors.lastResult', lang),
              style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                  color: cs.onSurface)),
          const SizedBox(height: 8),
          if (d.lastRun != null) ...[
            Row(
              children: [
                Icon(Icons.schedule, size: 14, color: cs.onSurfaceVariant),
                const SizedBox(width: 4),
                Text(
                  '${L10n.t('directors.lastRun', lang)}: ${_formatTimestamp(d.lastRun!)}',
                  style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
          if (d.lastResult != null && d.lastResult!.isNotEmpty)
            Container(
              width: double.infinity,
              constraints: const BoxConstraints(maxHeight: 300),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: cs.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: SingleChildScrollView(
                child: MarkdownBody(
                  data: d.lastResult!,
                  selectable: true,
                  styleSheet: MarkdownStyleSheet(
                    p: TextStyle(fontSize: 13, color: cs.onSurface),
                    code: TextStyle(
                      fontSize: 12,
                      fontFamily: 'monospace',
                      color: cs.primary,
                      backgroundColor: cs.surfaceContainerHighest,
                    ),
                  ),
                ),
              ),
            )
          else
            Text(L10n.t('directors.noResult', lang),
                style: TextStyle(
                    fontSize: 13,
                    fontStyle: FontStyle.italic,
                    color: cs.onSurfaceVariant)),

          // ── Last error ──
          if (d.lastError != null && d.lastError!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: cs.errorContainer.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.error_outline, size: 16, color: cs.error),
                      const SizedBox(width: 6),
                      Text(L10n.t('directors.lastError', lang),
                          style: TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                              color: cs.error)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(d.lastError!,
                      style: TextStyle(fontSize: 12, color: cs.onSurface)),
                ],
              ),
            ),
          ],
          const SizedBox(height: 20),

          // ── Related inbox items ──
          if (_relatedInbox != null && _relatedInbox!.isNotEmpty) ...[
            Text(L10n.t('directors.relatedInbox', lang),
                style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: cs.onSurface)),
            const SizedBox(height: 8),
            ...(_relatedInbox!.map((item) => Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                        color: cs.outlineVariant.withValues(alpha: 0.3)),
                  ),
                  child: ListTile(
                    dense: true,
                    leading: Icon(
                      _contentTypeIcon(item.contentType),
                      size: 20,
                      color: cs.primary,
                    ),
                    title: Text(item.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 13)),
                    subtitle: Text(
                      '${item.status} • ${_formatTimestamp(item.createdAt)}',
                      style: TextStyle(
                          fontSize: 11, color: cs.onSurfaceVariant),
                    ),
                  ),
                ))),
            const SizedBox(height: 20),
          ],

          // ── Action buttons ──
          Row(
            children: [
              if (d.enabled)
                Expanded(
                  child: FilledButton.icon(
                    onPressed: s.runningIds.contains(d.id)
                        ? null
                        : () => _runNow(d),
                    icon: s.runningIds.contains(d.id)
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child:
                                CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.play_arrow),
                    label: Text(L10n.t('directors.runNow', lang)),
                  ),
                ),
              if (d.enabled) const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _deleteDirector(d),
                  icon: Icon(Icons.delete_outline, color: cs.error),
                  label: Text(L10n.t('directors.delete', lang),
                      style: TextStyle(color: cs.error)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  String _formatTimestamp(double ts) {
    final dt = DateTime.fromMillisecondsSinceEpoch((ts * 1000).toInt());
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  IconData _contentTypeIcon(String type) {
    return switch (type) {
      'report' => Icons.description_outlined,
      'draft' => Icons.edit_note,
      'analysis' => Icons.analytics_outlined,
      'code' => Icons.code,
      'notification' => Icons.notifications_outlined,
      _ => Icons.article_outlined,
    };
  }
}

// ── Helper widgets ──

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final ColorScheme cs;

  const _InfoChip(
      {required this.icon, required this.label, required this.cs});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: cs.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(label,
              style:
                  TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
        ],
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  final String label;
  final IconData icon;
  final ColorScheme cs;

  const _StatTile(
      {required this.label, required this.icon, required this.cs});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: cs.onSurfaceVariant),
        const SizedBox(width: 6),
        Text(label,
            style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant)),
      ],
    );
  }
}
