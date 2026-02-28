// TODO(audit#5): Add widget and integration tests (chat flow, agent CRUD, permission flow)
// TODO(audit#8): Add Semantics labels to interactive widgets for accessibility
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/l10n.dart';
import 'app/theme.dart';
import 'models/a2ui.dart';
import 'models/agent.dart';
import 'models/message.dart';
import 'models/rate_limits.dart';
import 'models/subagent_info.dart';
import 'providers/agent_provider.dart';
import 'providers/audio_provider.dart';
import 'providers/connection_provider.dart';
import 'providers/metrics_provider.dart';
import 'providers/directors_provider.dart';
import 'providers/notification_provider.dart';
import 'providers/settings_provider.dart';
import 'services/crash_reporting_service.dart';
import 'services/lifecycle_observer.dart';
import 'services/notification_service.dart';
import 'widgets/permission_alert_dialog.dart';
import 'widgets/toast.dart';
import 'screens/api_key_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/file_browser_screen.dart';
import 'screens/pin_screen.dart';
import 'screens/server_url_screen.dart';
import 'services/websocket_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await CrashReportingService.instance.init(
    appRunner: () => runApp(const ProviderScope(child: RainApp())),
  );
}

class RainApp extends ConsumerWidget {
  const RainApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsProvider);

    return MaterialApp(
      title: 'Rain Assistant',
      debugShowCheckedModeBanner: false,
      theme: RainTheme.light(),
      darkTheme: RainTheme.dark(),
      themeMode: settings.darkMode ? ThemeMode.dark : ThemeMode.light,
      home: const _AppShell(),
    );
  }
}

/// Root shell that manages the auth flow and screen navigation.
class _AppShell extends ConsumerStatefulWidget {
  const _AppShell();

  @override
  ConsumerState<_AppShell> createState() => _AppShellState();
}

enum _AppScreen { loading, serverUrl, pin, apiKey, fileBrowser, chat }

