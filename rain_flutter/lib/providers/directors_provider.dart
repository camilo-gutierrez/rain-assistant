import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/director.dart';

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
      );
}

class DirectorsNotifier extends StateNotifier<DirectorsState> {
  DirectorsNotifier() : super(const DirectorsState());

  // ── Directors ──

  Future<void> loadDirectors(Dio dio) async {
    state = state.copyWith(
        directorsLoading: true, clearDirectorsError: true);
    try {
      final res = await dio.get('/directors');
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
      final res = await dio.get('/directors/stats');
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
      final res = await dio.get('/directors/tasks');
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
      final res = await dio.get('/directors/activity',
          queryParameters: {'limit': limit});
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
}

final directorsProvider =
    StateNotifierProvider<DirectorsNotifier, DirectorsState>((ref) {
  return DirectorsNotifier();
});
