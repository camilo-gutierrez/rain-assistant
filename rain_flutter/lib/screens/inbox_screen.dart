import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class InboxScreen extends ConsumerStatefulWidget {
  const InboxScreen({super.key});

  @override
  ConsumerState<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends ConsumerState<InboxScreen> {
  List<InboxItem>? _items;
  bool _loading = true;
  String? _error;
  int _unreadCount = 0;
  String _filter = 'all'; // all | unread | approved | archived

  @override
  void initState() {
    super.initState();
    _loadInbox();
  }

  Future<void> _loadInbox() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;

      // Load items with filter
      final params = <String, String>{};
      if (_filter != 'all') params['status'] = _filter;
      final res = await dio.get('/api/directors/inbox', queryParameters: params);
      if (!mounted) return;

      final list = (res.data['items'] as List? ?? [])
          .map((e) => InboxItem.fromJson(e as Map<String, dynamic>))
          .toList();
      final unread = (res.data['unread_count'] as num?)?.toInt() ?? 0;

      setState(() {
        _items = list;
        _unreadCount = unread;
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

  Future<void> _updateStatus(InboxItem item, String newStatus,
      {String? comment}) async {
    final lang = ref.read(settingsProvider).language;
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final body = <String, dynamic>{'status': newStatus};
      if (comment != null && comment.isNotEmpty) {
        body['user_comment'] = comment;
      }
      await dio.patch('/api/directors/inbox/${item.id}', data: body);
      if (!mounted) return;
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
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    }
  }

  Future<void> _markAsRead(InboxItem item) async {
    if (item.status != 'unread') return;
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.patch('/api/directors/inbox/${item.id}',
          data: {'status': 'read'});
      if (!mounted) return;
      // Silently update unread count
      setState(() {
        if (_unreadCount > 0) _unreadCount--;
      });
    } catch (_) {
      // Silently ignore read-mark failures
    }
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

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(L10n.t('inbox.title', lang)),
            if (_unreadCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: cs.primary,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$_unreadCount',
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

          // Content
          Expanded(child: _buildContent(cs, lang)),
        ],
      ),
    );
  }

  Widget _buildContent(ColorScheme cs, String lang) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: cs.error),
            const SizedBox(height: 16),
            Text(_error!,
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
    if (_items == null || _items!.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.inbox_outlined,
                size: 48, color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
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
        itemCount: _items!.length,
        separatorBuilder: (_, __) => const SizedBox(height: 4),
        itemBuilder: (_, i) => _InboxCard(
          item: _items![i],
          lang: lang,
          onMarkRead: () => _markAsRead(_items![i]),
          onApprove: () => _updateStatus(_items![i], 'approved'),
          onReject: () => _updateStatus(_items![i], 'rejected'),
          onArchive: () => _updateStatus(_items![i], 'archived'),
          onComment: (c) =>
              _updateStatus(_items![i], _items![i].status, comment: c),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Filter chip
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Inbox card
// ---------------------------------------------------------------------------

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
              ? BorderSide(color: cs.primary.withValues(alpha: 0.4), width: 1)
              : BorderSide(color: cs.outlineVariant.withValues(alpha: 0.3)),
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
                    // Status dot
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _statusColor(item.status, cs),
                      ),
                    ),
                    const SizedBox(width: 10),

                    // Title + director
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
                              fontSize: 12,
                              color: cs.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(width: 8),

                    // Content type chip
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
                              fontSize: 11,
                              color: cs.onSurfaceVariant,
                            ),
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

                  // Markdown content
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

                  // User comment if exists
                  if (item.userComment != null &&
                      item.userComment!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: cs.primaryContainer.withValues(alpha: 0.3),
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

                  // Comment input
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

                  // Action buttons
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
                              backgroundColor: Colors.green,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: widget.onReject,
                            icon: Icon(Icons.close, size: 16, color: cs.error),
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
