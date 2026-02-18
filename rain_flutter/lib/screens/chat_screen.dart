import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../models/message.dart';
import '../providers/agent_provider.dart';
import '../providers/audio_provider.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../services/websocket_service.dart';
import '../widgets/animated_message.dart';
import '../widgets/computer_action_block.dart';
import '../widgets/computer_screenshot.dart';
import '../widgets/mode_switcher.dart';
import '../widgets/model_switcher.dart';
import '../widgets/rate_limit_badge.dart';
import 'history_screen.dart';
import 'metrics_screen.dart';
import 'settings_screen.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  int _lastMessageCount = 0;
  bool _userScrolledUp = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final pos = _scrollController.position;
    _userScrolledUp = pos.maxScrollExtent - pos.pixels > 150;
  }

  void _scrollToBottom({bool force = false}) {
    if (!_scrollController.hasClients) return;
    if (!force && _userScrolledUp) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  void _sendMessage() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;

    final agentState = ref.read(agentProvider);
    final agentId = agentState.activeAgentId;
    if (agentId.isEmpty) return;

    final ws = ref.read(webSocketServiceProvider);
    ws.send({
      'type': 'send_message',
      'text': text,
      'agent_id': agentId,
    });

    ref.read(agentProvider.notifier).appendMessage(
          agentId,
          UserMessage.create(text),
        );
    ref.read(agentProvider.notifier).setProcessing(agentId, true);
    ref
        .read(agentProvider.notifier)
        .setAgentStatus(agentId, AgentStatus.working);

    _inputController.clear();
    _userScrolledUp = false;
    _scrollToBottom(force: true);
  }

  void _interrupt() {
    final agentState = ref.read(agentProvider);
    final agentId = agentState.activeAgentId;
    if (agentId.isEmpty) return;

    final ws = ref.read(webSocketServiceProvider);
    ws.send({'type': 'interrupt', 'agent_id': agentId});
    ref.read(agentProvider.notifier).setInterruptPending(agentId, true);
  }

  Future<void> _toggleRecording() async {
    final audioService = ref.read(audioServiceProvider);
    final isRecording = ref.read(isRecordingProvider);

    if (isRecording) {
      ref.read(isRecordingProvider.notifier).state = false;
      final text = await audioService.stopAndUpload();
      if (text != null && text.isNotEmpty) {
        _inputController.text = text;
        _inputController.selection = TextSelection.collapsed(
          offset: text.length,
        );
      }
    } else {
      ref.read(isRecordingProvider.notifier).state = true;
      await audioService.startRecording();
    }
  }

  Widget _menuItem(IconData icon, String l10nKey, String lang) {
    return Row(
      children: [
        Icon(icon, size: 20),
        const SizedBox(width: 12),
        Text(L10n.t(l10nKey, lang)),
      ],
    );
  }

  void _createAgent() {
    _showNewAgentDialog(context);
  }

  void _showNewAgentDialog(BuildContext context) {
    final labelController = TextEditingController();
    final lang = ref.read(settingsProvider).language;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(L10n.t('agent.new', lang)),
        content: TextField(
          controller: labelController,
          autofocus: true,
          decoration: InputDecoration(
            hintText: L10n.t('agent.nameHint', lang),
          ),
          onSubmitted: (_) {
            Navigator.of(ctx).pop();
            _doCreateAgent(labelController.text.trim());
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(L10n.t('agent.cancel', lang)),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              _doCreateAgent(labelController.text.trim());
            },
            child: Text(L10n.t('agent.create', lang)),
          ),
        ],
      ),
    );
  }

  void _doCreateAgent(String label) {
    final agentNotifier = ref.read(agentProvider.notifier);
    final agentId =
        agentNotifier.createAgent(label: label.isEmpty ? null : label);

    // Show CWD picker bottom sheet for the new agent
    _showCwdPicker(agentId);
  }

  void _showCwdPicker(String agentId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (ctx) => _CwdPickerSheet(
        agentId: agentId,
        onSelected: (path) {
          final ws = ref.read(webSocketServiceProvider);
          ws.send({
            'type': 'set_cwd',
            'path': path,
            'agent_id': agentId,
          });
          Navigator.of(ctx).pop();
        },
      ),
    );
  }

  void _destroyAgent(String agentId) {
    final agents = ref.read(agentProvider).agents;
    if (agents.length <= 1) return; // Don't destroy last agent
    final lang = ref.read(settingsProvider).language;

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(L10n.t('agent.delete', lang)),
        content: Text(L10n.t('agent.deleteConfirm', lang,
            {'name': agents[agentId]?.label ?? agentId})),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(L10n.t('agent.cancel', lang)),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () {
              Navigator.of(ctx).pop();
              final ws = ref.read(webSocketServiceProvider);
              ws.send({'type': 'destroy_agent', 'agent_id': agentId});
              ref.read(agentProvider.notifier).removeAgent(agentId);
            },
            child: Text(L10n.t('history.delete', lang)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final agentState = ref.watch(agentProvider);
    final agent = agentState.activeAgent;
    final wsStatus = ref.watch(connectionStatusProvider);
    final statusText = ref.watch(statusTextProvider);
    final isRecording = ref.watch(isRecordingProvider);

    final messages = agent?.messages ?? [];
    final isProcessing = agent?.isProcessing ?? false;
    final isWaitingFirstChunk =
        isProcessing && agent?.streamMessageId == null;

    // Auto-scroll on new messages or streaming updates
    if (messages.length != _lastMessageCount) {
      _lastMessageCount = messages.length;
      _scrollToBottom();
    } else if (isProcessing && agent?.streamMessageId != null) {
      _scrollToBottom();
    }

    final lang = ref.watch(settingsProvider).language;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          children: [
            const Text('Rain',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            Text(
              wsStatus.when(
                data: (s) => s == ConnectionStatus.connected
                    ? statusText
                    : s == ConnectionStatus.connecting
                        ? L10n.t('status.connecting', lang)
                        : L10n.t('status.disconnected', lang),
                loading: () => L10n.t('status.connecting', lang),
                error: (_, __) => L10n.t('status.connectionError', lang),
              ),
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
          ],
        ),
        actions: [
          // Rate limit badge
          RateLimitBadge(
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const MetricsScreen()),
            ),
          ),
          const SizedBox(width: 4),
          // Model switcher
          const ModelSwitcher(),
          const SizedBox(width: 4),
          if (isProcessing)
            IconButton(
              onPressed: _interrupt,
              icon: Icon(Icons.stop_circle_outlined, color: cs.error),
              tooltip: 'Interrumpir',
            ),
          // Overflow menu
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            onSelected: (v) {
              switch (v) {
                case 'history':
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const HistoryScreen()),
                  );
                case 'metrics':
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const MetricsScreen()),
                  );
                case 'settings':
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const SettingsScreen()),
                  );
              }
            },
            itemBuilder: (_) => [
              PopupMenuItem(value: 'history', child: _menuItem(Icons.history, 'history.title', lang)),
              PopupMenuItem(value: 'metrics', child: _menuItem(Icons.bar_chart, 'metrics.title', lang)),
              PopupMenuItem(value: 'settings', child: _menuItem(Icons.settings, 'settings.title', lang)),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // Agent tab bar
          if (agentState.agents.length > 1 || agentState.agents.isNotEmpty)
            _AgentTabBar(
              agents: agentState.agents,
              activeAgentId: agentState.activeAgentId,
              onSelect: (id) =>
                  ref.read(agentProvider.notifier).setActiveAgent(id),
              onCreate: _createAgent,
              onDestroy: _destroyAgent,
            ),

          // Messages list
          Expanded(
            child: messages.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.chat_bubble_outline,
                            size: 48,
                            color:
                                cs.onSurfaceVariant.withValues(alpha: 0.3)),
                        const SizedBox(height: 16),
                        Text(
                          'Envia un mensaje para comenzar',
                          style: TextStyle(color: cs.onSurfaceVariant),
                        ),
                        if (agent?.cwd != null) ...[
                          const SizedBox(height: 8),
                          Text(
                            agent!.cwd!,
                            style: TextStyle(
                              color: cs.onSurfaceVariant
                                  .withValues(alpha: 0.5),
                              fontSize: 12,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ],
                      ],
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    itemCount:
                        messages.length + (isWaitingFirstChunk ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == messages.length) {
                        return const _TypingIndicator();
                      }
                      final msg = messages[index];
                      return AnimatedMessage(
                        key: ValueKey(msg.id),
                        animate: msg.animate,
                        child: _MessageTile(message: msg),
                      );
                    },
                  ),
          ),

          // Mode switcher (computer use)
          if (agent != null && agent.mode == AgentMode.computerUse)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: ModeSwitcher(lang: lang),
            )
          else if (agent != null && agent.mode == AgentMode.coding && agent.messages.isNotEmpty)
            const SizedBox.shrink(), // placeholder for mode toggle if needed

          // Input bar
          _InputBar(
            controller: _inputController,
            isProcessing: isProcessing,
            isRecording: isRecording,
            onSend: _sendMessage,
            onToggleRecording: _toggleRecording,
          ),
        ],
      ),
    );
  }
}

