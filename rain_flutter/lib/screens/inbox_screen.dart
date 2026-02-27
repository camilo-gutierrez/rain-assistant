import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/directors_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class InboxScreen extends ConsumerStatefulWidget {
  const InboxScreen({super.key});

  @override
  ConsumerState<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends ConsumerState<InboxScreen> {
  String _filter = 'all';

  @override
  void initState() {
    super.initState();
    _loadInbox();
  }

  Future<void> _loadInbox() async {
    final dio = ref.read(authServiceProvider).authenticatedDio;
    await ref
        .read(directorsProvider.notifier)
        .loadInbox(dio, filter: _filter);
  }

  Future<void> _updateStatus(InboxItem item, String newStatus,
      {String? comment}) async {
    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final ok = await ref
        .read(directorsProvider.notifier)
        .updateInboxStatus(dio, item, newStatus, comment: comment);
    if (!mounted) return;
    if (ok) {
      showToast(
        context,
        newStatus == 'approved'
            ? L10n.t('inbox.approve', lang)
            : newStatus == 'rejected'
                ? L10n.t('inbox.reject', lang)
                : L10n.t('inbox.archive', lang),
        type: ToastType.success,
      );
      await _loadInbox();
    } else {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  Future<void> _markAsRead(InboxItem item) async {
    if (item.status != 'unread') return;
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.patch('/directors/inbox/${item.id}',
          data: {'status': 'read'});
      if (!mounted) return;
      ref.read(directorsProvider.notifier).markAsRead(item.id);
    } catch (_) {}
  }

  void _setFilter(String filter) {
    if (_filter == filter) return;
    setState(() => _filter = filter);
    _loadInbox();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
    final s = ref.watch(directorsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(L10n.t('inbox.title', lang)),
            if (s.unreadCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: cs.primary,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${s.unreadCount}',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: cs.onPrimary,
                  ),
                ),
              ),
            ],
          ],
        ),
        actions: [
          IconButton(
            onPressed: _loadInbox,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter chips
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                _FilterChip(
                  label: L10n.t('inbox.all', lang),
                  selected: _filter == 'all',
                  onTap: () => _setFilter('all'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: L10n.t('inbox.unread', lang),
                  selected: _filter == 'unread',
                  onTap: () => _setFilter('unread'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: L10n.t('inbox.approved', lang),
                  selected: _filter == 'approved',
                  onTap: () => _setFilter('approved'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: L10n.t('inbox.archived', lang),
                  selected: _filter == 'archived',
                  onTap: () => _setFilter('archived'),
                ),
              ],
            ),
          ),
          Expanded(child: _buildContent(cs, lang, s)),
        ],
      ),
    );
  }

  Widget _buildContent(ColorScheme cs, String lang, DirectorsState s) {
    if (s.inboxLoading && s.inboxItems.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (s.inboxError != null && s.inboxItems.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: cs.error),
            const SizedBox(height: 16),
            Text(s.inboxError!,
                textAlign: TextAlign.center,
                style: TextStyle(color: cs.onSurfaceVariant)),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _loadInbox,
              icon: const Icon(Icons.refresh),
              label: Text(L10n.t('metrics.refresh', lang)),
            ),
          ],
        ),
      );
    }
    if (s.inboxItems.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.inbox_outlined,
                size: 48,
                color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(L10n.t('inbox.empty', lang),
                style: TextStyle(color: cs.onSurfaceVariant)),
            const SizedBox(height: 4),
            Text(L10n.t('inbox.emptyHint', lang),
                style: TextStyle(
                    fontSize: 12,
                    color: cs.onSurfaceVariant.withValues(alpha: 0.6))),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadInbox,
      child: ListView.separated(
        padding: const EdgeInsets.only(top: 4, bottom: 16),
        itemCount: s.inboxItems.length,
        separatorBuilder: (_, __) => const SizedBox(height: 4),
        itemBuilder: (_, i) => _InboxCard(
          item: s.inboxItems[i],
          lang: lang,
          onMarkRead: () => _markAsRead(s.inboxItems[i]),
          onApprove: () => _updateStatus(s.inboxItems[i], 'approved'),
          onReject: () => _updateStatus(s.inboxItems[i], 'rejected'),
          onArchive: () => _updateStatus(s.inboxItems[i], 'archived'),
          onComment: (c) =>
              _updateStatus(s.inboxItems[i], s.inboxItems[i].status, comment: c),
        ),
      ),
    );
  }
}

// ── Filter chip ──

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? cs.primary : cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
            color: selected ? cs.onPrimary : cs.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

// ── Inbox card ──

class _InboxCard extends StatefulWidget {
  final InboxItem item;
  final String lang;
  final VoidCallback onMarkRead;
  final VoidCallback onApprove;
  final VoidCallback onReject;
  final VoidCallback onArchive;
  final ValueChanged<String> onComment;

  const _InboxCard({
    required this.item,
    required this.lang,
    required this.onMarkRead,
    required this.onApprove,
    required this.onReject,
    required this.onArchive,
    required this.onComment,
  });

