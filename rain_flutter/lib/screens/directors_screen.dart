import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/directors_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';
import 'director_detail_screen.dart';

// ── Cron validation ──

String? validateCron(String? value, String lang) {
  if (value == null || value.trim().isEmpty) return null;
  final trimmed = value.trim().toLowerCase();

  const aliases = {
    '@hourly', '@daily', '@weekly', '@monthly', '@yearly', '@annually'
  };
  if (aliases.contains(trimmed)) return null;

  final parts = trimmed.split(RegExp(r'\s+'));
  if (parts.length != 5) return L10n.t('directors.cronError', lang);

  final ranges = [
    [0, 59],
    [0, 23],
    [1, 31],
    [1, 12],
    [0, 7],
  ];

  final fieldPattern =
      RegExp(r'^(\*(/\d+)?|\d+(-\d+)?(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$');

  for (var i = 0; i < 5; i++) {
    if (!fieldPattern.hasMatch(parts[i])) {
      return L10n.t('directors.cronError', lang);
    }
    final numbers = RegExp(r'\d+').allMatches(parts[i]);
    for (final m in numbers) {
      final n = int.tryParse(m.group(0)!) ?? -1;
      if (n < ranges[i][0] || n > ranges[i][1]) {
        return L10n.t('directors.cronErrorRange', lang);
      }
    }
  }
  return null;
}

// ── Screen ──

class DirectorsScreen extends ConsumerStatefulWidget {
  const DirectorsScreen({super.key});

  @override
  ConsumerState<DirectorsScreen> createState() => _DirectorsScreenState();
}

