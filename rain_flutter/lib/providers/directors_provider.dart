import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/director.dart';

/// Status of a single director during a team run.
enum DirectorRunStatus { pending, running, completed, failed }

/// A director entry in the active team run.
class DirectorRunEntry {
  final String id;
  final String name;
  final DirectorRunStatus status;

  const DirectorRunEntry({
    required this.id,
    required this.name,
    this.status = DirectorRunStatus.pending,
  });

  DirectorRunEntry copyWith({DirectorRunStatus? status}) =>
      DirectorRunEntry(id: id, name: name, status: status ?? this.status);
}

/// Tracks the state of an active team run.
class ActiveTeamRun {
  final String projectId;
  final String projectName;
  final int directorCount;
  final Map<String, DirectorRunEntry> directors;
  final int completedTasks;
  final DateTime startedAt;

  const ActiveTeamRun({
    required this.projectId,
    required this.projectName,
    required this.directorCount,
    this.directors = const {},
    this.completedTasks = 0,
    required this.startedAt,
  });

  ActiveTeamRun copyWith({
    Map<String, DirectorRunEntry>? directors,
    int? completedTasks,
  }) =>
      ActiveTeamRun(
        projectId: projectId,
        projectName: projectName,
        directorCount: directorCount,
        directors: directors ?? this.directors,
        completedTasks: completedTasks ?? this.completedTasks,
        startedAt: startedAt,
      );

  int get doneCount => directors.values
      .where((d) =>
          d.status == DirectorRunStatus.completed ||
          d.status == DirectorRunStatus.failed)
      .length;

  int get total => directorCount > directors.length ? directorCount : directors.length;

  bool get allDone => total > 0 && doneCount >= total;
}

class DirectorsState {
  final List<Director> directors;
  final List<InboxItem> inboxItems;
  final List<DirectorTask> tasks;
  final List<DirectorTemplate> templates;
  final int unreadCount;
  final DirectorStats? stats;
  final List<ActivityItem> activity;
  final bool directorsLoading;
  final bool inboxLoading;
  final bool tasksLoading;
  final bool templatesLoading;
  final bool activityLoading;
  final String? directorsError;
  final String? inboxError;
  final Set<String> runningIds;
  // Projects
  final List<DirectorProject> projects;
  final List<TeamTemplate> teamTemplates;
  final String activeProjectId;
  final bool projectsLoading;
  final bool teamTemplatesLoading;
  final bool teamRunning;
  // Team run progress
  final ActiveTeamRun? activeTeamRun;

  const DirectorsState({
    this.directors = const [],
    this.inboxItems = const [],
    this.tasks = const [],
    this.templates = const [],
    this.unreadCount = 0,
    this.stats,
    this.activity = const [],
    this.directorsLoading = false,
    this.inboxLoading = false,
    this.tasksLoading = false,
    this.templatesLoading = false,
    this.activityLoading = false,
    this.directorsError,
    this.inboxError,
    this.runningIds = const {},
    this.projects = const [],
    this.teamTemplates = const [],
    this.activeProjectId = '',
    this.projectsLoading = false,
    this.teamTemplatesLoading = false,
    this.teamRunning = false,
    this.activeTeamRun,
  });