  @override
  State<_InboxCard> createState() => _InboxCardState();
}

class _InboxCardState extends State<_InboxCard> {
  bool _expanded = false;
  final _commentCtrl = TextEditingController();

  @override
  void dispose() {
    _commentCtrl.dispose();
    super.dispose();
  }

  void _toggleExpand() {
    setState(() => _expanded = !_expanded);
    if (_expanded) widget.onMarkRead();
  }

  String _contentTypeLabel(String type) {
    return switch (type) {
      'report' => L10n.t('inbox.typeReport', widget.lang),
      'draft' => L10n.t('inbox.typeDraft', widget.lang),
      'analysis' => L10n.t('inbox.typeAnalysis', widget.lang),
      'code' => L10n.t('inbox.typeCode', widget.lang),
      'notification' => L10n.t('inbox.typeNotification', widget.lang),
      _ => type,
    };
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

  Color _statusColor(String status, ColorScheme cs) {
    return switch (status) {
      'unread' => cs.primary,
      'read' => cs.onSurfaceVariant,
      'approved' => Colors.green,
      'rejected' => cs.error,
      'archived' => cs.onSurfaceVariant.withValues(alpha: 0.5),
      _ => cs.onSurfaceVariant,
    };
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

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final item = widget.item;
    final lang = widget.lang;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Card(
        elevation: item.status == 'unread' ? 2 : 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: item.status == 'unread'
              ? BorderSide(
                  color: cs.primary.withValues(alpha: 0.4), width: 1)
              : BorderSide(
                  color: cs.outlineVariant.withValues(alpha: 0.3)),
        ),
        child: InkWell(
          onTap: _toggleExpand,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _statusColor(item.status, cs),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item.title,
                            style: TextStyle(
                              fontWeight: item.status == 'unread'
                                  ? FontWeight.w600
                                  : FontWeight.normal,
                              fontSize: 14,
                              color: cs.onSurface,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${item.directorName} • ${_formatTimestamp(item.createdAt)}',
                            style: TextStyle(
                                fontSize: 12, color: cs.onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: cs.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(_contentTypeIcon(item.contentType),
                              size: 12, color: cs.onSurfaceVariant),
                          const SizedBox(width: 4),
                          Text(
                            _contentTypeLabel(item.contentType),
                            style: TextStyle(
                                fontSize: 11, color: cs.onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),

                // Expanded content
                if (_expanded) ...[
                  const SizedBox(height: 12),
                  const Divider(height: 1),
                  const SizedBox(height: 12),

                  Container(
                    width: double.infinity,
                    constraints: const BoxConstraints(maxHeight: 400),
                    child: SingleChildScrollView(
                      child: MarkdownBody(
                        data: item.content,
                        selectable: true,
                        styleSheet: MarkdownStyleSheet(
                          p: TextStyle(fontSize: 13, color: cs.onSurface),
                          code: TextStyle(
                            fontSize: 12,
                            fontFamily: 'monospace',
                            color: cs.primary,
                            backgroundColor: cs.surfaceContainerHighest,
                          ),
                          codeblockDecoration: BoxDecoration(
                            color: cs.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ),
                  ),

                  if (item.userComment != null &&
                      item.userComment!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color:
                            cs.primaryContainer.withValues(alpha: 0.3),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        item.userComment!,
                        style: TextStyle(
                          fontSize: 12,
                          fontStyle: FontStyle.italic,
                          color: cs.onSurface,
                        ),
                      ),
                    ),
                  ],

                  const SizedBox(height: 12),
                  TextField(
                    controller: _commentCtrl,
                    decoration: InputDecoration(
                      hintText: L10n.t('inbox.commentHint', lang),
                      border: const OutlineInputBorder(),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      isDense: true,
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.send, size: 18),
                        onPressed: () {
                          if (_commentCtrl.text.trim().isNotEmpty) {
                            widget.onComment(_commentCtrl.text.trim());
                            _commentCtrl.clear();
                          }
                        },
                      ),
                    ),
                    style: const TextStyle(fontSize: 13),
                  ),

                  if (item.status != 'approved' &&
                      item.status != 'rejected' &&
                      item.status != 'archived') ...[
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: widget.onApprove,
                            icon: const Icon(Icons.check, size: 16),
                            label: Text(L10n.t('inbox.approve', lang),
                                style: const TextStyle(fontSize: 13)),
                            style: FilledButton.styleFrom(
                                backgroundColor: Colors.green),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: widget.onReject,
                            icon: Icon(Icons.close,
                                size: 16, color: cs.error),
                            label: Text(L10n.t('inbox.reject', lang),
                                style: TextStyle(
                                    fontSize: 13, color: cs.error)),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton(
                          onPressed: widget.onArchive,
                          icon: Icon(Icons.archive_outlined,
                              color: cs.onSurfaceVariant),
                          tooltip: L10n.t('inbox.archive', lang),
                        ),
                      ],
                    ),
                  ],
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