// ── Agent tab bar ──

class _AgentTabBar extends StatelessWidget {
  final Map<String, Agent> agents;
  final String activeAgentId;
  final ValueChanged<String> onSelect;
  final VoidCallback onCreate;
  final ValueChanged<String> onDestroy;

  const _AgentTabBar({
    required this.agents,
    required this.activeAgentId,
    required this.onSelect,
    required this.onCreate,
    required this.onDestroy,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final entries = agents.entries.toList();

    return Container(
      height: 44,
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(
          bottom:
              BorderSide(color: cs.outlineVariant.withValues(alpha: 0.3)),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              itemCount: entries.length,
              itemBuilder: (context, index) {
                final agent = entries[index].value;
                final isActive = agent.id == activeAgentId;
                return _AgentTab(
                  agent: agent,
                  isActive: isActive,
                  onTap: () => onSelect(agent.id),
                  onClose: agents.length > 1
                      ? () => onDestroy(agent.id)
                      : null,
                );
              },
            ),
          ),
          // Add agent button
          if (agents.length < 5)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: SizedBox(
                width: 32,
                height: 32,
                child: IconButton(
                  onPressed: onCreate,
                  icon: const Icon(Icons.add, size: 18),
                  padding: EdgeInsets.zero,
                  tooltip: 'Nuevo agente',
                  style: IconButton.styleFrom(
                    backgroundColor:
                        cs.primary.withValues(alpha: 0.1),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _AgentTab extends StatelessWidget {
  final Agent agent;
  final bool isActive;
  final VoidCallback onTap;
  final VoidCallback? onClose;

  const _AgentTab({
    required this.agent,
    required this.isActive,
    required this.onTap,
    this.onClose,
  });

  Color _statusColor() {
    return switch (agent.status) {
      AgentStatus.working => Colors.orange,
      AgentStatus.done => Colors.green,
      AgentStatus.error => Colors.red,
      AgentStatus.idle => Colors.grey,
    };
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return GestureDetector(
      onTap: onTap,
      onLongPress: onClose,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 3, vertical: 6),
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          color: isActive ? cs.primaryContainer : cs.surface,
          borderRadius: BorderRadius.circular(20),
          border: isActive
              ? Border.all(color: cs.primary, width: 1.5)
              : Border.all(
                  color: cs.outlineVariant.withValues(alpha: 0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Status dot
            Container(
              width: 7,
              height: 7,
              decoration: BoxDecoration(
                color: _statusColor(),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 6),
            // Label
            Text(
              agent.label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                color:
                    isActive ? cs.onPrimaryContainer : cs.onSurfaceVariant,
              ),
            ),
            // Unread badge
            if (agent.unread > 0) ...[
              const SizedBox(width: 6),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: cs.error,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  agent.unread > 99 ? '99+' : '${agent.unread}',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: cs.onError,
                  ),
                ),
              ),
            ],
            // Close button (only visible on active tab with >1 agents)
            if (isActive && onClose != null) ...[
              const SizedBox(width: 4),
              SizedBox(
                width: 20,
                height: 20,
                child: IconButton(
                  onPressed: onClose,
                  icon: const Icon(Icons.close, size: 14),
                  padding: EdgeInsets.zero,
                  visualDensity: VisualDensity.compact,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// ── CWD picker bottom sheet for new agents ──

class _CwdPickerSheet extends ConsumerStatefulWidget {
  final String agentId;
  final ValueChanged<String> onSelected;

  const _CwdPickerSheet({
    required this.agentId,
    required this.onSelected,
  });

  @override
  ConsumerState<_CwdPickerSheet> createState() => _CwdPickerSheetState();
}

class _CwdPickerSheetState extends ConsumerState<_CwdPickerSheet> {
  List<Map<String, dynamic>> _entries = [];
  String _currentPath = '~';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadDirectory('~');
  }

  Future<void> _loadDirectory(String path) async {
    setState(() => _loading = true);
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/browse', queryParameters: {'path': path});
      if (!mounted) return;
      setState(() {
        _currentPath = res.data['current'] ?? path;
        _entries =
            List<Map<String, dynamic>>.from(res.data['entries'] ?? []);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return SizedBox(
      height: MediaQuery.of(context).size.height * 0.65,
      child: Column(
        children: [
          // Handle
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: 12, bottom: 8),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: cs.onSurfaceVariant.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          // Title
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                const Text('Seleccionar directorio',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                const Spacer(),
                FilledButton.tonal(
                  onPressed: () => widget.onSelected(_currentPath),
                  child: const Text('Usar este'),
                ),
              ],
            ),
          ),
          // Path bar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: cs.surfaceContainer,
            child: Text(
              _currentPath,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: cs.onSurfaceVariant,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          // Directory listing
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    itemCount: _entries.length,
                    itemBuilder: (context, index) {
                      final entry = _entries[index];
                      final isDir = entry['is_dir'] == true;
                      final name = entry['name'] as String;
                      return ListTile(
                        dense: true,
                        leading: Icon(
                          isDir
                              ? Icons.folder
                              : Icons.insert_drive_file_outlined,
                          size: 20,
                          color: isDir ? cs.primary : cs.onSurfaceVariant,
                        ),
                        title: Text(name, style: const TextStyle(fontSize: 14)),
                        onTap: isDir
                            ? () => _loadDirectory(entry['path'] as String)
                            : null,
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Input bar ──

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final bool isProcessing;
  final bool isRecording;
  final VoidCallback onSend;
  final VoidCallback onToggleRecording;

  const _InputBar({
    required this.controller,
    required this.isProcessing,
    required this.isRecording,
    required this.onSend,
    required this.onToggleRecording,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Container(
      padding: EdgeInsets.fromLTRB(
          8, 8, 8, MediaQuery.of(context).padding.bottom + 8),
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(
            top: BorderSide(
                color: cs.outlineVariant.withValues(alpha: 0.3))),
      ),
      child: Row(
        children: [
          // Mic button
          IconButton(
            onPressed: isProcessing ? null : onToggleRecording,
            icon: isRecording
                ? Icon(Icons.stop, color: cs.error)
                : const Icon(Icons.mic_none),
            style: isRecording
                ? IconButton.styleFrom(
                    backgroundColor:
                        cs.errorContainer.withValues(alpha: 0.3),
                  )
                : null,
          ),
          const SizedBox(width: 4),
          // Text field
          Expanded(
            child: TextField(
              controller: controller,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => onSend(),
              maxLines: 4,
              minLines: 1,
              enabled: !isRecording,
              decoration: InputDecoration(
                hintText:
                    isRecording ? 'Grabando...' : 'Escribe un mensaje...',
                filled: true,
                fillColor: cs.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20, vertical: 12),
              ),
            ),
          ),
          const SizedBox(width: 8),
          // Send button
          IconButton.filled(
            onPressed: isProcessing ? null : onSend,
            icon: isProcessing
                ? SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: cs.onPrimary,
                    ),
                  )
                : const Icon(Icons.send),
          ),
        ],
      ),
    );
  }
}

// ── Typing indicator (3 animated dots) ──

class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(16),
        ),
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(3, (i) {
                final delay = i * 0.2;
                final t =
                    ((_controller.value - delay) % 1.0).clamp(0.0, 1.0);
                final opacity = 0.3 +
                    0.7 *
                        (t < 0.5 ? t * 2 : (1 - t) * 2).clamp(0.0, 1.0);
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Opacity(
                    opacity: opacity,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: cs.onSurfaceVariant,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                );
              }),
            );
          },
        ),
      ),
    );
  }
}

// ── Message tile (pattern match on sealed Message) ──

class _MessageTile extends ConsumerWidget {
  final Message message;
  const _MessageTile({required this.message});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(settingsProvider).language;
    return switch (message) {
      UserMessage(:final text) => _UserBubble(text: text),
      AssistantMessage(:final text, :final isStreaming) =>
        _AssistantBubble(text: text, isStreaming: isStreaming),
      SystemMessage(:final text) => _SystemLine(text: text),
      ToolUseMessage() =>
        _ToolUseBlock(message: message as ToolUseMessage),
      ToolResultMessage() =>
        _ToolResultBlock(message: message as ToolResultMessage),
      PermissionRequestMessage() =>
        _PermissionBlock(message: message as PermissionRequestMessage),
      ComputerScreenshotMessage() => ComputerScreenshotBlock(
          message: message as ComputerScreenshotMessage, lang: lang),
      ComputerActionMessage() => ComputerActionBlock(
          message: message as ComputerActionMessage, lang: lang),
    };
  }
}

// ── User bubble ──

class _UserBubble extends StatelessWidget {
  final String text;
  const _UserBubble({required this.text});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: cs.primaryContainer,
          borderRadius: BorderRadius.circular(16),
        ),
        child: SelectableText(
          text,
          style: TextStyle(color: cs.onPrimaryContainer, fontSize: 15),
        ),
      ),
    );
  }
}

