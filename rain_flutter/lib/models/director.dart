/// Models for the Autonomous Directors system.

class Director {
  final String id;
  final String name;
  final String emoji;
  final String description;
  final String rolePrompt;
  final String? schedule;
  final bool enabled;
  final bool canDelegate;
  final String permissionLevel;
  final int runCount;
  final double totalCost;
  final double? lastRun;
  final double? nextRun;
  final String? lastResult;
  final String? lastError;
  final double createdAt;
  final double updatedAt;

  const Director({
    required this.id,
    required this.name,
    this.emoji = '\u{1F916}',
    this.description = '',
    required this.rolePrompt,
    this.schedule,
    this.enabled = true,
    this.canDelegate = false,
    this.permissionLevel = 'green',
    this.runCount = 0,
    this.totalCost = 0.0,
    this.lastRun,
    this.nextRun,
    this.lastResult,
    this.lastError,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Director.fromJson(Map<String, dynamic> json) => Director(
        id: json['id'] as String,
        name: json['name'] as String,
        emoji: (json['emoji'] as String?) ?? '\u{1F916}',
        description: (json['description'] as String?) ?? '',
        rolePrompt: (json['role_prompt'] as String?) ?? '',
        schedule: json['schedule'] as String?,
        enabled: json['enabled'] == 1 || json['enabled'] == true,
        canDelegate: json['can_delegate'] == 1 || json['can_delegate'] == true,
        permissionLevel: (json['permission_level'] as String?) ?? 'green',
        runCount: (json['run_count'] as num?)?.toInt() ?? 0,
        totalCost: (json['total_cost'] as num?)?.toDouble() ?? 0.0,
        lastRun: (json['last_run'] as num?)?.toDouble(),
        nextRun: (json['next_run'] as num?)?.toDouble(),
        lastResult: json['last_result'] as String?,
        lastError: json['last_error'] as String?,
        createdAt: (json['created_at'] as num).toDouble(),
        updatedAt: (json['updated_at'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'emoji': emoji,
        'description': description,
        'role_prompt': rolePrompt,
        'schedule': schedule,
        'enabled': enabled,
        'can_delegate': canDelegate,
        'permission_level': permissionLevel,
      };
}

class DirectorTask {
  final String id;
  final String title;
  final String description;
  final String creatorId;
  final String? assigneeId;
  final String status;
  final int priority;
  final String taskType;
  final String? claimedBy;
  final String? errorMessage;
  final double createdAt;
  final double updatedAt;
  final double? claimedAt;
  final double? completedAt;

  const DirectorTask({
    required this.id,
    required this.title,
    this.description = '',
    required this.creatorId,
    this.assigneeId,
    this.status = 'pending',
    this.priority = 5,
    this.taskType = 'analysis',
    this.claimedBy,
    this.errorMessage,
    required this.createdAt,
    required this.updatedAt,
    this.claimedAt,
    this.completedAt,
  });

  factory DirectorTask.fromJson(Map<String, dynamic> json) => DirectorTask(
        id: json['id'] as String,
        title: json['title'] as String,
        description: (json['description'] as String?) ?? '',
        creatorId: json['creator_id'] as String,
        assigneeId: json['assignee_id'] as String?,
        status: (json['status'] as String?) ?? 'pending',
        priority: (json['priority'] as num?)?.toInt() ?? 5,
        taskType: (json['task_type'] as String?) ?? 'analysis',
        claimedBy: json['claimed_by'] as String?,
        errorMessage: json['error_message'] as String?,
        createdAt: (json['created_at'] as num).toDouble(),
        updatedAt: (json['updated_at'] as num).toDouble(),
        claimedAt: (json['claimed_at'] as num?)?.toDouble(),
        completedAt: (json['completed_at'] as num?)?.toDouble(),
      );
}

class InboxItem {
  final String id;
  final String directorId;
  final String directorName;
  final String title;
  final String content;
  final String contentType;
  final String status;
  final int priority;
  final String? taskId;
  final String? userComment;
  final double createdAt;
  final double updatedAt;

  const InboxItem({
    required this.id,
    required this.directorId,
    required this.directorName,
    required this.title,
    required this.content,
    this.contentType = 'report',
    this.status = 'unread',
    this.priority = 5,
    this.taskId,
    this.userComment,
    required this.createdAt,
    required this.updatedAt,
  });

  factory InboxItem.fromJson(Map<String, dynamic> json) => InboxItem(
        id: json['id'] as String,
        directorId: json['director_id'] as String,
        directorName: json['director_name'] as String,
        title: json['title'] as String,
        content: (json['content'] as String?) ?? '',
        contentType: (json['content_type'] as String?) ?? 'report',
        status: (json['status'] as String?) ?? 'unread',
        priority: (json['priority'] as num?)?.toInt() ?? 5,
        taskId: json['task_id'] as String?,
        userComment: json['user_comment'] as String?,
        createdAt: (json['created_at'] as num).toDouble(),
        updatedAt: (json['updated_at'] as num).toDouble(),
      );
}

class DirectorTemplate {
  final String id;
  final String name;
  final String emoji;
  final String description;
  final String rolePrompt;
  final String defaultSchedule;
  final bool canDelegate;

  const DirectorTemplate({
    required this.id,
    required this.name,
    this.emoji = '\u{1F916}',
    this.description = '',
    required this.rolePrompt,
    this.defaultSchedule = '',
    this.canDelegate = false,
  });

  factory DirectorTemplate.fromJson(Map<String, dynamic> json) =>
      DirectorTemplate(
        id: json['id'] as String,
        name: json['name'] as String,
        emoji: (json['emoji'] as String?) ?? '\u{1F916}',
        description: (json['description'] as String?) ?? '',
        rolePrompt: (json['role_prompt'] as String?) ?? '',
        defaultSchedule: (json['default_schedule'] as String?) ?? '',
        canDelegate: json['can_delegate'] == true,
      );
}

class DirectorStats {
  final int pending;
  final int running;
  final int completed;
  final int failed;
  final int cancelled;
  final int total;
  final int inboxUnread;

  const DirectorStats({
    this.pending = 0,
    this.running = 0,
    this.completed = 0,
    this.failed = 0,
    this.cancelled = 0,
    this.total = 0,
    this.inboxUnread = 0,
  });

  factory DirectorStats.fromJson(Map<String, dynamic> json) {
    final ts = json['task_stats'] as Map<String, dynamic>? ?? {};
    return DirectorStats(
      pending: (ts['pending'] as num?)?.toInt() ?? 0,
      running: (ts['running'] as num?)?.toInt() ?? 0,
      completed: (ts['completed'] as num?)?.toInt() ?? 0,
      failed: (ts['failed'] as num?)?.toInt() ?? 0,
      cancelled: (ts['cancelled'] as num?)?.toInt() ?? 0,
      total: (ts['total'] as num?)?.toInt() ?? 0,
      inboxUnread: (json['inbox_unread'] as num?)?.toInt() ?? 0,
    );
  }
}

class ActivityItem {
  final String type;
  final String? directorId;
  final String? directorName;
  final String? emoji;
  final String? title;
  final String? preview;
  final String? status;
  final String? contentType;
  final String? taskId;
  final String? creatorId;
  final String? assigneeId;
  final double timestamp;
  final bool? success;

  const ActivityItem({
    required this.type,
    this.directorId,
    this.directorName,
    this.emoji,
    this.title,
    this.preview,
    this.status,
    this.contentType,
    this.taskId,
    this.creatorId,
    this.assigneeId,
    required this.timestamp,
    this.success,
  });

  factory ActivityItem.fromJson(Map<String, dynamic> json) => ActivityItem(
        type: json['type'] as String,
        directorId: json['director_id'] as String?,
        directorName: json['director_name'] as String?,
        emoji: json['emoji'] as String?,
        title: json['title'] as String?,
        preview: json['preview'] as String?,
        status: json['status'] as String?,
        contentType: json['content_type'] as String?,
        taskId: json['task_id'] as String?,
        creatorId: json['creator_id'] as String?,
        assigneeId: json['assignee_id'] as String?,
        timestamp: (json['timestamp'] as num?)?.toDouble() ?? 0.0,
        success: json['success'] as bool?,
      );
}
