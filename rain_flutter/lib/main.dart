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
import 'providers/agent_provider.dart';
import 'providers/audio_provider.dart';
import 'providers/connection_provider.dart';
import 'providers/metrics_provider.dart';
import 'providers/notification_provider.dart';
import 'providers/settings_provider.dart';
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

void main() {
  runApp(const ProviderScope(child: RainApp()));
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
        _connectWebSocket();
        return;
      }

      setState(() => _screen = _AppScreen.pin);
    } catch (e) {
      _initTimeout?.cancel();
      print('[Rain] Init failed: $e');
      if (mounted) {
        setState(() => _screen = _AppScreen.serverUrl);
      }
    }
  }

  void _connectWebSocket() {
    final auth = ref.read(authServiceProvider);
    final ws = ref.read(webSocketServiceProvider);

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
          setState(() => _screen = _AppScreen.fileBrowser);
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
        if (_screen == _AppScreen.apiKey) {
          setState(() => _screen = _AppScreen.fileBrowser);
        }

      case 'status':
        ref.read(statusTextProvider.notifier).state = msg['text'] ?? '';
        if (msg['cwd'] != null && agentId.isNotEmpty) {
          agentNotifier.setAgentCwd(agentId, msg['cwd']);
        }

      case 'assistant_text':
        if (agentId.isEmpty) break;
        agentNotifier.updateStreamingMessage(agentId, msg['text'] ?? '');
        agentNotifier.incrementUnread(agentId);

      case 'tool_use':
        if (agentId.isEmpty) break;
        agentNotifier.finalizeStreaming(agentId);
        agentNotifier.incrementUnread(agentId);
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
        }

        agentNotifier.setProcessing(agentId, false);
        agentNotifier.setInterruptPending(agentId, false);
        agentNotifier.setAgentStatus(agentId, AgentStatus.done);

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
        _dispatchNotification('error', agentId, msg);

      case 'permission_request':
        if (agentId.isEmpty) break;
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

      case 'sub_agent':
        if (agentId.isEmpty) break;
        agentNotifier.appendMessage(
          agentId,
          SubAgentMessage(
            id: UniqueKey().toString(),
            subAgentId: msg['sub_agent_id'] ?? '',
            task: msg['task'] ?? '',
            status: msg['status'] ?? 'spawned',
            preview: msg['preview'] ?? '',
            timestamp: DateTime.now().millisecondsSinceEpoch,
          ),
        );

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

      await dio.post('/history', data: {
        'id': 'conv_${agent.id}_$now',
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
    } catch (_) {
      // Silent fail for auto-save — non-critical
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
        final title = lang == 'es'
            ? '$agentLabel completado'
            : '$agentLabel completed';
        final cost = msg['cost'];
        final body = cost != null
            ? (lang == 'es'
                ? 'Costo: \$${cost.toStringAsFixed(4)}'
                : 'Cost: \$${cost.toStringAsFixed(4)}')
            : (lang == 'es' ? 'Tarea terminada' : 'Task finished');
        notifService.showInfoNotification(
          agentId: agentId,
          title: title,
          body: body,
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
