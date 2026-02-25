/// Model for tracking active sub-agents (runtime state, not chat messages).
/// Mirrors SubAgentInfo from frontend web (types.ts).
class SubAgentInfo {
  final String id;
  final String shortName;
  final String parentId;
  final String task;
  final String status; // "running" | "completed" | "error" | "cancelled"

  const SubAgentInfo({
    required this.id,
    required this.shortName,
    required this.parentId,
    required this.task,
    this.status = 'running',
  });

  SubAgentInfo copyWith({
    String? id,
    String? shortName,
    String? parentId,
    String? task,
    String? status,
  }) =>
      SubAgentInfo(
        id: id ?? this.id,
        shortName: shortName ?? this.shortName,
        parentId: parentId ?? this.parentId,
        task: task ?? this.task,
        status: status ?? this.status,
      );

  factory SubAgentInfo.fromJson(Map<String, dynamic> json) => SubAgentInfo(
        id: json['id'] as String? ?? '',
        shortName:
            json['shortName'] as String? ?? json['short_name'] as String? ?? '',
        parentId:
            json['parentId'] as String? ?? json['parent_id'] as String? ?? '',
        task: json['task'] as String? ?? '',
        status: json['status'] as String? ?? 'running',
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'shortName': shortName,
        'parentId': parentId,
        'task': task,
        'status': status,
      };
}
