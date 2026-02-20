import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../models/message.dart';
import '../providers/agent_provider.dart';
import '../providers/audio_provider.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../services/voice_mode_service.dart';
import '../services/websocket_service.dart';
import '../widgets/agent_manager_sheet.dart';
import '../widgets/animated_message.dart';
import '../widgets/chat_input_bar.dart';
import '../widgets/chat_messages.dart';
import '../widgets/computer_live_display.dart';
import '../widgets/cwd_picker_sheet.dart';
import '../widgets/mode_switcher.dart';
import '../widgets/model_switcher.dart';
import '../widgets/rate_limit_badge.dart';
import '../widgets/talk_mode_overlay.dart';
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

  // Voice mode
  final _voiceService = VoiceModeService();
  bool _talkModeActive = false;
  String _voiceStateLabel = '';
  StreamSubscription<Map<String, dynamic>>? _voiceMsgSub;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _voiceService.voiceState.addListener(_onVoiceStateChanged);
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    _voiceMsgSub?.cancel();
    _voiceService.voiceState.removeListener(_onVoiceStateChanged);
    _voiceService.dispose();
    super.dispose();
  }

  void _onVoiceStateChanged() {
    final state = _voiceService.voiceState.value;
    final lang = ref.read(settingsProvider).language;
    final label = switch (state) {
      VoiceState.listening => L10n.t('voice.listening', lang),
      VoiceState.wakeListening => L10n.t('voice.wakeListening', lang),
      VoiceState.recording => L10n.t('voice.recording', lang),
      VoiceState.transcribing => L10n.t('voice.transcribing', lang),
      VoiceState.processing => L10n.t('voice.processing', lang),
      VoiceState.speaking => L10n.t('voice.speaking', lang),
      VoiceState.idle => '',
    };
    if (mounted) setState(() => _voiceStateLabel = label);
  }

  void _startListeningVoiceMessages() {
    _voiceMsgSub?.cancel();
    final ws = ref.read(webSocketServiceProvider);
    _voiceMsgSub = ws.messageStream.listen((msg) {
      if (_voiceService.handleMessage(msg)) {
        // Voice transcription auto-send
        final text = _voiceService.lastTranscription.value;
        if (msg['type'] == 'voice_transcription' &&
            msg['is_final'] == true &&
            text.isNotEmpty) {
          _inputController.text = text;
          _sendMessage();
          _voiceService.lastTranscription.value = '';
        }
      }
    });
  }

  void _toggleTalkMode() {
    final agentId = ref.read(agentProvider).activeAgentId;
    if (agentId.isEmpty) return;
    final ws = ref.read(webSocketServiceProvider);
    final settings = ref.read(settingsProvider);

    if (_talkModeActive) {
      ws.send({'type': 'talk_mode_stop', 'agent_id': agentId});
      ws.send({'type': 'voice_mode_set', 'mode': 'push-to-talk', 'agent_id': agentId});
      _voiceService.deactivate();
      _voiceMsgSub?.cancel();
      setState(() => _talkModeActive = false);
    } else {
      ws.send({
        'type': 'voice_mode_set',
        'mode': settings.voiceMode,
        'agent_id': agentId,
        'vad_threshold': settings.vadSensitivity,
        'silence_timeout': settings.silenceTimeout,
      });
      if (settings.voiceMode == 'talk-mode') {
        ws.send({'type': 'talk_mode_start', 'agent_id': agentId});
      }
      _voiceService.activate(
        settings.voiceMode == 'wake-word' ? VoiceMode.wakeWord : VoiceMode.talkMode,
      );
      _startListeningVoiceMessages();
      setState(() => _talkModeActive = true);
    }
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
      builder: (ctx) => CwdPickerSheet(
        agentId: agentId,
        onSelected: (path) {
          final ws = ref.read(webSocketServiceProvider);
          final settings = ref.read(settingsProvider);
          ws.send({
            'type': 'set_cwd',
            'path': path,
            'agent_id': agentId,
            'model': settings.aiModel,
            'provider': settings.aiProvider.name,
          });
          Navigator.of(ctx).pop();
        },
      ),
    );
  }

  void _openAgentManager() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => AgentManagerSheet(
        onSwitchAgent: (id) {
          ref.read(agentProvider.notifier).setActiveAgent(id);
        },
        onDestroyAgent: _destroyAgent,
        onCreateAgent: _createAgent,
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
              tooltip: L10n.t('chat.stop', lang),
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
      body: Stack(
        children: [
          Column(
            children: [
              // Connection banner
              _ConnectionBanner(wsStatus: wsStatus, lang: lang),

          // Agent tab bar
          if (agentState.agents.isNotEmpty)
            _AgentTabBar(
              agents: agentState.agents,
              activeAgentId: agentState.activeAgentId,
              onSelect: (id) =>
                  ref.read(agentProvider.notifier).setActiveAgent(id),
              onCreate: _createAgent,
              onDestroy: _destroyAgent,
              onOpenManager: _openAgentManager,
            ),

          // Live display panel (computer use mode)
          if (agent != null && agent.mode == AgentMode.computerUse)
            ComputerLiveDisplay(lang: lang),

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
                          L10n.t('chat.emptyState', lang),
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
                        child: MessageTile(message: msg),
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
          ChatInputBar(
            controller: _inputController,
            isProcessing: isProcessing,
            isRecording: isRecording,
            onSend: _sendMessage,
            onToggleRecording: _toggleRecording,
            lang: lang,
            voiceMode: ref.watch(settingsProvider).voiceMode,
            talkModeActive: _talkModeActive,
            onToggleTalkMode: _toggleTalkMode,
            voiceStateLabel: _talkModeActive ? _voiceStateLabel : null,
          ),
            ],
          ), // end Column

          // Talk Mode overlay (covers screen when active in talk-mode)
          if (_talkModeActive && ref.watch(settingsProvider).voiceMode == 'talk-mode')
            Positioned.fill(
              child: TalkModeOverlay(
                voiceService: _voiceService,
                onEnd: _toggleTalkMode,
                lang: lang,
              ),
            ),
        ],
      ), // end Stack
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
  final VoidCallback onOpenManager;

  const _AgentTabBar({
    required this.agents,
    required this.activeAgentId,
    required this.onSelect,
    required this.onCreate,
    required this.onDestroy,
    required this.onOpenManager,
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
          // Agent manager button
          Padding(
            padding: const EdgeInsets.only(right: 4),
            child: SizedBox(
              width: 32,
              height: 32,
              child: IconButton(
                onPressed: onOpenManager,
                icon: const Icon(Icons.hub_outlined, size: 17),
                padding: EdgeInsets.zero,
                style: IconButton.styleFrom(
                  backgroundColor: cs.primary.withValues(alpha: 0.1),
                ),
              ),
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

// ── Connection banner (shown when disconnected/reconnecting) ──

class _ConnectionBanner extends StatelessWidget {
  final AsyncValue<ConnectionStatus> wsStatus;
  final String lang;

  const _ConnectionBanner({required this.wsStatus, required this.lang});

  @override
  Widget build(BuildContext context) {
    final isDisconnected = wsStatus.when(
      data: (s) => s == ConnectionStatus.disconnected,
      loading: () => false,
      error: (_, __) => true,
    );
    final isConnecting = wsStatus.when(
      data: (s) => s == ConnectionStatus.connecting,
      loading: () => true,
      error: (_, __) => false,
    );

    if (!isDisconnected && !isConnecting) return const SizedBox.shrink();

    final cs = Theme.of(context).colorScheme;
    final color = isDisconnected ? cs.error : Colors.orange;
    final text = isDisconnected
        ? L10n.t('status.disconnected', lang)
        : L10n.t('status.connecting', lang);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      color: color.withValues(alpha: 0.15),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (isConnecting)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: color,
                ),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Icon(Icons.cloud_off, size: 16, color: color),
            ),
          Text(
            text,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: color,
            ),
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





