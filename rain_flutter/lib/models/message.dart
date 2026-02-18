import 'package:uuid/uuid.dart';

const _uuid = Uuid();

/// Base class for all chat messages.
sealed class Message {
  final String id;
  final int timestamp;
  final bool animate;

  const Message({
    required this.id,
    required this.timestamp,
    this.animate = true,
  });

  String get type;

  Map<String, dynamic> toJson();

  static Message fromJson(Map<String, dynamic> json) {
    return switch (json['type']) {
      'user' => UserMessage.fromJson(json),
      'assistant' => AssistantMessage.fromJson(json),
      'system' => SystemMessage.fromJson(json),
      'tool_use' => ToolUseMessage.fromJson(json),
      'tool_result' => ToolResultMessage.fromJson(json),
      'permission_request' => PermissionRequestMessage.fromJson(json),
      'computer_screenshot' => ComputerScreenshotMessage.fromJson(json),
      'computer_action' => ComputerActionMessage.fromJson(json),
      _ => SystemMessage(
          id: json['id'] ?? _uuid.v4(),
          text: 'Unknown message type: ${json['type']}',
          timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        ),
    };
  }
}

class UserMessage extends Message {
  final String text;

  const UserMessage({
    required super.id,
    required this.text,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'user';

  factory UserMessage.create(String text) => UserMessage(
        id: _uuid.v4(),
        text: text,
        timestamp: DateTime.now().millisecondsSinceEpoch,
      );

  factory UserMessage.fromJson(Map<String, dynamic> json) => UserMessage(
        id: json['id'] ?? _uuid.v4(),
        text: json['text'] ?? '',
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'text': text,
        'timestamp': timestamp,
        'animate': animate,
      };
}

class AssistantMessage extends Message {
  final String text;
  final bool isStreaming;

  const AssistantMessage({
    required super.id,
    required this.text,
    this.isStreaming = false,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'assistant';

  AssistantMessage copyWith({String? text, bool? isStreaming}) =>
      AssistantMessage(
        id: id,
        text: text ?? this.text,
        isStreaming: isStreaming ?? this.isStreaming,
        timestamp: timestamp,
        animate: animate,
      );

  factory AssistantMessage.fromJson(Map<String, dynamic> json) =>
      AssistantMessage(
        id: json['id'] ?? _uuid.v4(),
        text: json['text'] ?? '',
        isStreaming: json['isStreaming'] ?? false,
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'text': text,
        'isStreaming': isStreaming,
        'timestamp': timestamp,
        'animate': animate,
      };
}

class SystemMessage extends Message {
  final String text;

  const SystemMessage({
    required super.id,
    required this.text,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'system';

  factory SystemMessage.create(String text) => SystemMessage(
        id: _uuid.v4(),
        text: text,
        timestamp: DateTime.now().millisecondsSinceEpoch,
      );

  factory SystemMessage.fromJson(Map<String, dynamic> json) => SystemMessage(
        id: json['id'] ?? _uuid.v4(),
        text: json['text'] ?? '',
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'text': text,
        'timestamp': timestamp,
        'animate': animate,
      };
}

class ToolUseMessage extends Message {
  final String tool;
  final Map<String, dynamic> input;
  final String toolUseId;

  const ToolUseMessage({
    required super.id,
    required this.tool,
    required this.input,
    required this.toolUseId,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'tool_use';

  factory ToolUseMessage.fromJson(Map<String, dynamic> json) => ToolUseMessage(
        id: json['id'] ?? _uuid.v4(),
        tool: json['tool'] ?? '',
        input: Map<String, dynamic>.from(json['input'] ?? {}),
        toolUseId: json['toolUseId'] ?? '',
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'tool': tool,
        'input': input,
        'toolUseId': toolUseId,
        'timestamp': timestamp,
        'animate': animate,
      };
}

class ToolResultMessage extends Message {
  final String content;
  final bool isError;
  final String toolUseId;

  const ToolResultMessage({
    required super.id,
    required this.content,
    required this.isError,
    required this.toolUseId,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'tool_result';

  factory ToolResultMessage.fromJson(Map<String, dynamic> json) =>
      ToolResultMessage(
        id: json['id'] ?? _uuid.v4(),
        content: json['content'] ?? '',
        isError: json['isError'] ?? false,
        toolUseId: json['toolUseId'] ?? '',
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'content': content,
        'isError': isError,
        'toolUseId': toolUseId,
        'timestamp': timestamp,
        'animate': animate,
      };
}

enum PermissionLevel { yellow, red, computer }

enum PermissionStatus { pending, approved, denied, expired }

class PermissionRequestMessage extends Message {
  final String requestId;
  final String tool;
  final Map<String, dynamic> input;
  final PermissionLevel level;
  final String reason;
  final PermissionStatus status;

  const PermissionRequestMessage({
    required super.id,
    required this.requestId,
    required this.tool,
    required this.input,
    required this.level,
    required this.reason,
    this.status = PermissionStatus.pending,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'permission_request';

  PermissionRequestMessage copyWith({PermissionStatus? status}) =>
      PermissionRequestMessage(
        id: id,
        requestId: requestId,
        tool: tool,
        input: input,
        level: level,
        reason: reason,
        status: status ?? this.status,
        timestamp: timestamp,
        animate: animate,
      );

  factory PermissionRequestMessage.fromJson(Map<String, dynamic> json) =>
      PermissionRequestMessage(
        id: json['id'] ?? _uuid.v4(),
        requestId: json['requestId'] ?? '',
        tool: json['tool'] ?? '',
        input: Map<String, dynamic>.from(json['input'] ?? {}),
        level: PermissionLevel.values.firstWhere(
          (e) => e.name == json['level'],
          orElse: () => PermissionLevel.yellow,
        ),
        reason: json['reason'] ?? '',
        status: PermissionStatus.values.firstWhere(
          (e) => e.name == json['status'],
          orElse: () => PermissionStatus.pending,
        ),
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'requestId': requestId,
        'tool': tool,
        'input': input,
        'level': level.name,
        'reason': reason,
        'status': status.name,
        'timestamp': timestamp,
        'animate': animate,
      };
}

class ComputerScreenshotMessage extends Message {
  final String image;
  final String action;
  final String description;
  final int iteration;

  const ComputerScreenshotMessage({
    required super.id,
    required this.image,
    required this.action,
    required this.description,
    required this.iteration,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'computer_screenshot';

  factory ComputerScreenshotMessage.fromJson(Map<String, dynamic> json) =>
      ComputerScreenshotMessage(
        id: json['id'] ?? _uuid.v4(),
        image: json['image'] ?? '',
        action: json['action'] ?? '',
        description: json['description'] ?? '',
        iteration: json['iteration'] ?? 0,
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'image': image,
        'action': action,
        'description': description,
        'iteration': iteration,
        'timestamp': timestamp,
        'animate': animate,
      };
}

class ComputerActionMessage extends Message {
  final String tool;
  final String action;
  final Map<String, dynamic> input;
  final String description;
  final int iteration;

  const ComputerActionMessage({
    required super.id,
    required this.tool,
    required this.action,
    required this.input,
    required this.description,
    required this.iteration,
    required super.timestamp,
    super.animate,
  });

  @override
  String get type => 'computer_action';

  factory ComputerActionMessage.fromJson(Map<String, dynamic> json) =>
      ComputerActionMessage(
        id: json['id'] ?? _uuid.v4(),
        tool: json['tool'] ?? '',
        action: json['action'] ?? '',
        input: Map<String, dynamic>.from(json['input'] ?? {}),
        description: json['description'] ?? '',
        iteration: json['iteration'] ?? 0,
        timestamp: json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch,
        animate: json['animate'] ?? false,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'tool': tool,
        'action': action,
        'input': input,
        'description': description,
        'iteration': iteration,
        'timestamp': timestamp,
        'animate': animate,
      };
}
