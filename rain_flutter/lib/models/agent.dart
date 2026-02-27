import 'message.dart';
import 'subagent_info.dart';

enum AgentStatus { idle, working, done, error }

enum AgentMode { coding, computerUse }

enum AgentPanel { fileBrowser, chat }

class DisplayInfo {
  final int screenWidth;
  final int screenHeight;
  final int scaledWidth;
  final int scaledHeight;
  final double scaleFactor;
  final int monitorIndex;
  final int monitorCount;
  final int monitorLeft;
  final int monitorTop;

  const DisplayInfo({
    required this.screenWidth,
    required this.screenHeight,
    required this.scaledWidth,
    required this.scaledHeight,
    required this.scaleFactor,
    this.monitorIndex = 1,
    this.monitorCount = 1,
    this.monitorLeft = 0,
    this.monitorTop = 0,
  });

  factory DisplayInfo.fromJson(Map<String, dynamic> json) {
    final offset = json['monitor_offset'] as Map<String, dynamic>?;
    return DisplayInfo(
      screenWidth: json['screen_width'] ?? 0,
      screenHeight: json['screen_height'] ?? 0,
      scaledWidth: json['scaled_width'] ?? 0,
      scaledHeight: json['scaled_height'] ?? 0,
      scaleFactor: (json['scale_factor'] ?? 1.0).toDouble(),
      monitorIndex: json['monitor_index'] ?? 1,
      monitorCount: json['monitor_count'] ?? 1,
      monitorLeft: offset?['left'] ?? 0,
      monitorTop: offset?['top'] ?? 0,
    );
  }
}

class Agent {
  final String id;
  String? cwd;
  String currentBrowsePath;
  String label;
  AgentStatus status;
  int unread;
  List<Message> messages;
  double scrollPos;
  String streamText;
  String? streamMessageId;
  bool isProcessing;
  bool interruptPending;
  bool historyLoaded;
  String? sessionId;
  AgentPanel activePanel;
  AgentMode mode;
  DisplayInfo? displayInfo;
  String? lastScreenshot;
  String? previousScreenshot;
  int computerIteration;
  bool autoApprove;
  List<SubAgentInfo> subAgents;

  Agent({
    required this.id,
    this.cwd,
    this.currentBrowsePath = '~',
    this.label = 'Agent',
    this.status = AgentStatus.idle,
    this.unread = 0,
    List<Message>? messages,
    this.scrollPos = 0,
    this.streamText = '',
    this.streamMessageId,
    this.isProcessing = false,
    this.interruptPending = false,
    this.historyLoaded = false,
    this.sessionId,
    this.activePanel = AgentPanel.chat,
    this.mode = AgentMode.coding,
    this.displayInfo,
    this.lastScreenshot,
    this.previousScreenshot,
    this.computerIteration = 0,
    this.autoApprove = false,
    List<SubAgentInfo>? subAgents,
  })  : messages = messages ?? [],
        subAgents = subAgents ?? [];
}