// ── Assistant bubble with markdown ──

class _AssistantBubble extends StatelessWidget {
  final String text;
  final bool isStreaming;
  const _AssistantBubble(
      {required this.text, required this.isStreaming});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final displayText = isStreaming ? '$text ▍' : text;

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(16),
        ),
        child: MarkdownBody(
          data: displayText,
          selectable: true,
          styleSheet: MarkdownStyleSheet(
            p: TextStyle(
                color: cs.onSurface, fontSize: 15, height: 1.5),
            code: TextStyle(
              color: cs.onSurface,
              backgroundColor: cs.surfaceContainer,
              fontSize: 13,
              fontFamily: 'monospace',
            ),
            codeblockDecoration: BoxDecoration(
              color: cs.surfaceContainer,
              borderRadius: BorderRadius.circular(8),
            ),
            codeblockPadding: const EdgeInsets.all(12),
            blockquoteDecoration: BoxDecoration(
              border: Border(
                left: BorderSide(color: cs.primary, width: 3),
              ),
            ),
            blockquotePadding: const EdgeInsets.only(left: 12),
            h1: TextStyle(
                color: cs.onSurface,
                fontSize: 22,
                fontWeight: FontWeight.bold),
            h2: TextStyle(
                color: cs.onSurface,
                fontSize: 19,
                fontWeight: FontWeight.bold),
            h3: TextStyle(
                color: cs.onSurface,
                fontSize: 17,
                fontWeight: FontWeight.w600),
            listBullet:
                TextStyle(color: cs.onSurface, fontSize: 15),
            a: TextStyle(color: cs.primary),
            strong: TextStyle(
                color: cs.onSurface, fontWeight: FontWeight.bold),
            em: TextStyle(
                color: cs.onSurface, fontStyle: FontStyle.italic),
          ),
        ),
      ),
    );
  }
}