class _AppShellState extends ConsumerState<_AppShell> {
  _AppScreen _screen = _AppScreen.loading;
  StreamSubscription<Map<String, dynamic>>? _wsSub;
  AppLifecycleObserver? _lifecycleObserver;
  Timer? _initTimeout;
  bool _hasRestoredSession = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _lifecycleObserver = AppLifecycleObserver(ref);
      WidgetsBinding.instance.addObserver(_lifecycleObserver!);
    });
    // Safety timeout: if still loading after 15s, force navigate out
    _initTimeout = Timer(const Duration(seconds: 15), () {
      if (mounted && _screen == _AppScreen.loading) {
        setState(() => _screen = _AppScreen.serverUrl);
      }
    });
    _init();
  }

  Future<void> _init() async {
    try {
      // Load persisted settings
      await ref.read(settingsProvider.notifier).loadFromPrefs();

      // Initialize notification system (non-critical, don't block on failure)
      try {
        await ref.read(notificationSettingsProvider.notifier).loadFromPrefs();
        final notifService = ref.read(notificationServiceProvider);
        await notifService.init();
        notifService.onNotificationTap = _onNotificationTap;
      } catch (e) {
        print('[Rain] Notification init failed (non-critical): $e');
      }

      // Initialize background task service (foreground service for keep-alive)
      ref.read(backgroundTaskServiceProvider).init();

      // Configure audio session for background playback (non-critical)
      try {
        await ref.read(audioServiceProvider).initAudioSession();
      } catch (e) {
        print('[Rain] Audio session init failed (non-critical): $e');
      }

      // Load persisted auth state
      final auth = ref.read(authServiceProvider);
      await auth.init();

      if (!mounted) return;

      _initTimeout?.cancel();

      if (auth.serverUrl == null) {
        setState(() => _screen = _AppScreen.serverUrl);
        return;
      }

      ref.read(hasServerUrlProvider.notifier).state = true;

      if (auth.token != null) {
        // Try to reconnect with existing token
        ref.read(isAuthenticatedProvider.notifier).state = true;
        // Restore agent session (cwd, sessionId) from local storage
        _hasRestoredSession =
            await ref.read(agentProvider.notifier).restoreSession();
        _connectWebSocket();
        return;
      }

      setState(() => _screen = _AppScreen.pin);
    } catch (e, stack) {
      _initTimeout?.cancel();
      print('[Rain] Init failed: $e');
      CrashReportingService.instance.captureException(
        e,
        stackTrace: stack,
        context: 'app_init',
      );
      if (mounted) {
        setState(() => _screen = _AppScreen.serverUrl);
      }
    }
  }

  void _connectWebSocket() {
    final auth = ref.read(authServiceProvider);
    final ws = ref.read(webSocketServiceProvider);

    CrashReportingService.instance.addBreadcrumb(
      message: 'WebSocket connecting',
      category: 'connection',
    );

    // Show loading while WebSocket connects
    setState(() => _screen = _AppScreen.loading);

    ws.connect(auth.wsUrl, auth.token!);
    _listenToMessages();

    // Wait for actual connection before advancing to apiKey screen
    late StreamSubscription<ConnectionStatus> sub;
    int errorCount = 0;
    sub = ws.statusStream.listen((status) {
      if (!mounted) {
        sub.cancel();
        return;
      }
      if (status == ConnectionStatus.connected) {
        sub.cancel();
        // api_key_loaded may have arrived during loading — check before
        if (ref.read(apiKeyLoadedProvider)) {
          // Skip file browser if we restored agents with a valid cwd
          if (_hasRestoredSession) {
            _resumeRestoredSession();
            setState(() => _screen = _AppScreen.chat);
          } else {
            setState(() => _screen = _AppScreen.fileBrowser);
          }
        } else {
          setState(() => _screen = _AppScreen.apiKey);
        }
      } else if (status == ConnectionStatus.error) {
        errorCount++;
        // After 2 failed attempts, stop waiting and go back to server URL
        if (errorCount >= 2) {
          sub.cancel();
          ws.disconnect();
          setState(() => _screen = _AppScreen.serverUrl);
        }
      }
    });
  }

  void _listenToMessages() {
    _wsSub?.cancel();
    final ws = ref.read(webSocketServiceProvider);

    _wsSub = ws.messageStream.listen(_handleMessage);

    // Track connection status for toasts
    _statusSub?.cancel();
    _statusSub = ws.statusStream.listen(_handleConnectionStatus);
  }

  bool _wasConnected = false;
  StreamSubscription<ConnectionStatus>? _statusSub;
  DateTime _lastBgNotifUpdate = DateTime(0);

  void _handleConnectionStatus(ConnectionStatus status) {
    if (status == ConnectionStatus.connected && !_wasConnected) {
      _wasConnected = true;
      // Show restored toast only if we previously lost connection
      if (_screen == _AppScreen.chat) {
        final lang = ref.read(settingsProvider).language;
        showToast(context, L10n.t('toast.connectionRestored', lang),
            type: ToastType.success);
      }

      // Resume sessions for all agents
      final agents = ref.read(agentProvider).agents;
      final ws = ref.read(webSocketServiceProvider);
      final settings = ref.read(settingsProvider);
      for (final agent in agents.values) {
        if (agent.cwd != null && agent.sessionId != null && agent.sessionId!.isNotEmpty) {
          ws.send({
            'type': 'set_cwd',
            'path': agent.cwd,
            'agent_id': agent.id,
            'session_id': agent.sessionId,
            'model': settings.aiModel,
            'provider': settings.aiProvider.name,
          });
        }
      }

      // Reload messages from server in case tasks completed while disconnected
      _checkPendingTasks();
    } else if ((status == ConnectionStatus.disconnected ||
                status == ConnectionStatus.error) &&
        _wasConnected) {
      _wasConnected = false;
      // Clear processing state for all agents to avoid infinite loading
      final agentNotifier = ref.read(agentProvider.notifier);
      final agents = ref.read(agentProvider).agents;
      for (final agentId in agents.keys) {
        if (agents[agentId]?.isProcessing ?? false) {
          agentNotifier.finalizeStreaming(agentId);
          agentNotifier.setProcessing(agentId, false);
          agentNotifier.setAgentStatus(agentId, AgentStatus.idle);
        }
      }
      if (_screen == _AppScreen.chat) {
        final lang = ref.read(settingsProvider).language;
        showToast(context, L10n.t('toast.connectionLost', lang),
            type: ToastType.warning,
            duration: const Duration(seconds: 5));
      }
    }
  }

  /// Resume a restored session: re-send set_cwd for each agent and load messages.
  void _resumeRestoredSession() {
    final agents = ref.read(agentProvider).agents;
    final ws = ref.read(webSocketServiceProvider);
    final settings = ref.read(settingsProvider);

    final agentNotifier = ref.read(agentProvider.notifier);
    final lang = settings.language;

    for (final agent in agents.values) {
      if (agent.cwd != null) {
        ws.send({
          'type': 'set_cwd',
          'path': agent.cwd,
          'agent_id': agent.id,
          'model': settings.aiModel,
          'provider': settings.aiProvider.name,
          if (agent.sessionId != null && agent.sessionId!.isNotEmpty)
            'session_id': agent.sessionId,
        });
      }
      // Load messages from server history
      _restoreMessagesFromHistory(agent.id);

      // Detect interrupted tasks (agent was processing when app was killed)
      if (agent.isProcessing) {
        final notifService = ref.read(notificationServiceProvider);
        notifService.showInfoNotification(
          agentId: agent.id,
          title: L10n.t('bg.interruptedTitle', lang, {'agent': agent.label}),
          body: L10n.t('bg.interruptedBody', lang),
        );
        agentNotifier.setProcessing(agent.id, false);
        agentNotifier.setAgentStatus(agent.id, AgentStatus.idle);
      }
    }
  }

  /// Fetch the latest auto-saved conversation for an agent and load its messages.
  Future<void> _restoreMessagesFromHistory(String agentId) async {
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;

      // Try to load the active auto-save for this agent
      final res = await dio.get('/history/conv_${agentId}_active');
      if (res.statusCode == 200) {
        final data = res.data as Map<String, dynamic>;
        final rawMessages = data['messages'] as List? ?? [];
        if (rawMessages.isEmpty) return;

        final messages = rawMessages
            .map((m) => Message.fromJson(m as Map<String, dynamic>))
            .toList();

        final agentNotifier = ref.read(agentProvider.notifier);
        agentNotifier.setMessages(agentId, messages);
        agentNotifier.setHistoryLoaded(agentId, true);

        // Restore session_id if present
        final sessionId = data['sessionId'] as String?;
        if (sessionId != null && sessionId.isNotEmpty) {
          agentNotifier.setAgentSessionId(agentId, sessionId);
        }
      }
    } catch (_) {
      // Non-critical — user just sees empty chat
    }
  }

  void _handleMessage(Map<String, dynamic> msg) {
    final type = msg['type'] as String?;
    if (type == null) return;

    final agentNotifier = ref.read(agentProvider.notifier);
    final agentId = (msg['agent_id'] as String?) ??
        ref.read(agentProvider).activeAgentId;

    switch (type) {
      case '_unauthorized':
        ref.read(authServiceProvider).clearToken();
        ref.read(isAuthenticatedProvider.notifier).state = false;
        ref.read(agentProvider.notifier).clearSession();
        _hasRestoredSession = false;
        final lang = ref.read(settingsProvider).language;
        if (mounted) {
          showToast(context, L10n.t('toast.sessionExpired', lang),
              type: ToastType.warning,
              duration: const Duration(seconds: 4));
        }
        setState(() => _screen = _AppScreen.pin);

      case 'api_key_loaded':
        ref.read(apiKeyLoadedProvider.notifier).state = true;
        ref.read(currentProviderProvider.notifier).state =
            msg['provider'] ?? 'claude';
        CrashReportingService.instance.setTag('provider', msg['provider'] ?? 'claude');
        if (_screen == _AppScreen.apiKey) {
          if (_hasRestoredSession) {
            _resumeRestoredSession();
            setState(() => _screen = _AppScreen.chat);
          } else {
            setState(() => _screen = _AppScreen.fileBrowser);
          }
        }

      case 'status':
        ref.read(statusTextProvider.notifier).state = msg['text'] ?? '';
        if (msg['cwd'] != null && agentId.isNotEmpty) {
          agentNotifier.setAgentCwd(agentId, msg['cwd']);
          agentNotifier.persistSession();
        }
        // Propagate status text to persistent notification (throttled)
        if ((msg['text'] as String?)?.isNotEmpty == true) {
          final statusAgent = ref.read(agentProvider).agents[agentId];
          _updateBgNotificationThrottled(
            title: L10n.t('bg.working', ref.read(settingsProvider).language),
            body: '${statusAgent?.label ?? agentId}: ${msg['text']}',
          );
        }

      case 'assistant_text':
        if (agentId.isEmpty) break;
        agentNotifier.updateStreamingMessage(agentId, msg['text'] ?? '');
        agentNotifier.incrementUnread(agentId);
        // Update persistent notification when agent starts responding (throttled)
        final textAgent = ref.read(agentProvider).agents[agentId];
        final textLang = ref.read(settingsProvider).language;
        _updateBgNotificationThrottled(
          title: L10n.t('bg.working', textLang),
          body: L10n.t('bg.responding', textLang, {
            'agent': textAgent?.label ?? agentId,
          }),
        );

      case 'tool_use':
        if (agentId.isEmpty) break;
        agentNotifier.finalizeStreaming(agentId);
        agentNotifier.incrementUnread(agentId);
        // Update foreground service notification with current tool (throttled)
        final agent = ref.read(agentProvider).agents[agentId];
        final lang = ref.read(settingsProvider).language;
        final toolName = msg['tool'] ?? '';
        _updateBgNotificationThrottled(
          title: L10n.t('bg.working', lang),
          body: L10n.t('bg.tool', lang, {
            'agent': agent?.label ?? agentId,
            'tool': toolName,
          }),
        );
        agentNotifier.appendMessage(
          agentId,
          ToolUseMessage(
            id: UniqueKey().toString(),
            tool: msg['tool'] ?? '',
            input: Map<String, dynamic>.from(msg['input'] ?? {}),
            toolUseId: msg['id'] ?? '',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );

      case 'tool_result':
        if (agentId.isEmpty) break;
        agentNotifier.appendMessage(
          agentId,
          ToolResultMessage(
            id: UniqueKey().toString(),
            content: msg['content'] ?? '',
            isError: msg['is_error'] ?? false,
            toolUseId: msg['tool_use_id'] ?? '',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );

      case 'result':
        if (agentId.isEmpty) break;
        agentNotifier.finalizeStreaming(agentId);

        // Build metrics system message
        final cost = msg['cost'];
        final durationMs = msg['duration_ms'];
        final numTurns = msg['num_turns'];
        final parts = <String>[];
        if (durationMs != null) {
          parts.add('${(durationMs / 1000).toStringAsFixed(1)}s');
        }
        if (numTurns != null) parts.add('$numTurns turns');
        if (cost != null) parts.add('\$${cost.toStringAsFixed(4)}');
        if (parts.isNotEmpty) {
          agentNotifier.appendMessage(agentId, SystemMessage.create(parts.join(' | ')));
        }

        if (msg['session_id'] != null) {
          agentNotifier.setAgentSessionId(agentId, msg['session_id']);
          agentNotifier.persistSession();
        }

        agentNotifier.setProcessing(agentId, false);
        agentNotifier.setInterruptPending(agentId, false);
        agentNotifier.setAgentStatus(agentId, AgentStatus.done);
        _checkStopBackgroundTask();

        // TTS auto-play
        final settings = ref.read(settingsProvider);
        if (settings.ttsEnabled && settings.ttsAutoPlay) {
          final agent = ref.read(agentProvider).agents[agentId];
          if (agent != null) {
            // Find the last assistant message text
            final lastAssistant = agent.messages.reversed
                .whereType<AssistantMessage>()
                .firstOrNull;
            if (lastAssistant != null && lastAssistant.text.isNotEmpty) {
              ref
                  .read(audioServiceProvider)
                  .synthesize(lastAssistant.text, settings.ttsVoice);
            }
          }
        }
        _dispatchNotification('result', agentId, msg);

        // Auto-save conversation
        _autoSaveConversation(agentId);

      case 'error':
        if (agentId.isEmpty) break;
        agentNotifier.finalizeStreaming(agentId);
        agentNotifier.incrementUnread(agentId);
        agentNotifier.appendMessage(
          agentId,
          SystemMessage.create('Error: ${msg['text'] ?? 'Unknown'}'),
        );
        agentNotifier.setProcessing(agentId, false);
        agentNotifier.setAgentStatus(agentId, AgentStatus.error);
        _checkStopBackgroundTask();
        _dispatchNotification('error', agentId, msg);

      case 'permission_request':
        if (agentId.isEmpty) break;
        // Safety net: auto-respond if agent has auto-approve enabled
        final reqAgent = agentNotifier.state.agents[agentId];
        if (reqAgent != null && reqAgent.autoApprove) {
          final ws = ref.read(webSocketServiceProvider);
          ws.send({
            'type': 'permission_response',
            'request_id': msg['request_id'] ?? '',
            'agent_id': agentId,
            'approved': true,
          });
          break;
        }
        agentNotifier.finalizeStreaming(agentId);
        agentNotifier.setProcessing(agentId, false);
        agentNotifier.incrementUnread(agentId);
        agentNotifier.appendMessage(
          agentId,
          PermissionRequestMessage(
            id: UniqueKey().toString(),
            requestId: msg['request_id'] ?? '',
            tool: msg['tool'] ?? '',
            input: Map<String, dynamic>.from(msg['input'] ?? {}),
            level: PermissionLevel.values.firstWhere(
              (e) => e.name == msg['level'],
              orElse: () => PermissionLevel.yellow,
            ),
            reason: msg['reason'] ?? '',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );
        _dispatchNotification('permission_request', agentId, msg);

      case 'auto_approve_changed':
        if (agentId.isNotEmpty) {
          agentNotifier.setAutoApprove(agentId, msg['enabled'] == true);
        }

      case 'agent_destroyed':
        if (agentId.isNotEmpty) agentNotifier.removeAgent(agentId);

      case 'mode_changed':
        if (agentId.isEmpty) break;
        final mode = msg['mode'] == 'computer_use'
            ? AgentMode.computerUse
            : AgentMode.coding;
        agentNotifier.setAgentMode(agentId, mode);
        if (msg['display_info'] != null) {
          agentNotifier.setDisplayInfo(
            agentId,
            DisplayInfo.fromJson(Map<String, dynamic>.from(msg['display_info'])),
          );
        }

      case 'computer_screenshot':
        if (agentId.isEmpty) break;
        agentNotifier.updateLastScreenshot(agentId, msg['image'] ?? '');
        agentNotifier.appendMessage(
          agentId,
          ComputerScreenshotMessage(
            id: UniqueKey().toString(),
            image: msg['image'] ?? '',
            action: msg['action'] ?? '',
            description: msg['description'] ?? '',
            iteration: msg['iteration'] ?? 0,
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );

      case 'computer_action':
        if (agentId.isEmpty) break;
        agentNotifier.appendMessage(
          agentId,
          ComputerActionMessage(
            id: UniqueKey().toString(),
            tool: msg['tool'] ?? '',
            action: msg['action'] ?? '',
            input: Map<String, dynamic>.from(msg['input'] ?? {}),
            description: msg['description'] ?? '',
            iteration: msg['iteration'] ?? 0,
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );
        agentNotifier.incrementComputerIteration(agentId);

      case 'computer_use_paused':
        if (agentId.isEmpty) break;
        final requestId = msg['request_id'] as String? ?? '';
        final iterations = msg['iterations'] as int? ?? 0;
        final maxIterations = msg['max_iterations'] as int? ?? 50;
        if (mounted && requestId.isNotEmpty) {
          _showComputerUsePausedDialog(agentId, requestId, iterations, maxIterations);
        }

      case 'subagent_spawned':
        final subAgentId = msg['agent_id'] as String? ?? '';
        final parentId = msg['parent_agent_id'] as String? ?? agentId;
        if (parentId.isEmpty) break;

        // Track active sub-agent
        agentNotifier.addSubAgent(
          parentId,
          SubAgentInfo(
            id: subAgentId,
            shortName: msg['short_name'] as String? ?? 'Sub',
            parentId: parentId,
            task: msg['task'] as String? ?? '',
            status: 'running',
          ),
        );

        // Show spawned message in parent's chat
        agentNotifier.appendMessage(
          parentId,
          SubAgentMessage(
            id: UniqueKey().toString(),
            subAgentId: subAgentId,
            task: msg['task'] as String? ?? '',
            status: 'spawned',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );

      case 'subagent_completed':
        final subAgentId = msg['agent_id'] as String? ?? '';
        final parentId = msg['parent_agent_id'] as String? ?? agentId;
        if (parentId.isEmpty || subAgentId.isEmpty) break;

        final finalStatus = msg['status'] as String? ?? 'completed';

        // Update tracking status
        agentNotifier.updateSubAgentStatus(parentId, subAgentId, finalStatus);

        // Show completion message in parent's chat
        agentNotifier.appendMessage(
          parentId,
          SubAgentMessage(
            id: UniqueKey().toString(),
            subAgentId: subAgentId,
            task: '',
            status: finalStatus,
            preview: msg['result_preview'] as String? ?? '',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );

        // Remove from active tracking after 3 seconds
        Future.delayed(const Duration(seconds: 3), () {
          agentNotifier.removeSubAgent(parentId, subAgentId);
        });

      // ── A2UI surfaces ──
      case 'a2ui_surface':
        if (agentId.isEmpty) break;
        final surfaceJson = msg['surface'];
        if (surfaceJson != null) {
          try {
            final surface = A2UISurface.fromJson(
              Map<String, dynamic>.from(surfaceJson as Map),
            );
            agentNotifier.upsertSurface(agentId, surface);
            agentNotifier.incrementUnread(agentId);
          } catch (e) {
            agentNotifier.appendMessage(
              agentId,
              SystemMessage.create('A2UI render error: $e'),
            );
          }
        }

      case 'a2ui_update':
        if (agentId.isEmpty) break;
        final surfaceId = msg['surface_id'] as String? ?? '';
        final updates = msg['updates'];
        if (surfaceId.isNotEmpty && updates is List) {
          try {
            agentNotifier.applySurfaceUpdates(
              agentId,
              surfaceId,
              updates
                  .map((u) => Map<String, dynamic>.from(u as Map))
                  .toList(),
            );
          } catch (e) {
            agentNotifier.appendMessage(
              agentId,
              SystemMessage.create('A2UI update error: $e'),
            );
          }
        }

      case 'model_info':
        if (msg['model'] != null) {
          ref.read(currentModelProvider.notifier).state = msg['model'];
          CrashReportingService.instance.setTag('model', msg['model']);
        }

      case '_reconnecting':
        if (mounted) {
          final lang = ref.read(settingsProvider).language;
          showToast(context, L10n.t('toast.connectionFailed', lang),
              type: ToastType.warning);
        }

      case 'rate_limits':
        if (msg['limits'] != null) {
          ref.read(rateLimitsProvider.notifier).state =
              RateLimits.fromJson(Map<String, dynamic>.from(msg['limits']));
        }

      case 'director_event':
        final directorsNotifier = ref.read(directorsProvider.notifier);
        final event = msg['event'] as String? ?? '';
        if (event == 'run_complete' || event == 'task_complete') {
          directorsNotifier.incrementUnread();
          final directorId = msg['director_id'] as String? ?? '';
          if (directorId.isNotEmpty) {
            directorsNotifier.onDirectorRunComplete(directorId);
          }
        }
    }
  }

  Future<void> _autoSaveConversation(String agentId) async {
    try {
      final agent = ref.read(agentProvider).agents[agentId];
      if (agent == null || agent.messages.isEmpty) return;

      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final now = DateTime.now().millisecondsSinceEpoch;

      // Use first user message as label
      final firstUserMsg = agent.messages
          .whereType<UserMessage>()
          .firstOrNull;
      final preview = firstUserMsg?.text ?? '';
      final label = preview.length > 50
          ? '${preview.substring(0, 50)}...'
          : preview.isEmpty
              ? 'Conversation'
              : preview;

      // Calculate total cost from SystemMessage metrics
      double totalCost = 0;
      for (final m in agent.messages) {
        if (m is SystemMessage) {
          final match = RegExp(r'\$(\d+\.\d+)').firstMatch(m.text);
          if (match != null) {
            totalCost += double.tryParse(match.group(1)!) ?? 0;
          }
        }
      }

      // Stable ID per agent — server upserts, no duplicates
      await dio.post('/history', data: {
        'id': 'conv_${agent.id}_active',
        'createdAt': now,
        'updatedAt': now,
        'label': label,
        'cwd': agent.cwd ?? '',
        'messageCount': agent.messages.length,
        'preview': preview,
        'totalCost': totalCost,
        'version': 1,
        'agentId': agent.id,
        'sessionId': agent.sessionId ?? '',
        'messages': agent.messages.map((m) => m.toJson()).toList(),
      });

      // Persist agent metadata locally after successful save
      ref.read(agentProvider.notifier).persistSession();
    } catch (_) {
      // Silent fail for auto-save — non-critical
    }
  }

  void _showComputerUsePausedDialog(
      String agentId, String requestId, int iterations, int maxIterations) {
    final lang = ref.read(settingsProvider).language;
    var extraIterations = 50.0;

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          icon: Icon(Icons.pause_circle, size: 40, color: Theme.of(ctx).colorScheme.primary),
          title: Text(L10n.t('cu.pausedTitle', lang)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(L10n.t('cu.pausedBody', lang, {
                'current': '$iterations',
                'max': '$maxIterations',
              })),
              const SizedBox(height: 16),
              Text(
                L10n.t('cu.pausedExtra', lang, {'n': '${extraIterations.round()}'}),
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              Slider(
                value: extraIterations,
                min: 10,
                max: 150,
                divisions: 14,
                label: '${extraIterations.round()}',
                onChanged: (v) => setDialogState(() => extraIterations = v),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(ctx).pop();
                ref.read(webSocketServiceProvider).send({
                  'type': 'computer_use_deny_continue',
                  'request_id': requestId,
                  'agent_id': agentId,
                });
              },
              child: Text(L10n.t('cu.stop', lang)),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(ctx).pop();
                ref.read(webSocketServiceProvider).send({
                  'type': 'computer_use_continue',
                  'request_id': requestId,
                  'agent_id': agentId,
                  'extra_iterations': extraIterations.round(),
                });
              },
              child: Text(L10n.t('cu.continue', lang)),
            ),
          ],
        ),
      ),
    );
  }

  /// Reload messages from server for all agents (after reconnect).
  Future<void> _checkPendingTasks() async {
    final agents = ref.read(agentProvider).agents;
    for (final agent in agents.values) {
      if (agent.sessionId != null && agent.sessionId!.isNotEmpty) {
        _restoreMessagesFromHistory(agent.id);
      }
    }
  }

  /// Throttled update of the persistent background notification (max once per 2s).
  void _updateBgNotificationThrottled({
    required String title,
    required String body,
  }) {
    final now = DateTime.now();
    if (now.difference(_lastBgNotifUpdate).inMilliseconds < 2000) return;
    _lastBgNotifUpdate = now;
    final bg = ref.read(backgroundTaskServiceProvider);
    if (bg.isRunning) {
      bg.updateNotification(title: title, body: body);
    }
  }

  /// Stop the foreground service if no agents are still processing.
  void _checkStopBackgroundTask() {
    final agents = ref.read(agentProvider).agents;
    final anyProcessing = agents.values.any((a) => a.isProcessing);
    if (!anyProcessing) {
      ref.read(backgroundTaskServiceProvider).stop();
    }
  }

  void _onNotificationTap(NotificationPayload payload) {
    if (_screen != _AppScreen.chat) {
      setState(() => _screen = _AppScreen.chat);
    }
    final agentNotifier = ref.read(agentProvider.notifier);
    if (ref.read(agentProvider).agents.containsKey(payload.agentId)) {
      agentNotifier.setActiveAgent(payload.agentId);
    }
  }

  void _dispatchNotification(
      String type, String agentId, Map<String, dynamic> msg) {
    final notifSettings = ref.read(notificationSettingsProvider);
    final notifService = ref.read(notificationServiceProvider);
    final lifecycle = ref.read(appLifecycleProvider);
    final lang = ref.read(settingsProvider).language;
    final agent = ref.read(agentProvider).agents[agentId];
    final agentLabel = agent?.label ?? agentId;
    final activeAgentId = ref.read(agentProvider).activeAgentId;
    final isBackground = lifecycle != AppLifecycleState.resumed;
    final isOnDifferentAgent = agentId != activeAgentId;

    switch (type) {
      case 'permission_request':
        if (!notifSettings.permissionNotifications) return;

        final tool = msg['tool'] ?? '';
        final level = msg['level'] ?? 'yellow';
        final requestId = msg['request_id'] ?? '';
        final title = lang == 'es'
            ? 'Permiso requerido - $agentLabel'
            : 'Permission required - $agentLabel';
        final body = lang == 'es'
            ? 'Herramienta: $tool (${level.toString().toUpperCase()})'
            : 'Tool: $tool (${level.toString().toUpperCase()})';

        if (isBackground) {
          notifService.showPermissionNotification(
            agentId: agentId,
            tool: tool,
            level: level,
            requestId: requestId,
            title: title,
            body: body,
          );
        } else if (isOnDifferentAgent &&
            notifSettings.inAppDialogs &&
            _screen == _AppScreen.chat) {
          showPermissionAlertDialog(
            context,
            ref,
            agentId: agentId,
            agentLabel: agentLabel,
            tool: tool,
            requestId: requestId,
            level: PermissionLevel.values.firstWhere(
              (e) => e.name == level,
              orElse: () => PermissionLevel.yellow,
            ),
          );
          if (notifSettings.hapticFeedback) {
            notifService.hapticForPermission();
          }
        } else {
          if (notifSettings.hapticFeedback) {
            notifService.hapticForPermission();
          }
        }

      case 'result':
        if (!notifSettings.resultNotifications) return;
        if (!isBackground && !isOnDifferentAgent) return;
        final resultTitle = lang == 'es'
            ? '$agentLabel completado'
            : '$agentLabel completed';

        // Build rich body: metrics + response preview
        final resultCost = msg['cost'];
        final resultDuration = msg['duration_ms'];
        final resultTurns = msg['num_turns'];
        final metricParts = <String>[];
        if (resultDuration != null) {
          metricParts.add('${(resultDuration / 1000).toStringAsFixed(1)}s');
        }
        if (resultTurns != null) metricParts.add('$resultTurns turns');
        if (resultCost != null) {
          metricParts.add('\$${resultCost.toStringAsFixed(4)}');
        }

        // Preview of the last assistant message
        final lastAssistantMsg = agent?.messages.reversed
            .whereType<AssistantMessage>()
            .firstOrNull;
        final preview = lastAssistantMsg?.text ?? '';
        final previewTruncated = preview.length > 100
            ? '${preview.substring(0, 100)}...'
            : preview;

        var resultBody = metricParts.isNotEmpty ? metricParts.join(' | ') : '';
        if (previewTruncated.isNotEmpty) {
          resultBody = resultBody.isEmpty
              ? previewTruncated
              : '$resultBody\n$previewTruncated';
        }
        if (resultBody.isEmpty) {
          resultBody = lang == 'es' ? 'Tarea terminada' : 'Task finished';
        }

        notifService.showInfoNotification(
          agentId: agentId,
          title: resultTitle,
          body: resultBody,
        );

      case 'error':
        if (!notifSettings.errorNotifications) return;
        if (!isBackground && !isOnDifferentAgent) return;
        final title = lang == 'es' ? 'Error - $agentLabel' : 'Error - $agentLabel';
        final body = msg['text'] ?? (lang == 'es' ? 'Error desconocido' : 'Unknown error');
        notifService.showErrorNotification(
          agentId: agentId,
          title: title,
          body: body,
        );
    }
  }

  @override
  void dispose() {
    _initTimeout?.cancel();
    _wsSub?.cancel();
    _statusSub?.cancel();
    if (_lifecycleObserver != null) {
      WidgetsBinding.instance.removeObserver(_lifecycleObserver!);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return switch (_screen) {
      _AppScreen.loading => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      _AppScreen.serverUrl => ServerUrlScreen(
          onConnected: () => setState(() => _screen = _AppScreen.pin),
        ),
      _AppScreen.pin => PinScreen(
          onAuthenticated: () => _connectWebSocket(),
        ),
      _AppScreen.apiKey => ApiKeyScreen(
          onConfigured: () => setState(() => _screen = _AppScreen.fileBrowser),
        ),
      _AppScreen.fileBrowser => FileBrowserScreen(
          onSelected: () => setState(() => _screen = _AppScreen.chat),
        ),
      _AppScreen.chat => const ChatScreen(),
    };
  }
}