class _DirectorsScreenState extends ConsumerState<DirectorsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(_onTabChanged);
    _initialLoad();
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _initialLoad() {
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final notifier = ref.read(directorsProvider.notifier);
    notifier.loadDirectors(dio);
    notifier.loadStats(dio);
    notifier.loadProjects(dio);
    notifier.loadTeamTemplates(dio);
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) return;
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final notifier = ref.read(directorsProvider.notifier);
    switch (_tabController.index) {
      case 1:
        final s = ref.read(directorsProvider);
        if (s.templates.isEmpty) notifier.loadTemplates(dio);
        if (s.teamTemplates.isEmpty) notifier.loadTeamTemplates(dio);
      case 2:
        notifier.loadTasks(dio);
      case 3:
        notifier.loadActivity(dio);
    }
  }

  Future<void> _refresh() async {
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final notifier = ref.read(directorsProvider.notifier);
    await notifier.loadDirectors(dio);
    notifier.loadStats(dio);
  }

  Future<void> _toggleEnabled(Director d) async {
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final ok = await ref.read(directorsProvider.notifier).toggleEnabled(dio, d);
    if (!ok && mounted) {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  Future<void> _runNow(Director d) async {
    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final ok = await ref.read(directorsProvider.notifier).runNow(dio, d);
    if (mounted && ok) {
      showToast(context, L10n.t('directors.running', lang),
          type: ToastType.success);
    } else if (mounted) {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  Future<void> _runTeam() async {
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final projectId = ref.read(directorsProvider).activeProjectId;
    if (projectId.isEmpty) return;
    final ok = await ref.read(directorsProvider.notifier).runProject(dio, projectId);
    if (mounted && !ok) {
      showToast(context, 'Error', type: ToastType.error);
    }
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
    if (!ok && mounted) {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  Future<void> _createDirector(Map<String, dynamic> data) async {
    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final ok =
        await ref.read(directorsProvider.notifier).createDirector(dio, data);
    if (mounted && ok) {
      showToast(context, L10n.t('directors.create', lang),
          type: ToastType.success);
      _tabController.animateTo(0);
    } else if (mounted) {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  void _showCreateSheet({DirectorTemplate? template}) {
    final lang = ref.read(settingsProvider).language;
    final ps = ref.read(directorsProvider);
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
        projects: ps.projects,
        activeProjectId: ps.activeProjectId,
        onCreated: (data) async {
          Navigator.of(ctx).pop();
          await _createDirector(data);
        },
      ),
    );
  }

  void _showCreateProjectSheet() {
    final lang = ref.read(settingsProvider).language;
    final teamTemplates = ref.read(directorsProvider).teamTemplates;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _CreateProjectSheet(
        lang: lang,
        teamTemplates: teamTemplates,
        onCreated: (data) async {
          Navigator.of(ctx).pop();
          await _createProject(data);
        },
      ),
    );
  }

  Future<void> _createProject(Map<String, dynamic> data) async {
    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final notifier = ref.read(directorsProvider.notifier);
    final project = await notifier.createProject(dio, data);
    if (mounted && project != null) {
      showToast(context, L10n.t('projects.create', lang),
          type: ToastType.success);
      notifier.setActiveProject(dio, project.id);
      _tabController.animateTo(0);
    } else if (mounted) {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  Future<void> _deleteProject(DirectorProject project) async {
    final lang = ref.read(settingsProvider).language;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(L10n.t('projects.delete', lang)),
        content: Text(
            L10n.t('projects.deleteConfirm', lang, {'name': project.name})),
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
            child: Text(L10n.t('projects.delete', lang)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final dio = ref.read(authServiceProvider).authenticatedDio;
    final ok =
        await ref.read(directorsProvider.notifier).deleteProject(dio, project.id);
    if (!ok && mounted) {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    final ps = ref.watch(directorsProvider);
    final activeProject = ps.activeProjectId.isEmpty
        ? null
        : ps.projects.cast<DirectorProject?>().firstWhere(
              (p) => p!.id == ps.activeProjectId,
              orElse: () => null,
            );

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('directors.title', lang)),
        actions: [
          PopupMenuButton<String>(
            tooltip: L10n.t('projects.title', lang),
            offset: const Offset(0, 48),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(activeProject?.emoji ?? '📋',
                      style: const TextStyle(fontSize: 18)),
                  const SizedBox(width: 4),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 100),
                    child: Text(
                      activeProject?.name ??
                          L10n.t('projects.allDirectors', lang),
                      style: TextStyle(fontSize: 13, color: cs.onSurface),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(Icons.arrow_drop_down,
                      size: 18, color: cs.onSurfaceVariant),
                ],
              ),
            ),
            onSelected: (value) {
              if (value == '_create') {
                _showCreateProjectSheet();
              } else if (value == '_delete' && activeProject != null) {
                _deleteProject(activeProject);
              } else {
                final dio = ref.read(authServiceProvider).authenticatedDio;
                ref
                    .read(directorsProvider.notifier)
                    .setActiveProject(dio, value);
              }
            },
            itemBuilder: (ctx) => [
              PopupMenuItem(
                value: '',
                child: Row(children: [
                  const Text('📋', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 10),
                  Text(L10n.t('projects.allDirectors', lang)),
                ]),
              ),
              if (ps.projects.isNotEmpty) const PopupMenuDivider(),
              ...ps.projects.map((p) => PopupMenuItem(
                    value: p.id,
                    child: Row(children: [
                      Text(p.emoji, style: const TextStyle(fontSize: 16)),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(p.name,
                            overflow: TextOverflow.ellipsis),
                      ),
                      if (p.id == ps.activeProjectId)
                        Icon(Icons.check, size: 18, color: cs.primary),
                    ]),
                  )),
              const PopupMenuDivider(),
              PopupMenuItem(
                value: '_create',
                child: Row(children: [
                  Icon(Icons.add_circle_outline,
                      size: 18, color: cs.primary),
                  const SizedBox(width: 10),
                  Text(L10n.t('projects.create', lang),
                      style: TextStyle(color: cs.primary)),
                ]),
              ),
              if (activeProject != null)
                PopupMenuItem(
                  value: '_delete',
                  child: Row(children: [
                    Icon(Icons.delete_outline, size: 18, color: cs.error),
                    const SizedBox(width: 10),
                    Text(L10n.t('projects.delete', lang),
                        style: TextStyle(color: cs.error)),
                  ]),
                ),
            ],
          ),
          IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh)),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: [
            Tab(text: L10n.t('directors.title', lang)),
            Tab(text: L10n.t('directors.templates', lang)),
            Tab(text: L10n.t('directors.taskQueue', lang)),
            Tab(text: L10n.t('directors.activity', lang)),
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
          _buildActivityTab(cs, lang),
        ],
      ),
    );
  }

  // ── Directors tab ──

  Widget _buildDirectorsTab(ColorScheme cs, String lang) {
    final s = ref.watch(directorsProvider);

    if (s.directorsLoading && s.directors.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (s.directorsError != null && s.directors.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: cs.error),
            const SizedBox(height: 16),
            Text(s.directorsError!,
                textAlign: TextAlign.center,
                style: TextStyle(color: cs.onSurfaceVariant)),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
              label: Text(L10n.t('metrics.refresh', lang)),
            ),
          ],
        ),
      );
    }
    if (s.directors.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.smart_toy_outlined,
                size: 48,
                color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(L10n.t('directors.empty', lang),
                style: TextStyle(color: cs.onSurfaceVariant)),
            const SizedBox(height: 4),
            Text(L10n.t('directors.emptyHint', lang),
                style: TextStyle(
                    fontSize: 12,
                    color: cs.onSurfaceVariant.withValues(alpha: 0.6))),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.only(top: 8, bottom: 80),
        children: [
          // Run Team button + progress
          if (s.activeProjectId.isNotEmpty && s.directors.isNotEmpty) ...[
            if (s.activeTeamRun == null)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
                child: FilledButton.tonalIcon(
                  onPressed: s.teamRunning ? null : _runTeam,
                  icon: s.teamRunning
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.play_circle_outline, size: 20),
                  label: Text(
                    s.teamRunning
                        ? L10n.t('directors.teamRunning', lang)
                        : L10n.t('directors.runTeam', lang),
                  ),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(double.infinity, 44),
                  ),
                ),
              ),
            if (s.activeTeamRun != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
                child: _TeamRunProgress(
                  run: s.activeTeamRun!,
                  lang: lang,
                  onDismiss: () =>
                      ref.read(directorsProvider.notifier).clearTeamRun(),
                ),
              ),
          ],
          if (s.stats != null) _StatsHeader(stats: s.stats!, lang: lang),
          ...s.directors.map((d) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: _DirectorCard(
                  director: d,
                  lang: lang,
                  isRunning: s.runningIds.contains(d.id),
                  onToggle: () => _toggleEnabled(d),
                  onRun: () => _runNow(d),
                  onDelete: () => _deleteDirector(d),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => DirectorDetailScreen(directorId: d.id),
                    ),
                  ),
                ),
              )),
        ],
      ),
    );
  }

  // ── Templates tab ──

  Widget _buildTemplatesTab(ColorScheme cs, String lang) {
    final s = ref.watch(directorsProvider);

    if (s.templatesLoading && s.templates.isEmpty && s.teamTemplates.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (s.templates.isEmpty && s.teamTemplates.isEmpty) {
      return Center(
        child: Text(L10n.t('directors.empty', lang),
            style: TextStyle(color: cs.onSurfaceVariant)),
      );
    }

    final visibleTeams =
        s.teamTemplates.where((t) => t.directors.isNotEmpty).toList();

    return DefaultTabController(
      length: 2,
      child: Column(
        children: [
          // Inner segmented tab bar
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Container(
              height: 36,
              decoration: BoxDecoration(
                color: cs.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(10),
              ),
              child: TabBar(
                indicatorSize: TabBarIndicatorSize.tab,
                dividerColor: Colors.transparent,
                indicator: BoxDecoration(
                  color: cs.surface,
                  borderRadius: BorderRadius.circular(8),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.08),
                      blurRadius: 2,
                      offset: const Offset(0, 1),
                    ),
                  ],
                ),
                indicatorPadding: const EdgeInsets.all(3),
                labelColor: cs.onSurface,
                unselectedLabelColor: cs.onSurfaceVariant,
                labelStyle: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600),
                unselectedLabelStyle: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w500),
                tabs: [
                  Tab(text: L10n.t('directors.individualTemplates', lang)),
                  Tab(text: L10n.t('directors.teamTemplates', lang)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          // Tab content
          Expanded(
            child: TabBarView(
              children: [
                // Individual directors list
                s.templates.isEmpty
                    ? Center(
                        child: Text(L10n.t('directors.empty', lang),
                            style: TextStyle(color: cs.onSurfaceVariant)))
                    : ListView.builder(
                        padding: const EdgeInsets.only(bottom: 80),
                        itemCount: s.templates.length,
                        itemBuilder: (_, i) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: _TemplateCard(
                            template: s.templates[i],
                            lang: lang,
                            onInstall: () =>
                                _showCreateSheet(template: s.templates[i]),
                          ),
                        ),
                      ),
                // Teams list
                visibleTeams.isEmpty
                    ? Center(
                        child: Text(L10n.t('directors.empty', lang),
                            style: TextStyle(color: cs.onSurfaceVariant)))
                    : ListView.builder(
                        padding: const EdgeInsets.only(bottom: 80),
                        itemCount: visibleTeams.length,
                        itemBuilder: (_, i) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: _TeamTemplateCard(
                            team: visibleTeams[i],
                            lang: lang,
                            onCreateProject: () =>
                                _createProjectFromTeam(visibleTeams[i]),
                          ),
                        ),
                      ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _createProjectFromTeam(TeamTemplate team) async {
    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;
    final notifier = ref.read(directorsProvider.notifier);
    final project = await notifier.createProject(dio, {
      'name': team.name,
      'emoji': team.emoji,
      'description': team.description,
      'color': team.color,
      'team_template': team.id,
    });
    if (mounted && project != null) {
      showToast(context, L10n.t('projects.create', lang),
          type: ToastType.success);
      notifier.setActiveProject(dio, project.id);
      _tabController.animateTo(0);
    } else if (mounted) {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  // ── Tasks tab ──

  Widget _buildTasksTab(ColorScheme cs, String lang) {
    final s = ref.watch(directorsProvider);

    if (s.tasksLoading && s.tasks.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (s.tasks.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.task_outlined,
                size: 48,
                color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(L10n.t('directors.noTasks', lang),
                style: TextStyle(color: cs.onSurfaceVariant)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () async {
        final dio = ref.read(authServiceProvider).authenticatedDio;
        await ref.read(directorsProvider.notifier).loadTasks(dio);
      },
      child: ListView.separated(
        padding: const EdgeInsets.only(top: 8, bottom: 16),
        itemCount: s.tasks.length,
        separatorBuilder: (_, __) => const SizedBox(height: 4),
        itemBuilder: (_, i) => _TaskRow(task: s.tasks[i], lang: lang),
      ),
    );
  }

  // ── Activity tab ──

  Widget _buildActivityTab(ColorScheme cs, String lang) {
    final s = ref.watch(directorsProvider);

    if (s.activityLoading && s.activity.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (s.activity.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.timeline_outlined,
                size: 48,
                color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(L10n.t('directors.activityEmpty', lang),
                style: TextStyle(color: cs.onSurfaceVariant)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () async {
        final dio = ref.read(authServiceProvider).authenticatedDio;
        await ref.read(directorsProvider.notifier).loadActivity(dio);
      },
      child: ListView.separated(
        padding: const EdgeInsets.only(top: 8, bottom: 16),
        itemCount: s.activity.length,
        separatorBuilder: (_, __) => const Divider(height: 1, indent: 56),
        itemBuilder: (_, i) =>
            _ActivityRow(item: s.activity[i], lang: lang),
      ),
    );
  }
}

// ── Stats header ──

class _StatsHeader extends StatelessWidget {
  final DirectorStats stats;
  final String lang;

  const _StatsHeader({required this.stats, required this.lang});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      child: Row(
        children: [
          _StatCard(
            icon: Icons.hourglass_empty,
            count: stats.pending,
            label: L10n.t('directors.statsPending', lang),
            color: Colors.orange,
            cs: cs,
          ),
          const SizedBox(width: 8),
          _StatCard(
            icon: Icons.play_circle_outline,
            count: stats.running,
            label: L10n.t('directors.statsRunning', lang),
            color: cs.primary,
            cs: cs,
          ),
          const SizedBox(width: 8),
          _StatCard(
            icon: Icons.check_circle_outline,
            count: stats.completed,
            label: L10n.t('directors.statsCompleted', lang),
            color: Colors.green,
            cs: cs,
          ),
          const SizedBox(width: 8),
          _StatCard(
            icon: Icons.error_outline,
            count: stats.failed,
            label: L10n.t('directors.statsFailed', lang),
            color: cs.error,
            cs: cs,
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final int count;
  final String label;
  final Color color;
  final ColorScheme cs;

  const _StatCard({
    required this.icon,
    required this.count,
    required this.label,
    required this.color,
    required this.cs,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(height: 4),
            Text('$count',
                style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: color)),
            Text(label,
                style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant),
                overflow: TextOverflow.ellipsis),
          ],
        ),
      ),
    );
  }
}

// ── Activity row ──

class _ActivityRow extends StatelessWidget {
  final ActivityItem item;
  final String lang;

  const _ActivityRow({required this.item, required this.lang});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    IconData icon;
    Color iconColor;
    String title;
    String subtitle;

    switch (item.type) {
      case 'director_run':
        icon = item.success == true
            ? Icons.check_circle_outline
            : Icons.error_outline;
        iconColor = item.success == true ? Colors.green : cs.error;
        title =
            '${item.emoji ?? ''} ${item.directorName ?? item.directorId ?? ''}'
                .trim();
        subtitle = item.preview?.isNotEmpty == true
            ? item.preview!
            : (item.success == true
                ? L10n.t('directors.statsCompleted', lang)
                : L10n.t('directors.statsFailed', lang));
      case 'inbox_item':
        icon = Icons.inbox_outlined;
        iconColor = cs.primary;
        title = item.title ?? '';
        subtitle = item.directorName ?? '';
      case 'task':
        icon = Icons.task_outlined;
        iconColor = switch (item.status) {
          'completed' => Colors.green,
          'running' => cs.primary,
          'failed' => cs.error,
          _ => Colors.orange,
        };
        title = item.title ?? '';
        subtitle = '${item.creatorId ?? ''} → ${item.assigneeId ?? ''}';
      default:
        icon = Icons.circle_outlined;
        iconColor = cs.onSurfaceVariant;
        title = item.type;
        subtitle = '';
    }

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: iconColor.withValues(alpha: 0.15),
        child: Icon(icon, size: 20, color: iconColor),
      ),
      title: Text(title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 14)),
      subtitle: Text(subtitle,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
      trailing: Text(
        _formatTimestamp(item.timestamp),
        style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
      ),
      dense: true,
    );
  }

  String _formatTimestamp(double ts) {
    final dt = DateTime.fromMillisecondsSinceEpoch((ts * 1000).toInt());
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m';
    if (diff.inHours < 24) return '${diff.inHours}h';
    return '${diff.inDays}d';
  }
}

// ── Director card (compact, navigates to detail) ──

class _DirectorCard extends StatelessWidget {
  final Director director;
  final String lang;
  final bool isRunning;
  final VoidCallback onToggle;
  final VoidCallback onRun;
  final VoidCallback onDelete;
  final VoidCallback onTap;

  const _DirectorCard({
    required this.director,
    required this.lang,
    required this.isRunning,
    required this.onToggle,
    required this.onRun,
    required this.onDelete,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final d = director;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Card(
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: d.enabled
              ? BorderSide(
                  color: cs.primary.withValues(alpha: 0.3), width: 1)
              : BorderSide.none,
        ),
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
                      child:
                          Text(d.emoji, style: const TextStyle(fontSize: 24)),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(d.name,
                                    style: TextStyle(
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15,
                                      color: d.enabled
                                          ? cs.onSurface
                                          : cs.onSurfaceVariant,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis),
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
                                fontSize: 12, color: cs.onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                    Switch(
                        value: d.enabled, onChanged: (_) => onToggle()),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.play_arrow,
                        size: 14, color: cs.onSurfaceVariant),
                    const SizedBox(width: 4),
                    Text(
                        L10n.t(
                            'directors.runs', lang, {'n': '${d.runCount}'}),
                        style: TextStyle(
                            fontSize: 12, color: cs.onSurfaceVariant)),
                    const SizedBox(width: 16),
                    Icon(Icons.attach_money,
                        size: 14, color: cs.onSurfaceVariant),
                    const SizedBox(width: 2),
                    Text('\$${d.totalCost.toStringAsFixed(4)}',
                        style: TextStyle(
                            fontSize: 12, color: cs.onSurfaceVariant)),
                    if (d.canDelegate) ...[
                      const SizedBox(width: 16),
                      Icon(Icons.call_split, size: 14, color: cs.primary),
                      const SizedBox(width: 4),
                      Text(L10n.t('directors.canDelegate', lang),
                          style:
                              TextStyle(fontSize: 12, color: cs.primary)),
                    ],
                    const Spacer(),
                    if (d.enabled)
                      SizedBox(
                        height: 30,
                        child: FilledButton.tonalIcon(
                          onPressed: isRunning ? null : onRun,
                          icon: isRunning
                              ? const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2))
                              : const Icon(Icons.play_arrow, size: 16),
                          label: Text(L10n.t('directors.runNow', lang),
                              style: const TextStyle(fontSize: 12)),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Template card ──

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
            borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                    shape: BoxShape.circle, color: cs.primaryContainer),
                alignment: Alignment.center,
                child: Text(t.emoji, style: const TextStyle(fontSize: 24)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(t.name,
                        style: TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 15,
                            color: cs.onSurface)),
                    if (t.description.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(t.description,
                          style: TextStyle(
                              fontSize: 12, color: cs.onSurfaceVariant),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis),
                    ],
                    if (t.defaultSchedule.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(children: [
                        Icon(Icons.schedule,
                            size: 12, color: cs.onSurfaceVariant),
                        const SizedBox(width: 4),
                        Text(t.defaultSchedule,
                            style: TextStyle(
                                fontSize: 11, color: cs.onSurfaceVariant)),
                      ]),
                    ],
                  ],
                ),
              ),
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

// ── Team template card ──

class _TeamTemplateCard extends StatefulWidget {
  final TeamTemplate team;
  final String lang;
  final VoidCallback onCreateProject;

  const _TeamTemplateCard({
    required this.team,
    required this.lang,
    required this.onCreateProject,
  });

  @override
  State<_TeamTemplateCard> createState() => _TeamTemplateCardState();
}

class _TeamTemplateCardState extends State<_TeamTemplateCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final team = widget.team;
    final lang = widget.lang;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Card(
        elevation: 1,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16)),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: cs.tertiaryContainer,
                    ),
                    alignment: Alignment.center,
                    child: Text(team.emoji,
                        style: const TextStyle(fontSize: 24)),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text(team.name,
                                  style: TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 15,
                                    color: cs.onSurface,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: cs.tertiaryContainer,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.group, size: 12,
                                      color: cs.onTertiaryContainer),
                                  const SizedBox(width: 4),
                                  Text(
                                    L10n.t('directors.teamDirectors', lang,
                                        {'count': '${team.directors.length}'}),
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w600,
                                      color: cs.onTertiaryContainer,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        if (team.description.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(team.description,
                              style: TextStyle(
                                  fontSize: 12, color: cs.onSurfaceVariant),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
            // Action buttons
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
              child: Row(
                children: [
                  TextButton.icon(
                    onPressed: () => setState(() => _expanded = !_expanded),
                    icon: Icon(
                      _expanded
                          ? Icons.expand_less
                          : Icons.expand_more,
                      size: 18,
                    ),
                    label: Text(
                      _expanded
                          ? L10n.t('agent.hide', lang)
                          : L10n.t('agent.details', lang),
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                  const Spacer(),
                  FilledButton.icon(
                    onPressed: widget.onCreateProject,
                    icon: const Icon(Icons.create_new_folder_outlined, size: 18),
                    label: Text(L10n.t('directors.createProject', lang)),
                  ),
                ],
              ),
            ),
            // Expanded director details
            if (_expanded && team.directorDetails.isNotEmpty)
              Container(
                decoration: BoxDecoration(
                  color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
                  borderRadius: const BorderRadius.vertical(
                      bottom: Radius.circular(16)),
                ),
                child: Column(
                  children: [
                    const Divider(height: 1),
                    ...team.directorDetails.map((dir) => Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 6),
                          child: Row(
                            children: [
                              Text(dir.emoji,
                                  style: const TextStyle(fontSize: 18)),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    Text(dir.name,
                                        style: TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.w500,
                                            color: cs.onSurface)),
                                    if (dir.description.isNotEmpty)
                                      Text(dir.description,
                                          style: TextStyle(
                                              fontSize: 11,
                                              color: cs.onSurfaceVariant),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis),
                                  ],
                                ),
                              ),
                              if (dir.defaultSchedule.isNotEmpty) ...[
                                Icon(Icons.schedule,
                                    size: 12, color: cs.onSurfaceVariant),
                                const SizedBox(width: 4),
                                Text(dir.defaultSchedule,
                                    style: TextStyle(
                                        fontSize: 11,
                                        color: cs.onSurfaceVariant)),
                              ],
                            ],
                          ),
                        )),
                    const SizedBox(height: 6),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// ── Task row ──

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
          side: BorderSide(
              color: cs.outlineVariant.withValues(alpha: 0.3)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Container(
                width: 10,
                height: 10,
                decoration:
                    BoxDecoration(shape: BoxShape.circle, color: statusColor),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(task.title,
                        style: TextStyle(
                            fontWeight: FontWeight.w500,
                            fontSize: 14,
                            color: cs.onSurface),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 2),
                    Text('${task.taskType} • ${task.status}',
                        style: TextStyle(
                            fontSize: 12, color: cs.onSurfaceVariant)),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: task.priority <= 3
                      ? cs.errorContainer
                      : cs.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text('P${task.priority}',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: task.priority <= 3
                          ? cs.onErrorContainer
                          : cs.onSurfaceVariant,
                    )),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Team run progress widget ──

class _TeamRunProgress extends StatelessWidget {
  final ActiveTeamRun run;
  final String lang;
  final VoidCallback onDismiss;

  const _TeamRunProgress({
    required this.run,
    required this.lang,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final entries = run.directors.values.toList();
    final pct = run.total > 0 ? run.doneCount / run.total : 0.0;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: cs.primary.withValues(alpha: 0.3)),
      ),
      color: cs.primary.withValues(alpha: 0.05),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 8, 0),
            child: Row(
              children: [
                if (run.allDone)
                  Icon(Icons.check_circle, size: 18, color: Colors.green)
                else
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: cs.primary,
                    ),
                  ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    run.allDone
                        ? L10n.t('directors.teamRunFinished', lang, {
                            'name': run.projectName,
                            'success':
                                '${entries.where((d) => d.status == DirectorRunStatus.completed).length}',
                            'failed':
                                '${entries.where((d) => d.status == DirectorRunStatus.failed).length}',
                          })
                        : L10n.t('directors.teamRunning', lang),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: cs.onSurface,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (run.allDone)
                  IconButton(
                    onPressed: onDismiss,
                    icon: Icon(Icons.close, size: 18, color: cs.onSurfaceVariant),
                    tooltip: L10n.t('directors.dismissProgress', lang),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
          ),

          // Progress bar
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 8, 14, 0),
            child: Column(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: pct,
                    minHeight: 6,
                    backgroundColor: cs.surfaceContainerHighest,
                    color: cs.primary,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      L10n.t('directors.teamProgress', lang, {
                        'completed': '${run.doneCount}',
                        'total': '${run.total}',
                      }),
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurfaceVariant),
                    ),
                    if (run.completedTasks > 0)
                      Text(
                        L10n.t('directors.teamProgressTasks', lang, {
                          'count': '${run.completedTasks}',
                        }),
                        style: TextStyle(
                            fontSize: 12, color: cs.onSurfaceVariant),
                      ),
                  ],
                ),
              ],
            ),
          ),

          // Director list
          if (entries.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 12),
              child: Column(
                children: entries
                    .map((d) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Row(
                            children: [
                              _StatusDot(status: d.status, cs: cs),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  d.name,
                                  style: TextStyle(
                                      fontSize: 13, color: cs.onSurface),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              Text(
                                _statusLabel(d.status, lang),
                                style: TextStyle(
                                    fontSize: 12,
                                    color: cs.onSurfaceVariant),
                              ),
                            ],
                          ),
                        ))
                    .toList(),
              ),
            ),
        ],
      ),
    );
  }

  String _statusLabel(DirectorRunStatus status, String lang) {
    return switch (status) {
      DirectorRunStatus.running => L10n.t('directors.runningDirector', lang),
      DirectorRunStatus.completed =>
        L10n.t('directors.completedDirector', lang),
      DirectorRunStatus.failed => L10n.t('directors.failedDirector', lang),
      DirectorRunStatus.pending => L10n.t('directors.pendingDirector', lang),
    };
  }
}