// ── System message line ──

class _SystemLine extends StatelessWidget {
  final String text;
  const _SystemLine({required this.text});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Center(
        child: Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: cs.surfaceContainerHigh.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            text,
            style:
                TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
          ),
        ),
      ),
    );
  }
}

// ── Expandable tool_use block ──

class _ToolUseBlock extends StatelessWidget {
  final ToolUseMessage message;
  const _ToolUseBlock({required this.message});

  IconData _toolIcon(String tool) {
    return switch (tool) {
      'bash' || 'execute' => Icons.terminal,
      'write' || 'create_file' => Icons.edit_note,
      'read' || 'read_file' => Icons.description_outlined,
      'search' || 'grep' || 'find' => Icons.search,
      'browser' || 'web' => Icons.language,
      _ => Icons.build_outlined,
    };
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final inputJson =
        const JsonEncoder.withIndent('  ').convert(message.input);

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
              color: cs.outlineVariant.withValues(alpha: 0.3)),
        ),
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          dense: true,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading: Icon(_toolIcon(message.tool),
              size: 18, color: cs.primary),
          title: Text(
            message.tool,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: cs.onSurface,
            ),
          ),
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: cs.surfaceContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                inputJson,
                style: TextStyle(
                  fontSize: 12,
                  fontFamily: 'monospace',
                  color: cs.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Expandable tool_result block ──

class _ToolResultBlock extends StatelessWidget {
  final ToolResultMessage message;
  const _ToolResultBlock({required this.message});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isError = message.isError;
    final preview = message.content.length > 80
        ? '${message.content.substring(0, 80)}...'
        : message.content;

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 3),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: isError
              ? cs.errorContainer.withValues(alpha: 0.3)
              : cs.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isError
                ? cs.error.withValues(alpha: 0.3)
                : cs.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          dense: true,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading: Icon(
            isError
                ? Icons.error_outline
                : Icons.check_circle_outline,
            size: 18,
            color: isError ? cs.error : Colors.green,
          ),
          title: Text(
            isError ? 'Error' : preview,
            style: TextStyle(
              fontSize: 12,
              color: isError ? cs.error : cs.onSurfaceVariant,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          children: [
            Container(
              width: double.infinity,
              constraints: const BoxConstraints(maxHeight: 300),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: cs.surfaceContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SingleChildScrollView(
                child: SelectableText(
                  message.content,
                  style: TextStyle(
                    fontSize: 12,
                    fontFamily: 'monospace',
                    color: isError ? cs.error : cs.onSurfaceVariant,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Permission request block with PIN input + countdown ──

class _PermissionBlock extends ConsumerStatefulWidget {
  final PermissionRequestMessage message;
  const _PermissionBlock({required this.message});

  @override
  ConsumerState<_PermissionBlock> createState() =>
      _PermissionBlockState();
}

class _PermissionBlockState extends ConsumerState<_PermissionBlock> {
  final _pinController = TextEditingController();
  Timer? _countdownTimer;
  int _remainingSeconds = 0;

  @override
  void initState() {
    super.initState();
    if (widget.message.status == PermissionStatus.pending) {
      _startCountdown();
    }
  }

  void _startCountdown() {
    // 5 minutes from when the message was created
    const timeoutMs = 5 * 60 * 1000;
    final elapsed =
        DateTime.now().millisecondsSinceEpoch - widget.message.timestamp;
    final remaining = timeoutMs - elapsed;

    if (remaining <= 0) {
      _remainingSeconds = 0;
      _expire();
      return;
    }

    _remainingSeconds = (remaining / 1000).ceil();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) {
        _countdownTimer?.cancel();
        return;
      }
      setState(() {
        _remainingSeconds--;
        if (_remainingSeconds <= 0) {
          _countdownTimer?.cancel();
          _expire();
        }
      });
    });
  }

  void _expire() {
    final agentId = ref.read(agentProvider).activeAgentId;
    ref.read(agentProvider.notifier).updatePermissionStatus(
          agentId,
          widget.message.requestId,
          PermissionStatus.expired,
        );
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _pinController.dispose();
    super.dispose();
  }

  String _formatTime(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '$m:${s.toString().padLeft(2, '0')}';
  }

  void _respond(bool approved) {
    _countdownTimer?.cancel();
    final agentId = ref.read(agentProvider).activeAgentId;

    final ws = ref.read(webSocketServiceProvider);
    final payload = <String, dynamic>{
      'type': 'permission_response',
      'request_id': widget.message.requestId,
      'agent_id': agentId,
      'approved': approved,
    };

    // Include PIN for RED level
    if (widget.message.level == PermissionLevel.red && approved) {
      payload['pin'] = _pinController.text;
    }

    ws.send(payload);

    ref.read(agentProvider.notifier).updatePermissionStatus(
          agentId,
          widget.message.requestId,
          approved ? PermissionStatus.approved : PermissionStatus.denied,
        );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isRed = widget.message.level == PermissionLevel.red;
    final isPending =
        widget.message.status == PermissionStatus.pending;
    final inputJson = const JsonEncoder.withIndent('  ')
        .convert(widget.message.input);

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: isRed ? cs.errorContainer : cs.tertiaryContainer,
          borderRadius: BorderRadius.circular(16),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            ListTile(
              dense: true,
              leading: Icon(
                isRed ? Icons.gpp_bad : Icons.shield_outlined,
                color: isRed ? cs.error : cs.tertiary,
              ),
              title: Text(
                'Permiso: ${widget.message.tool}',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: isRed
                      ? cs.onErrorContainer
                      : cs.onTertiaryContainer,
                ),
              ),
              subtitle: Text(
                widget.message.reason,
                style: TextStyle(
                  fontSize: 12,
                  color: isRed
                      ? cs.onErrorContainer.withValues(alpha: 0.7)
                      : cs.onTertiaryContainer.withValues(alpha: 0.7),
                ),
              ),
              trailing: isPending && _remainingSeconds > 0
                  ? Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: (_remainingSeconds < 60
                                ? cs.error
                                : cs.onSurfaceVariant)
                            .withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _formatTime(_remainingSeconds),
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          fontFamily: 'monospace',
                          color: _remainingSeconds < 60
                              ? cs.error
                              : cs.onSurfaceVariant,
                        ),
                      ),
                    )
                  : null,
            ),

            // Tool input details (expandable)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: ExpansionTile(
                dense: true,
                tilePadding: EdgeInsets.zero,
                childrenPadding:
                    const EdgeInsets.only(bottom: 8),
                title: Text(
                  'Detalles',
                  style: TextStyle(
                    fontSize: 12,
                    color: isRed
                        ? cs.onErrorContainer.withValues(alpha: 0.6)
                        : cs.onTertiaryContainer
                            .withValues(alpha: 0.6),
                  ),
                ),
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(8),
                    constraints:
                        const BoxConstraints(maxHeight: 150),
                    decoration: BoxDecoration(
                      color: cs.surface.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: SingleChildScrollView(
                      child: SelectableText(
                        inputJson,
                        style: TextStyle(
                          fontSize: 11,
                          fontFamily: 'monospace',
                          color: isRed
                              ? cs.onErrorContainer
                              : cs.onTertiaryContainer,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // PIN input for RED level
            if (isPending && isRed)
              Padding(
                padding:
                    const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: TextField(
                  controller: _pinController,
                  obscureText: true,
                  decoration: InputDecoration(
                    hintText: 'Ingresa PIN para aprobar',
                    filled: true,
                    fillColor: cs.surface.withValues(alpha: 0.5),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                    isDense: true,
                    prefixIcon: Icon(Icons.lock_outline,
                        size: 18, color: cs.error),
                  ),
                  style: const TextStyle(fontSize: 14),
                ),
              ),

            // Action buttons / status
            if (isPending)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    OutlinedButton(
                      onPressed: () => _respond(false),
                      child: const Text('Denegar'),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(
                      onPressed: () => _respond(true),
                      style: isRed
                          ? FilledButton.styleFrom(
                              backgroundColor: cs.error,
                              foregroundColor: cs.onError,
                            )
                          : null,
                      child: const Text('Aprobar'),
                    ),
                  ],
                ),
              )
            else
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Row(
                  children: [
                    Icon(
                      widget.message.status ==
                              PermissionStatus.approved
                          ? Icons.check_circle
                          : widget.message.status ==
                                  PermissionStatus.denied
                              ? Icons.cancel
                              : Icons.timer_off,
                      size: 16,
                      color: widget.message.status ==
                              PermissionStatus.approved
                          ? Colors.green
                          : cs.error,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      widget.message.status ==
                              PermissionStatus.approved
                          ? 'Aprobado'
                          : widget.message.status ==
                                  PermissionStatus.denied
                              ? 'Denegado'
                              : 'Expirado',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: widget.message.status ==
                                PermissionStatus.approved
                            ? Colors.green
                            : cs.error,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
