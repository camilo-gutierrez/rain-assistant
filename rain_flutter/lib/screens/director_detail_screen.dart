import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/directors_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/context_editor_sheet.dart';
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

          // ── Context configuration ──
          if (d.requiredContext.isNotEmpty ||
              d.contextWindow.isNotEmpty) ...[
            _ContextConfigSection(
              director: d,
              lang: lang,
              cs: cs,
              onConfigure: () => showContextEditorSheet(context, d),
            ),
            const SizedBox(height: 20),
          ],

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
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      FilledButton.icon(
                        onPressed: s.runningIds.contains(d.id) || d.needsSetup
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
                      if (d.needsSetup)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            L10n.t('directors.runBlocked', lang),
                            style: TextStyle(
                                fontSize: 11, color: cs.onSurfaceVariant),
                            textAlign: TextAlign.center,
                          ),
                        ),
                    ],
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

// ── Context configuration section ──
// Shows a clear setup wizard when fields are missing, or a summary when complete.

class _ContextConfigSection extends StatelessWidget {
  final Director director;
  final String lang;
  final ColorScheme cs;
  final VoidCallback onConfigure;

  const _ContextConfigSection({
    required this.director,
    required this.lang,
    required this.cs,
    required this.onConfigure,
  });

  @override
  Widget build(BuildContext context) {
    final d = director;

    // Separate required user-editable fields from runtime fields
    final requiredFields = d.requiredContext
        .where((f) => f.required && !f.readOnly && !f.autoManaged)
        .toList();
    final optionalFields = d.requiredContext
        .where((f) => !f.required && !f.readOnly && !f.autoManaged)
        .toList();

    final filledRequired = requiredFields
        .where((f) => !d.missingFields.contains(f.key))
        .length;
    final totalRequired = requiredFields.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header row
        Row(
          children: [
            Expanded(
              child: Text(
                L10n.t('directors.contextConfig', lang),
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                  color: cs.onSurface,
                ),
              ),
            ),
            SizedBox(
              height: 32,
              child: FilledButton.tonalIcon(
                onPressed: onConfigure,
                icon: const Icon(Icons.tune, size: 16),
                label: Text(
                  L10n.t('directors.configure', lang),
                  style: const TextStyle(fontSize: 12),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),

        // Setup status card
        if (d.needsSetup)
          _SetupRequiredCard(
            requiredFields: requiredFields,
            missingFields: d.missingFields,
            filledRequired: filledRequired,
            totalRequired: totalRequired,
            lang: lang,
            cs: cs,
            onConfigure: onConfigure,
            contextWindow: d.contextWindow,
          )
        else
          _SetupCompleteCard(
            requiredFields: requiredFields,
            optionalFields: optionalFields,
            lang: lang,
            cs: cs,
            contextWindow: d.contextWindow,
          ),
      ],
    );
  }
}

class _SetupRequiredCard extends StatelessWidget {
  final List<ContextFieldMeta> requiredFields;
  final List<String> missingFields;
  final int filledRequired;
  final int totalRequired;
  final String lang;
  final ColorScheme cs;
  final VoidCallback onConfigure;
  final Map<String, dynamic> contextWindow;

  const _SetupRequiredCard({
    required this.requiredFields,
    required this.missingFields,
    required this.filledRequired,
    required this.totalRequired,
    required this.lang,
    required this.cs,
    required this.onConfigure,
    required this.contextWindow,
  });

  @override
  Widget build(BuildContext context) {
    final progress = totalRequired > 0 ? filledRequired / totalRequired : 0.0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.amber.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.amber.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title row with icon
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.amber.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.checklist_rounded,
                    color: Colors.amber.shade700, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      L10n.t('directors.setupRequired', lang),
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
                        color: Colors.amber.shade700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      L10n.t('directors.setupProgress', lang, {
                        'done': '$filledRequired',
                        'total': '$totalRequired',
                      }),
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: cs.surfaceContainerHighest,
              color: Colors.amber.shade700,
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 16),

          // Checklist of required fields
          ...requiredFields.map((field) {
            final isMissing = missingFields.contains(field.key);
            final label = field.localizedLabel(lang);
            final hint = field.localizedHint(lang);
            final hasFile = field.allowFileAttach;

            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 1),
                    child: Icon(
                      isMissing
                          ? Icons.radio_button_unchecked
                          : Icons.check_circle,
                      size: 18,
                      color: isMissing
                          ? Colors.amber.shade700
                          : Colors.green.shade600,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text(
                                label,
                                style: TextStyle(
                                  fontWeight: FontWeight.w500,
                                  fontSize: 13,
                                  color: isMissing
                                      ? cs.onSurface
                                      : cs.onSurfaceVariant,
                                  decoration: isMissing
                                      ? null
                                      : TextDecoration.lineThrough,
                                ),
                              ),
                            ),
                            if (hasFile) ...[
                              const SizedBox(width: 6),
                              Icon(Icons.attach_file,
                                  size: 14, color: cs.primary),
                            ],
                          ],
                        ),
                        if (isMissing && hint.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(
                              hint,
                              style: TextStyle(
                                fontSize: 11,
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ),
                        if (!isMissing)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(
                              _getPreview(field),
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.green.shade600,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),

          const SizedBox(height: 8),

          // CTA button
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onConfigure,
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: Text(L10n.t('directors.completeSetup', lang)),
              style: FilledButton.styleFrom(
                backgroundColor: Colors.amber.shade700,
                foregroundColor: Colors.white,
                minimumSize: const Size.fromHeight(44),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _getPreview(ContextFieldMeta field) {
    final val = contextWindow[field.key];
    if (val == null) return '';
    final s = val.toString();
    return s.length > 50 ? '${s.substring(0, 50)}...' : s;
  }
}

class _SetupCompleteCard extends StatelessWidget {
  final List<ContextFieldMeta> requiredFields;
  final List<ContextFieldMeta> optionalFields;
  final String lang;
  final ColorScheme cs;
  final Map<String, dynamic> contextWindow;

  const _SetupCompleteCard({
    required this.requiredFields,
    required this.optionalFields,
    required this.lang,
    required this.cs,
    required this.contextWindow,
  });

  @override
  Widget build(BuildContext context) {
    final configuredOptional = optionalFields
        .where((f) {
          final val = contextWindow[f.key];
          return val != null &&
              val.toString().isNotEmpty &&
              val.toString() != '[]';
        })
        .length;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.green.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.green.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.check_circle,
                  color: Colors.green.shade600, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  L10n.t('directors.setupComplete', lang),
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: Colors.green.shade600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '${requiredFields.length} ${L10n.t('directors.requiredFields', lang).toLowerCase()}'
            '${optionalFields.isNotEmpty ? ' · $configuredOptional/${optionalFields.length} ${L10n.t('directors.optionalFields', lang).toLowerCase()}' : ''}',
            style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
          ),
          // Show configured required fields as compact chips
          if (requiredFields.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: requiredFields.map((f) {
                final label = f.localizedLabel(lang);
                return Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: cs.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.check, size: 12, color: Colors.green.shade600),
                      const SizedBox(width: 4),
                      Text(label,
                          style:
                              TextStyle(fontSize: 11, color: cs.onSurfaceVariant)),
                    ],
                  ),
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }
}