class _StatusDot extends StatelessWidget {
  final DirectorRunStatus status;
  final ColorScheme cs;

  const _StatusDot({required this.status, required this.cs});

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      DirectorRunStatus.pending => cs.onSurfaceVariant.withValues(alpha: 0.4),
      DirectorRunStatus.running => cs.primary,
      DirectorRunStatus.completed => Colors.green,
      DirectorRunStatus.failed => cs.error,
    };

    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
      ),
    );
  }
}

// ── Create director bottom sheet ──

class _CreateDirectorSheet extends StatefulWidget {
  final String lang;
  final DirectorTemplate? template;
  final List<DirectorProject> projects;
  final String activeProjectId;
  final Future<void> Function(Map<String, dynamic> data) onCreated;

  const _CreateDirectorSheet({
    required this.lang,
    this.template,
    this.projects = const [],
    this.activeProjectId = '',
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
  late String _selectedProjectId;

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
    _selectedProjectId = widget.activeProjectId;
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
    if (_selectedProjectId.isNotEmpty) {
      data['project_id'] = _selectedProjectId;
    }
    final schedule = _scheduleCtrl.text.trim();
    if (schedule.isNotEmpty) data['schedule'] = schedule;

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
              Text(L10n.t('directors.createTitle', lang),
                  style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: cs.onSurface)),
              const SizedBox(height: 20),
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
              TextFormField(
                controller: _descCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('directors.description', lang),
                  border: const OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 14),
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
                validator: (v) => (v == null || v.trim().length < 20)
                    ? L10n.t('directors.rolePromptHint', lang)
                    : null,
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _scheduleCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('directors.schedule', lang),
                  hintText: L10n.t('directors.scheduleHint', lang),
                  border: const OutlineInputBorder(),
                ),
                validator: (v) => validateCron(v, lang),
              ),
              if (widget.projects.isNotEmpty) ...[
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  initialValue: _selectedProjectId.isEmpty ? null : _selectedProjectId,
                  decoration: InputDecoration(
                    labelText: L10n.t('projects.title', lang),
                    border: const OutlineInputBorder(),
                  ),
                  isExpanded: true,
                  items: [
                    DropdownMenuItem<String>(
                      value: null,
                      child: Text(L10n.t('projects.defaultProject', lang),
                          style: TextStyle(color: cs.onSurfaceVariant)),
                    ),
                    ...widget.projects.map((p) => DropdownMenuItem<String>(
                          value: p.id,
                          child: Row(
                            children: [
                              Text(p.emoji,
                                  style: const TextStyle(fontSize: 16)),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(p.name,
                                    overflow: TextOverflow.ellipsis),
                              ),
                            ],
                          ),
                        )),
                  ],
                  onChanged: (v) =>
                      setState(() => _selectedProjectId = v ?? ''),
                ),
              ],
              const SizedBox(height: 10),
              SwitchListTile(
                title: Text(L10n.t('directors.canDelegate', lang),
                    style: const TextStyle(fontSize: 14)),
                value: _canDelegate,
                onChanged: (v) => setState(() => _canDelegate = v),
                contentPadding: EdgeInsets.zero,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _saving
                          ? null
                          : () => Navigator.of(context).pop(),
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
                              child: CircularProgressIndicator(
                                  strokeWidth: 2))
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

