import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class DirectorsScreen extends ConsumerStatefulWidget {
  const DirectorsScreen({super.key});

  @override
  ConsumerState<DirectorsScreen> createState() => _DirectorsScreenState();
}

class _DirectorsScreenState extends ConsumerState<DirectorsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  // Directors tab
  List<Director>? _directors;
  bool _directorsLoading = true;
  String? _directorsError;
  final Set<String> _runningIds = {};

  // Templates tab
  List<DirectorTemplate>? _templates;
  bool _templatesLoading = true;

  // Tasks tab
  List<DirectorTask>? _tasks;
  bool _tasksLoading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(_onTabChanged);
    _loadDirectors();
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) return;
    switch (_tabController.index) {
      case 1:
        if (_templates == null) _loadTemplates();
      case 2:
        _loadTasks();
    }
  }

  // ── API ──

  Future<void> _loadDirectors() async {
    setState(() {
      _directorsLoading = true;
      _directorsError = null;
    });
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.get('/api/directors');
      if (!mounted) return;
      final list = (res.data['directors'] as List? ?? [])
          .map((e) => Director.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() {
        _directors = list;
        _directorsLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _directorsError = e.toString();
        _directorsLoading = false;
      });
    }
  }

  Future<void> _loadTemplates() async {
    setState(() => _templatesLoading = true);
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.get('/api/directors/templates');
      if (!mounted) return;
      final list = (res.data['templates'] as List? ?? [])
          .map((e) => DirectorTemplate.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() {
        _templates = list;
        _templatesLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _templatesLoading = false);
    }
  }

  Future<void> _loadTasks() async {
    setState(() => _tasksLoading = true);
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.get('/api/directors/tasks');
      if (!mounted) return;
      final list = (res.data['tasks'] as List? ?? [])
          .map((e) => DirectorTask.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() {
        _tasks = list;
        _tasksLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _tasksLoading = false);
    }
  }

  Future<void> _toggleEnabled(Director d) async {
    final endpoint = d.enabled
        ? '/api/directors/${d.id}/disable'
        : '/api/directors/${d.id}/enable';
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.post(endpoint);
      if (!mounted) return;
      await _loadDirectors();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    }
  }

  Future<void> _runNow(Director d) async {
    final lang = ref.read(settingsProvider).language;
    setState(() => _runningIds.add(d.id));
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.post('/api/directors/${d.id}/run');
      if (!mounted) return;
      showToast(context, L10n.t('directors.running', lang),
          type: ToastType.success);
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    } finally {
      if (mounted) setState(() => _runningIds.remove(d.id));
    }
  }

  Future<void> _deleteDirector(Director d) async {
    final lang = ref.read(settingsProvider).language;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(L10n.t('directors.delete', lang)),
        content: Text(L10n.t('directors.deleteConfirm', lang,
            {'name': d.name})),
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

    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.delete('/api/directors/${d.id}');
      if (!mounted) return;
      await _loadDirectors();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    }
  }

  Future<void> _createFromTemplate(DirectorTemplate t) async {
    _showCreateSheet(template: t);
  }

  Future<void> _createDirector(Map<String, dynamic> data) async {
    final lang = ref.read(settingsProvider).language;
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.post('/api/directors', data: data);
      if (!mounted) return;
      showToast(context, L10n.t('directors.create', lang),
          type: ToastType.success);
      await _loadDirectors();
      _tabController.animateTo(0);
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    }
  }

  void _showCreateSheet({DirectorTemplate? template}) {
    final lang = ref.read(settingsProvider).language;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _CreateDirectorSheet(
        lang: lang,
        template: template,
        onCreated: (data) async {
          Navigator.of(ctx).pop();
          await _createDirector(data);
        },
      ),
    );
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('directors.title', lang)),
        actions: [
          IconButton(
            onPressed: _loadDirectors,
            icon: const Icon(Icons.refresh),
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: L10n.t('directors.title', lang)),
            Tab(text: L10n.t('directors.templates', lang)),
            Tab(text: L10n.t('directors.taskQueue', lang)),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showCreateSheet(),
        icon: const Icon(Icons.add),
        label: Text(L10n.t('directors.create', lang)),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildDirectorsTab(cs, lang),
          _buildTemplatesTab(cs, lang),
          _buildTasksTab(cs, lang),
        ],
      ),
    );
  }

  Widget _buildDirectorsTab(ColorScheme cs, String lang) {
    if (_directorsLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_directorsError != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: cs.error),
            const SizedBox(height: 16),
            Text(_directorsError!,
                textAlign: TextAlign.center,
                style: TextStyle(color: cs.onSurfaceVariant)),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _loadDirectors,
              icon: const Icon(Icons.refresh),
              label: Text(L10n.t('metrics.refresh', lang)),
            ),
          ],
        ),
      );
    }
    if (_directors == null || _directors!.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.smart_toy_outlined,
                size: 48, color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(L10n.t('directors.empty', lang),
                style: TextStyle(color: cs.onSurfaceVariant)),
            const SizedBox(height: 4),
            Text(L10n.t('directors.emptyHint', lang),
                style: TextStyle(
                    fontSize: 12, color: cs.onSurfaceVariant.withValues(alpha: 0.6))),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadDirectors,
      child: ListView.separated(
        padding: const EdgeInsets.only(top: 8, bottom: 80),
        itemCount: _directors!.length,
        separatorBuilder: (_, __) => const SizedBox(height: 4),
        itemBuilder: (_, i) => _DirectorCard(
          director: _directors![i],
          lang: lang,
          isRunning: _runningIds.contains(_directors![i].id),
          onToggle: () => _toggleEnabled(_directors![i]),
          onRun: () => _runNow(_directors![i]),
          onDelete: () => _deleteDirector(_directors![i]),
        ),
      ),
    );
  }

  Widget _buildTemplatesTab(ColorScheme cs, String lang) {
    if (_templatesLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_templates == null || _templates!.isEmpty) {
      return Center(
        child: Text(L10n.t('directors.empty', lang),
            style: TextStyle(color: cs.onSurfaceVariant)),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.only(top: 8, bottom: 80),
      itemCount: _templates!.length,
      separatorBuilder: (_, __) => const SizedBox(height: 4),
      itemBuilder: (_, i) => _TemplateCard(
        template: _templates![i],
        lang: lang,
        onInstall: () => _createFromTemplate(_templates![i]),
      ),
    );
  }

  Widget _buildTasksTab(ColorScheme cs, String lang) {
    if (_tasksLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_tasks == null || _tasks!.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.task_outlined,
                size: 48, color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(L10n.t('directors.noTasks', lang),
                style: TextStyle(color: cs.onSurfaceVariant)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadTasks,
      child: ListView.separated(
        padding: const EdgeInsets.only(top: 8, bottom: 16),
        itemCount: _tasks!.length,
        separatorBuilder: (_, __) => const SizedBox(height: 4),
        itemBuilder: (_, i) => _TaskRow(task: _tasks![i], lang: lang),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Director card
// ---------------------------------------------------------------------------

class _DirectorCard extends StatefulWidget {
  final Director director;
  final String lang;
  final bool isRunning;
  final VoidCallback onToggle;
  final VoidCallback onRun;
  final VoidCallback onDelete;

  const _DirectorCard({
    required this.director,
    required this.lang,
    required this.isRunning,
    required this.onToggle,
    required this.onRun,
    required this.onDelete,
  });

  @override
  State<_DirectorCard> createState() => _DirectorCardState();
}

class _DirectorCardState extends State<_DirectorCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final d = widget.director;
    final lang = widget.lang;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Card(
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: d.enabled
              ? BorderSide(color: cs.primary.withValues(alpha: 0.3), width: 1)
              : BorderSide.none,
        ),
        child: InkWell(
          onTap: () => setState(() => _expanded = !_expanded),
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row
                Row(
                  children: [
                    // Emoji avatar
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: d.enabled
                            ? cs.primaryContainer
                            : cs.surfaceContainerHighest,
                      ),
                      alignment: Alignment.center,
                      child: Text(d.emoji, style: const TextStyle(fontSize: 24)),
                    ),
                    const SizedBox(width: 12),

                    // Name + schedule
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  d.name,
                                  style: TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 15,
                                    color: d.enabled
                                        ? cs.onSurface
                                        : cs.onSurfaceVariant,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: d.enabled
                                      ? cs.primaryContainer
                                      : cs.surfaceContainerHighest,
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Text(
                                  d.enabled
                                      ? L10n.t('directors.enabled', lang)
                                      : L10n.t('directors.disabled', lang),
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w600,
                                    color: d.enabled
                                        ? cs.primary
                                        : cs.onSurfaceVariant,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            d.schedule != null
                                ? '${L10n.t('directors.schedule', lang)}: ${d.schedule}'
                                : L10n.t('directors.manual', lang),
                            style: TextStyle(
                              fontSize: 12,
                              color: cs.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),

                    // Enable toggle
                    Switch(
                      value: d.enabled,
                      onChanged: (_) => widget.onToggle(),
                    ),
                  ],
                ),

                // Stats row
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.play_arrow, size: 14, color: cs.onSurfaceVariant),
                    const SizedBox(width: 4),
                    Text(
                      L10n.t('directors.runs', lang, {'n': '${d.runCount}'}),
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurfaceVariant),
                    ),
                    const SizedBox(width: 16),
                    Icon(Icons.attach_money, size: 14, color: cs.onSurfaceVariant),
                    const SizedBox(width: 2),
                    Text(
                      '\$${d.totalCost.toStringAsFixed(4)}',
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurfaceVariant),
                    ),
                    if (d.canDelegate) ...[
                      const SizedBox(width: 16),
                      Icon(Icons.call_split, size: 14, color: cs.primary),
                      const SizedBox(width: 4),
                      Text(
                        L10n.t('directors.canDelegate', lang),
                        style: TextStyle(fontSize: 12, color: cs.primary),
                      ),
                    ],
                    const Spacer(),
                    // Run Now button
                    if (d.enabled)
                      SizedBox(
                        height: 30,
                        child: FilledButton.tonalIcon(
                          onPressed: widget.isRunning ? null : widget.onRun,
                          icon: widget.isRunning
                              ? const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2),
                                )
                              : const Icon(Icons.play_arrow, size: 16),
                          label: Text(
                            L10n.t('directors.runNow', lang),
                            style: const TextStyle(fontSize: 12),
                          ),
                        ),
                      ),
                  ],
                ),

                // Expanded details
                if (_expanded) ...[
                  const SizedBox(height: 12),
                  const Divider(height: 1),
                  const SizedBox(height: 12),

                  if (d.description.isNotEmpty) ...[
                    Text(d.description,
                        style: TextStyle(
                            fontSize: 13, color: cs.onSurfaceVariant)),
                    const SizedBox(height: 8),
                  ],

                  // Role prompt preview
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: cs.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      d.rolePrompt.length > 300
                          ? '${d.rolePrompt.substring(0, 300)}...'
                          : d.rolePrompt,
                      style: TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                        color: cs.onSurfaceVariant,
                      ),
                    ),
                  ),

                  if (d.lastRun != null) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.schedule, size: 14, color: cs.onSurfaceVariant),
                        const SizedBox(width: 4),
                        Text(
                          '${L10n.t('directors.lastRun', lang)}: ${_formatTimestamp(d.lastRun!)}',
                          style: TextStyle(
                              fontSize: 12, color: cs.onSurfaceVariant),
                        ),
                        if (d.lastError != null) ...[
                          const SizedBox(width: 8),
                          Icon(Icons.error_outline, size: 14, color: cs.error),
                        ],
                      ],
                    ),
                  ],

                  const SizedBox(height: 12),
                  // Delete button
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(
                      onPressed: widget.onDelete,
                      icon: Icon(Icons.delete_outline, size: 16, color: cs.error),
                      label: Text(
                        L10n.t('directors.delete', lang),
                        style: TextStyle(color: cs.error, fontSize: 13),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
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
}

// ---------------------------------------------------------------------------
// Template card
// ---------------------------------------------------------------------------

class _TemplateCard extends StatelessWidget {
  final DirectorTemplate template;
  final String lang;
  final VoidCallback onInstall;

  const _TemplateCard({
    required this.template,
    required this.lang,
    required this.onInstall,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final t = template;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Card(
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              // Emoji avatar
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: cs.primaryContainer,
                ),
                alignment: Alignment.center,
                child: Text(t.emoji, style: const TextStyle(fontSize: 24)),
              ),
              const SizedBox(width: 12),

              // Name + description
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      t.name,
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
                        color: cs.onSurface,
                      ),
                    ),
                    if (t.description.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        t.description,
                        style: TextStyle(
                          fontSize: 12,
                          color: cs.onSurfaceVariant,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    if (t.defaultSchedule.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(Icons.schedule, size: 12, color: cs.onSurfaceVariant),
                          const SizedBox(width: 4),
                          Text(
                            t.defaultSchedule,
                            style: TextStyle(
                              fontSize: 11,
                              color: cs.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),

              // Install button
              FilledButton.tonalIcon(
                onPressed: onInstall,
                icon: const Icon(Icons.add, size: 18),
                label: Text(L10n.t('directors.install', lang)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Task row
// ---------------------------------------------------------------------------

class _TaskRow extends StatelessWidget {
  final DirectorTask task;
  final String lang;

  const _TaskRow({required this.task, required this.lang});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    final statusColor = switch (task.status) {
      'completed' => Colors.green,
      'running' => cs.primary,
      'failed' => cs.error,
      'cancelled' => cs.onSurfaceVariant,
      _ => Colors.orange,
    };

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Card(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: cs.outlineVariant.withValues(alpha: 0.3)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Status dot
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: statusColor,
                ),
              ),
              const SizedBox(width: 10),

              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      task.title,
                      style: TextStyle(
                        fontWeight: FontWeight.w500,
                        fontSize: 14,
                        color: cs.onSurface,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${task.taskType} • ${task.status}',
                      style: TextStyle(
                        fontSize: 12,
                        color: cs.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),

              // Priority badge
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: task.priority <= 3
                      ? cs.errorContainer
                      : cs.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  'P${task.priority}',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: task.priority <= 3
                        ? cs.onErrorContainer
                        : cs.onSurfaceVariant,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Create director bottom sheet
// ---------------------------------------------------------------------------

class _CreateDirectorSheet extends StatefulWidget {
  final String lang;
  final DirectorTemplate? template;
  final Future<void> Function(Map<String, dynamic> data) onCreated;

  const _CreateDirectorSheet({
    required this.lang,
    this.template,
    required this.onCreated,
  });

  @override
  State<_CreateDirectorSheet> createState() => _CreateDirectorSheetState();
}

class _CreateDirectorSheetState extends State<_CreateDirectorSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _emojiCtrl;
  late final TextEditingController _nameCtrl;
  late final TextEditingController _descCtrl;
  late final TextEditingController _promptCtrl;
  late final TextEditingController _scheduleCtrl;
  bool _canDelegate = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final t = widget.template;
    _emojiCtrl = TextEditingController(text: t?.emoji ?? '\u{1F916}');
    _nameCtrl = TextEditingController(text: t?.name ?? '');
    _descCtrl = TextEditingController(text: t?.description ?? '');
    _promptCtrl = TextEditingController(text: t?.rolePrompt ?? '');
    _scheduleCtrl = TextEditingController(text: t?.defaultSchedule ?? '');
    _canDelegate = t?.canDelegate ?? false;
  }

  @override
  void dispose() {
    _emojiCtrl.dispose();
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _promptCtrl.dispose();
    _scheduleCtrl.dispose();
    super.dispose();
  }

  String _generateId(String name) {
    return name
        .toLowerCase()
        .trim()
        .replaceAll(RegExp(r'[^a-z0-9]+'), '_')
        .replaceAll(RegExp(r'^_+|_+$'), '');
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);

    final data = <String, dynamic>{
      'id': _generateId(_nameCtrl.text),
      'name': _nameCtrl.text.trim(),
      'emoji': _emojiCtrl.text.trim(),
      'description': _descCtrl.text.trim(),
      'role_prompt': _promptCtrl.text.trim(),
      'can_delegate': _canDelegate,
    };

    final schedule = _scheduleCtrl.text.trim();
    if (schedule.isNotEmpty) {
      data['schedule'] = schedule;
    }

    await widget.onCreated(data);
    if (mounted) setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = widget.lang;

    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Drag handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: cs.onSurfaceVariant.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              Text(
                L10n.t('directors.createTitle', lang),
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: cs.onSurface,
                ),
              ),
              const SizedBox(height: 20),

              // Emoji + Name row
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 72,
                    child: TextFormField(
                      controller: _emojiCtrl,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 28),
                      decoration: InputDecoration(
                        labelText: L10n.t('directors.emoji', lang),
                        border: const OutlineInputBorder(),
                        contentPadding: const EdgeInsets.symmetric(
                            vertical: 12, horizontal: 8),
                      ),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? '' : null,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _nameCtrl,
                      decoration: InputDecoration(
                        labelText: L10n.t('directors.name', lang),
                        border: const OutlineInputBorder(),
                      ),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? '' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Description
              TextFormField(
                controller: _descCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('directors.description', lang),
                  border: const OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 14),

              // Role prompt
              TextFormField(
                controller: _promptCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('directors.rolePrompt', lang),
                  hintText: L10n.t('directors.rolePromptHint', lang),
                  border: const OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
                maxLines: 5,
                minLines: 3,
                validator: (v) =>
                    (v == null || v.trim().length < 20) ? L10n.t('directors.rolePromptHint', lang) : null,
              ),
              const SizedBox(height: 14),

              // Schedule
              TextFormField(
                controller: _scheduleCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('directors.schedule', lang),
                  hintText: L10n.t('directors.scheduleHint', lang),
                  border: const OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 10),

              // Can delegate toggle
              SwitchListTile(
                title: Text(L10n.t('directors.canDelegate', lang),
                    style: const TextStyle(fontSize: 14)),
                value: _canDelegate,
                onChanged: (v) => setState(() => _canDelegate = v),
                contentPadding: EdgeInsets.zero,
              ),
              const SizedBox(height: 16),

              // Buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed:
                          _saving ? null : () => Navigator.of(context).pop(),
                      child: Text(L10n.t('agent.cancel', lang)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: _saving ? null : _submit,
                      child: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child:
                                  CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(L10n.t('directors.create', lang)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }
}