  DirectorsState copyWith({
    List<Director>? directors,
    List<InboxItem>? inboxItems,
    List<DirectorTask>? tasks,
    List<DirectorTemplate>? templates,
    int? unreadCount,
    DirectorStats? stats,
    bool clearStats = false,
    List<ActivityItem>? activity,
    bool? directorsLoading,
    bool? inboxLoading,
    bool? tasksLoading,
    bool? templatesLoading,
    bool? activityLoading,
    String? directorsError,
    bool clearDirectorsError = false,
    String? inboxError,
    bool clearInboxError = false,
    Set<String>? runningIds,
    List<DirectorProject>? projects,
    List<TeamTemplate>? teamTemplates,
    String? activeProjectId,
    bool? projectsLoading,
    bool? teamTemplatesLoading,
    bool? teamRunning,
    ActiveTeamRun? activeTeamRun,
    bool clearActiveTeamRun = false,
  }) =>
      DirectorsState(
        directors: directors ?? this.directors,
        inboxItems: inboxItems ?? this.inboxItems,
        tasks: tasks ?? this.tasks,
        templates: templates ?? this.templates,
        unreadCount: unreadCount ?? this.unreadCount,
        stats: clearStats ? null : (stats ?? this.stats),
        activity: activity ?? this.activity,
        directorsLoading: directorsLoading ?? this.directorsLoading,
        inboxLoading: inboxLoading ?? this.inboxLoading,
        tasksLoading: tasksLoading ?? this.tasksLoading,
        templatesLoading: templatesLoading ?? this.templatesLoading,
        activityLoading: activityLoading ?? this.activityLoading,
        directorsError: clearDirectorsError
            ? null
            : (directorsError ?? this.directorsError),
        inboxError:
            clearInboxError ? null : (inboxError ?? this.inboxError),
        runningIds: runningIds ?? this.runningIds,
        projects: projects ?? this.projects,
        teamTemplates: teamTemplates ?? this.teamTemplates,
        activeProjectId: activeProjectId ?? this.activeProjectId,
        projectsLoading: projectsLoading ?? this.projectsLoading,
        teamTemplatesLoading: teamTemplatesLoading ?? this.teamTemplatesLoading,
        teamRunning: teamRunning ?? this.teamRunning,
        activeTeamRun: clearActiveTeamRun
            ? null
            : (activeTeamRun ?? this.activeTeamRun),
      );
}

class DirectorsNotifier extends StateNotifier<DirectorsState> {
  DirectorsNotifier() : super(const DirectorsState());

  String get _projectParam => state.activeProjectId.isNotEmpty
      ? state.activeProjectId
      : '';

  // ── Projects ──