// ── Create project bottom sheet ──

class _CreateProjectSheet extends StatefulWidget {
  final String lang;
  final List<TeamTemplate> teamTemplates;
  final Future<void> Function(Map<String, dynamic> data) onCreated;

  const _CreateProjectSheet({
    required this.lang,
    required this.teamTemplates,
    required this.onCreated,
  });

  @override
  State<_CreateProjectSheet> createState() => _CreateProjectSheetState();
}

class _CreateProjectSheetState extends State<_CreateProjectSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _emojiCtrl;
  late final TextEditingController _nameCtrl;
  late final TextEditingController _descCtrl;
  String? _selectedTemplate;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _emojiCtrl = TextEditingController(text: '\u{1F4C1}');
    _nameCtrl = TextEditingController();
    _descCtrl = TextEditingController();
  }

  @override
  void dispose() {
    _emojiCtrl.dispose();
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  void _onTemplateChanged(String? value) {
    setState(() => _selectedTemplate = value);
    if (value == null) return;
    final tmpl = widget.teamTemplates.cast<TeamTemplate?>().firstWhere(
          (t) => t!.id == value,
          orElse: () => null,
        );
    if (tmpl == null) return;
    if (_nameCtrl.text.isEmpty) _nameCtrl.text = tmpl.name;
    if (_emojiCtrl.text == '\u{1F4C1}') _emojiCtrl.text = tmpl.emoji;
    if (_descCtrl.text.isEmpty) _descCtrl.text = tmpl.description;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);

    final data = <String, dynamic>{
      'name': _nameCtrl.text.trim(),
      'emoji': _emojiCtrl.text.trim(),
      'description': _descCtrl.text.trim(),
    };
    if (_selectedTemplate != null) data['team_template'] = _selectedTemplate;

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
              Text(L10n.t('projects.create', lang),
                  style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: cs.onSurface)),
              const SizedBox(height: 20),
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
                        labelText: L10n.t('projects.name', lang),
                        border: const OutlineInputBorder(),
                      ),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? '' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _descCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('projects.description', lang),
                  border: const OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                initialValue: _selectedTemplate,
                decoration: InputDecoration(
                  labelText: L10n.t('projects.teamTemplate', lang),
                  border: const OutlineInputBorder(),
                ),
                isExpanded: true,
                items: [
                  DropdownMenuItem<String>(
                    value: null,
                    child: Text(L10n.t('projects.emptyTemplate', lang),
                        style: TextStyle(color: cs.onSurfaceVariant)),
                  ),
                  ...widget.teamTemplates
                      .where((t) => t.directors.isNotEmpty)
                      .map((t) => DropdownMenuItem<String>(
                            value: t.id,
                            child: Row(
                              children: [
                                Text(t.emoji,
                                    style: const TextStyle(fontSize: 18)),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(t.name,
                                          style: const TextStyle(
                                              fontSize: 14)),
                                      Text(
                                        L10n.t('projects.directors', lang,
                                            {'n': '${t.directors.length}'}),
                                        style: TextStyle(
                                            fontSize: 11,
                                            color: cs.onSurfaceVariant),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          )),
                ],
                onChanged: _onTemplateChanged,
              ),
              const SizedBox(height: 16),
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
                              child: CircularProgressIndicator(
                                  strokeWidth: 2))
                          : Text(L10n.t('projects.create', lang)),
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
