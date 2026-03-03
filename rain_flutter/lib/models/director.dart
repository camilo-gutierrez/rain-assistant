// Models for the Autonomous Directors system.

import 'dart:convert';

class DirectorProject {
  final String id;
  final String name;
  final String emoji;
  final String description;
  final String color;
  final String? teamTemplate;
  final double createdAt;
  final double updatedAt;

  const DirectorProject({
    required this.id,
    required this.name,
    this.emoji = '\u{1F4C1}',
    this.description = '',
    this.color = '#6C7086',
    this.teamTemplate,
    required this.createdAt,
    required this.updatedAt,
  });

  factory DirectorProject.fromJson(Map<String, dynamic> json) =>
      DirectorProject(
        id: json['id'] as String,
        name: json['name'] as String,
        emoji: (json['emoji'] as String?) ?? '\u{1F4C1}',
        description: (json['description'] as String?) ?? '',
        color: (json['color'] as String?) ?? '#6C7086',
        teamTemplate: json['team_template'] as String?,
        createdAt: (json['created_at'] as num).toDouble(),
        updatedAt: (json['updated_at'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'emoji': emoji,
        'description': description,
        'color': color,
        'team_template': teamTemplate,
      };
}

class TeamTemplate {
  final String id;
  final String name;
  final String emoji;
  final String description;
  final String color;
  final List<String> directors;
  final List<DirectorTemplate> directorDetails;

  const TeamTemplate({
    required this.id,
    required this.name,
    this.emoji = '\u{1F4C1}',
    this.description = '',
    this.color = '#6C7086',
    this.directors = const [],
    this.directorDetails = const [],
  });

  factory TeamTemplate.fromJson(Map<String, dynamic> json) => TeamTemplate(
        id: json['id'] as String,
        name: json['name'] as String,
        emoji: (json['emoji'] as String?) ?? '\u{1F4C1}',
        description: (json['description'] as String?) ?? '',
        color: (json['color'] as String?) ?? '#6C7086',
        directors: (json['directors'] as List?)
                ?.map((e) => e as String)
                .toList() ??
            [],
        directorDetails: (json['director_details'] as List?)
                ?.map((e) => DirectorTemplate.fromJson(e as Map<String, dynamic>))
                .toList() ??
            [],
      );
}

// ---------------------------------------------------------------------------
// Context field metadata — describes a configurable context field for a director
// ---------------------------------------------------------------------------

class ContextFieldMeta {
  final String key;
  final String label;
  final String labelEs;
  final String type; // text, textarea, tags, number, select, toggle
  final String hint;
  final String hintEs;
  final bool required;
  final String defaultValue;
  final List<String> options;
  final String group;
  final bool readOnly;
  final bool autoManaged;
  final bool allowFileAttach;

  const ContextFieldMeta({
    required this.key,
    required this.label,
    this.labelEs = '',
    this.type = 'text',
    this.hint = '',
    this.hintEs = '',
    this.required = false,
    this.defaultValue = '',
    this.options = const [],
    this.group = 'general',
    this.readOnly = false,
    this.autoManaged = false,
    this.allowFileAttach = false,
  });

  factory ContextFieldMeta.fromJson(Map<String, dynamic> json) =>
      ContextFieldMeta(
        key: json['key'] as String,
        label: (json['label'] as String?) ?? '',
        labelEs: (json['label_es'] as String?) ?? '',
        type: (json['type'] as String?) ?? 'text',
        hint: (json['hint'] as String?) ?? '',
        hintEs: (json['hint_es'] as String?) ?? '',
        required: json['required'] == true,
        defaultValue: (json['default'] as String?) ?? '',
        options: (json['options'] as List?)
                ?.map((e) => e as String)
                .toList() ??
            [],
        group: (json['group'] as String?) ?? 'general',
        readOnly: json['read_only'] == true,
        autoManaged: json['auto_managed'] == true,
        allowFileAttach: json['allow_file_attach'] == true,
      );

  /// Get the label in the user's language.
  String localizedLabel(String lang) =>
      lang == 'es' && labelEs.isNotEmpty ? labelEs : label;

  /// Get the hint in the user's language.
  String localizedHint(String lang) =>
      lang == 'es' && hintEs.isNotEmpty ? hintEs : hint;
}

// ---------------------------------------------------------------------------
// Director
// ---------------------------------------------------------------------------

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
  // Context configuration
  final Map<String, dynamic> contextWindow;
  final String templateId;
  final String setupStatus; // "complete" | "needs_setup"
  final List<String> missingFields;
  final List<ContextFieldMeta> requiredContext;

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
    this.contextWindow = const {},
    this.templateId = '',
    this.setupStatus = 'complete',
    this.missingFields = const [],
    this.requiredContext = const [],
  });

  factory Director.fromJson(Map<String, dynamic> json) {
    // Parse context_window — can be a Map or a JSON string
    Map<String, dynamic> ctx = {};
    final rawCtx = json['context_window'];
    if (rawCtx is Map<String, dynamic>) {
      ctx = rawCtx;
    } else if (rawCtx is String && rawCtx.isNotEmpty) {
      try {
        ctx = jsonDecode(rawCtx) as Map<String, dynamic>;
      } catch (_) {}
    }

    return Director(
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
      contextWindow: ctx,
      templateId: (json['template_id'] as String?) ?? '',
      setupStatus: (json['setup_status'] as String?) ?? 'complete',
      missingFields: (json['missing_fields'] as List?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      requiredContext: (json['required_context'] as List?)
              ?.map(
                  (e) => ContextFieldMeta.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

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

  /// Whether this director needs the user to configure context fields.
  bool get needsSetup => setupStatus == 'needs_setup';
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
  final List<ContextFieldMeta> requiredContext;

  const DirectorTemplate({
    required this.id,
    required this.name,
    this.emoji = '\u{1F916}',
    this.description = '',
    required this.rolePrompt,
    this.defaultSchedule = '',
    this.canDelegate = false,
    this.requiredContext = const [],
  });

  factory DirectorTemplate.fromJson(Map<String, dynamic> json) =>
      DirectorTemplate(
        id: json['id'] as String,
        name: json['name'] as String,
        emoji: (json['emoji'] as String?) ?? '\u{1F916}',
        description: (json['description'] as String?) ?? '',
        rolePrompt: (json['role_prompt'] as String?) ?? '',
        defaultSchedule: (json['schedule'] as String?) ?? '',
        canDelegate: json['can_delegate'] == true,
        requiredContext: (json['required_context'] as List?)
                ?.map((e) =>
                    ContextFieldMeta.fromJson(e as Map<String, dynamic>))
                .toList() ??
            [],
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