  Future<void> loadProjects(Dio dio) async {
    state = state.copyWith(projectsLoading: true);
    try {
      final res = await dio.get('/directors/projects');
      final list = (res.data['projects'] as List? ?? [])
          .map((e) => DirectorProject.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(projects: list, projectsLoading: false);
    } catch (_) {
      state = state.copyWith(projectsLoading: false);
    }
  }

  Future<void> loadTeamTemplates(Dio dio) async {
    state = state.copyWith(teamTemplatesLoading: true);
    try {
      final res = await dio.get('/directors/team-templates');
      final list = (res.data['team_templates'] as List? ?? [])
          .map((e) => TeamTemplate.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(teamTemplates: list, teamTemplatesLoading: false);
    } catch (_) {
      state = state.copyWith(teamTemplatesLoading: false);
    }
  }

  Future<DirectorProject?> createProject(Dio dio, Map<String, dynamic> data) async {
    try {
      final res = await dio.post('/directors/projects', data: data);
      final project = DirectorProject.fromJson(res.data['project'] as Map<String, dynamic>);
      await loadProjects(dio);
      return project;
    } catch (_) {
      return null;
    }
  }

  Future<bool> deleteProject(Dio dio, String projectId) async {
    try {
      await dio.delete('/directors/projects/$projectId');
      await loadProjects(dio);
      if (state.activeProjectId == projectId) {
        setActiveProject(dio, '');
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  void setActiveProject(Dio dio, String projectId) {
    state = state.copyWith(
      activeProjectId: projectId,
      directors: const [],
      inboxItems: const [],
      tasks: const [],
      activity: const [],
      clearStats: true,
    );
    loadDirectors(dio);
    loadStats(dio);
    loadInbox(dio);
    loadTasks(dio);
    loadActivity(dio);
  }

  // ── Directors ──

  Future<void> loadDirectors(Dio dio) async {
    state = state.copyWith(
        directorsLoading: true, clearDirectorsError: true);
    try {
      final params = <String, dynamic>{};
      if (_projectParam.isNotEmpty) params['project_id'] = _projectParam;
      final res = await dio.get('/directors', queryParameters: params);
      final list = (res.data['directors'] as List? ?? [])
          .map((e) => Director.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(directors: list, directorsLoading: false);
    } catch (e) {
      state = state.copyWith(
          directorsError: e.toString(), directorsLoading: false);
    }
  }

  Future<void> loadStats(Dio dio) async {
    try {
      final params = <String, dynamic>{};
      if (_projectParam.isNotEmpty) params['project_id'] = _projectParam;
      final res = await dio.get('/directors/stats', queryParameters: params);
      final stats = DirectorStats.fromJson(res.data as Map<String, dynamic>);
      state = state.copyWith(stats: stats, unreadCount: stats.inboxUnread);
    } catch (_) {}
  }

  Future<bool> createDirector(Dio dio, Map<String, dynamic> data) async {
    try {
      await dio.post('/directors', data: data);
      await loadDirectors(dio);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> toggleEnabled(Dio dio, Director d) async {
    final endpoint =
        d.enabled ? '/directors/${d.id}/disable' : '/directors/${d.id}/enable';
    try {
      await dio.post(endpoint);
      await loadDirectors(dio);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> runNow(Dio dio, Director d) async {
    state = state.copyWith(runningIds: {...state.runningIds, d.id});
    try {
      await dio.post('/directors/${d.id}/run');
      return true;
    } catch (_) {
      return false;
    } finally {
      state = state.copyWith(
          runningIds: Set.from(state.runningIds)..remove(d.id));
    }
  }

  Future<bool> runProject(Dio dio, String projectId) async {
    state = state.copyWith(teamRunning: true);
    try {
      final res = await dio.post('/directors/projects/$projectId/run');
      // Initialize team run progress from HTTP response
      if (state.activeTeamRun == null) {
        final dirsList = (res.data['directors'] as List? ?? []);
        final project = state.projects.cast<DirectorProject?>().firstWhere(
              (p) => p!.id == projectId,
              orElse: () => null,
            );
        final entries = <String, DirectorRunEntry>{};
        for (var i = 0; i < dirsList.length; i++) {
          final d = dirsList[i] as Map<String, dynamic>;
          final id = d['id'] as String? ?? '';
          entries[id] = DirectorRunEntry(
            id: id,
            name: d['name'] as String? ?? '',
            // First director starts running (sequential execution)
            status: i == 0
                ? DirectorRunStatus.running
                : DirectorRunStatus.pending,
          );
        }
        state = state.copyWith(
          activeTeamRun: ActiveTeamRun(
            projectId: projectId,
            projectName: project?.name ?? '',
            directorCount: dirsList.length,
            directors: entries,
            startedAt: DateTime.now(),
          ),
        );
      }
      return true;
    } catch (_) {
      state = state.copyWith(teamRunning: false);
      return false;
    }
  }

  Future<bool> deleteDirector(Dio dio, Director d) async {
    try {
      await dio.delete('/directors/${d.id}');
      await loadDirectors(dio);
      return true;
    } catch (_) {
      return false;
    }
  }

  // ── Inbox ──

  Future<void> loadInbox(Dio dio, {String? filter}) async {
    state = state.copyWith(inboxLoading: true, clearInboxError: true);
    try {
      final params = <String, String>{};
      if (filter != null && filter != 'all') params['status'] = filter;
      if (_projectParam.isNotEmpty) params['project_id'] = _projectParam;
      final res =
          await dio.get('/directors/inbox', queryParameters: params);
      final list = (res.data['items'] as List? ?? [])
          .map((e) => InboxItem.fromJson(e as Map<String, dynamic>))
          .toList();
      final unread = (res.data['unread_count'] as num?)?.toInt() ?? 0;
      state = state.copyWith(
          inboxItems: list, unreadCount: unread, inboxLoading: false);
    } catch (e) {
      state =
          state.copyWith(inboxError: e.toString(), inboxLoading: false);
    }
  }

  Future<bool> updateInboxStatus(Dio dio, InboxItem item, String newStatus,
      {String? comment}) async {
    try {
      final body = <String, dynamic>{'status': newStatus};
      if (comment != null && comment.isNotEmpty) body['user_comment'] = comment;
      await dio.patch('/directors/inbox/${item.id}', data: body);
      return true;
    } catch (_) {
      return false;
    }
  }

  void markAsRead(String itemId) {
    if (state.unreadCount > 0) {
      state = state.copyWith(unreadCount: state.unreadCount - 1);
    }
  }

  void incrementUnread() {
    state = state.copyWith(unreadCount: state.unreadCount + 1);
  }

  // ── Templates ──

  Future<void> loadTemplates(Dio dio) async {
    state = state.copyWith(templatesLoading: true);
    try {
      final res = await dio.get('/directors/templates');
      final list = (res.data['templates'] as List? ?? [])
          .map((e) => DirectorTemplate.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(templates: list, templatesLoading: false);
    } catch (_) {
      state = state.copyWith(templatesLoading: false);
    }
  }

  // ── Tasks ──

  Future<void> loadTasks(Dio dio) async {
    state = state.copyWith(tasksLoading: true);
    try {
      final params = <String, dynamic>{};
      if (_projectParam.isNotEmpty) params['project_id'] = _projectParam;
      final res = await dio.get('/directors/tasks', queryParameters: params);
      final list = (res.data['tasks'] as List? ?? [])
          .map((e) => DirectorTask.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(tasks: list, tasksLoading: false);
    } catch (_) {
      state = state.copyWith(tasksLoading: false);
    }
  }

  // ── Activity ──

  Future<void> loadActivity(Dio dio, {int limit = 30}) async {
    state = state.copyWith(activityLoading: true);
    try {
      final params = <String, dynamic>{'limit': limit};
      if (_projectParam.isNotEmpty) params['project_id'] = _projectParam;
      final res = await dio.get('/directors/activity',
          queryParameters: params);
      final list = (res.data['activity'] as List? ?? [])
          .map((e) => ActivityItem.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(activity: list, activityLoading: false);
    } catch (_) {
      state = state.copyWith(activityLoading: false);
    }
  }

  // ── WebSocket events ──

  void onDirectorRunComplete(String directorId) {
    state = state.copyWith(
        runningIds: Set.from(state.runningIds)..remove(directorId));
  }

  /// Called when team_run_start event arrives via WebSocket.
  void onTeamRunStart(String projectId, String projectName, int directorCount) {
    if (state.activeTeamRun != null) return; // HTTP may have initialized it first
    state = state.copyWith(
      teamRunning: true,
      activeTeamRun: ActiveTeamRun(
        projectId: projectId,
        projectName: projectName,
        directorCount: directorCount,
        startedAt: DateTime.now(),
      ),
    );
  }

  /// Called when run_complete event arrives — a single director finished.
  void onTeamDirectorComplete(String directorId, String directorName, bool success) {
    final run = state.activeTeamRun;
    if (run == null) return;

    final dirs = Map<String, DirectorRunEntry>.from(run.directors);

    // Update or add this director
    dirs[directorId] = DirectorRunEntry(
      id: directorId,
      name: directorName,
      status: success ? DirectorRunStatus.completed : DirectorRunStatus.failed,
    );

    // Mark next pending director as running (sequential execution)
    final pending = dirs.entries
        .where((e) => e.value.status == DirectorRunStatus.pending)
        .toList();
    if (pending.isNotEmpty) {
      final nextId = pending.first.key;
      dirs[nextId] = dirs[nextId]!.copyWith(status: DirectorRunStatus.running);
    }

    state = state.copyWith(activeTeamRun: run.copyWith(directors: dirs));
  }

  /// Called when task_complete event arrives.
  void onTeamTaskComplete() {
    final run = state.activeTeamRun;
    if (run == null) return;
    state = state.copyWith(
      activeTeamRun: run.copyWith(completedTasks: run.completedTasks + 1),
    );
  }

  Timer? _autoClearTimer;

  /// Called when team_run_complete event arrives — all directors finished.
  void onTeamRunFinish() {
    final run = state.activeTeamRun;
    if (run == null) return;

    // Ensure all directors are in terminal state
    final dirs = Map<String, DirectorRunEntry>.from(run.directors);
    for (final id in dirs.keys) {
      final d = dirs[id]!;
      if (d.status == DirectorRunStatus.pending ||
          d.status == DirectorRunStatus.running) {
        dirs[id] = d.copyWith(status: DirectorRunStatus.completed);
      }
    }

    state = state.copyWith(
      teamRunning: false,
      activeTeamRun: run.copyWith(directors: dirs),
    );

    // Auto-clear after 8 seconds
    _autoClearTimer?.cancel();
    _autoClearTimer = Timer(const Duration(seconds: 8), () {
      if (state.activeTeamRun?.startedAt == run.startedAt) {
        clearTeamRun();
      }
    });
  }

  /// Manually dismiss the team run progress.
  void clearTeamRun() {
    _autoClearTimer?.cancel();
    state = state.copyWith(
      teamRunning: false,
      clearActiveTeamRun: true,
    );
  }
}

final directorsProvider =
    StateNotifierProvider<DirectorsNotifier, DirectorsState>((ref) {
  return DirectorsNotifier();
});
