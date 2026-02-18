class ConversationMeta {
  final String id;
  final int createdAt;
  final int updatedAt;
  final String label;
  final String cwd;
  final int messageCount;
  final String preview;
  final double totalCost;

  const ConversationMeta({
    required this.id,
    required this.createdAt,
    required this.updatedAt,
    required this.label,
    required this.cwd,
    required this.messageCount,
    required this.preview,
    required this.totalCost,
  });

  factory ConversationMeta.fromJson(Map<String, dynamic> json) =>
      ConversationMeta(
        id: json['id'] ?? '',
        createdAt: json['createdAt'] ?? 0,
        updatedAt: json['updatedAt'] ?? 0,
        label: json['label'] ?? '',
        cwd: json['cwd'] ?? '',
        messageCount: json['messageCount'] ?? 0,
        preview: json['preview'] ?? '',
        totalCost: (json['totalCost'] ?? 0).toDouble(),
      );
}
