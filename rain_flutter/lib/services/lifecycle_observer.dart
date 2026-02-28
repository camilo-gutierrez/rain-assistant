import 'dart:io';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../providers/agent_provider.dart';
import '../providers/notification_provider.dart';
import '../providers/settings_provider.dart';

/// Observes app lifecycle and updates [appLifecycleProvider].
/// Persists agent session when app goes to background.
/// Starts/stops the foreground service to keep WebSocket alive.
class AppLifecycleObserver extends WidgetsBindingObserver {
  final WidgetRef ref;
  bool _batteryCheckDone = false;

  AppLifecycleObserver(this.ref);

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    ref.read(appLifecycleProvider.notifier).state = state;

    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      ref.read(agentProvider.notifier).persistSession();
      _maybeStartBackgroundTask();
    } else if (state == AppLifecycleState.resumed) {
      _stopBackgroundTaskIfIdle();
    }
  }

  /// Start the foreground service if any agent is processing.
  void _maybeStartBackgroundTask() {
    final agents = ref.read(agentProvider).agents;
    final workingAgent = agents.values
        .where((a) => a.isProcessing)
        .firstOrNull;

    if (workingAgent != null) {
      final lang = ref.read(settingsProvider).language;
      ref.read(backgroundTaskServiceProvider).start(
        title: L10n.t('bg.working', lang),
        body: L10n.t('bg.processing', lang, {'agent': workingAgent.label}),
      );

      // One-time battery optimization check (Android only)
      if (!_batteryCheckDone && Platform.isAndroid) {
        _batteryCheckDone = true;
        _checkBatteryOptimization(workingAgent.id, lang);
      }
    }
  }

  /// Warn user if battery optimization may kill the background service.
  Future<void> _checkBatteryOptimization(String agentId, String lang) async {
    try {
      final bgService = ref.read(backgroundTaskServiceProvider);
      final isExempt = await bgService.isBatteryOptimizationDisabled();
      if (!isExempt) {
        final notifService = ref.read(notificationServiceProvider);
        notifService.showInfoNotification(
          agentId: agentId,
          title: L10n.t('bg.batteryTitle', lang),
          body: L10n.t('bg.batteryBody', lang),
        );
      }
    } catch (_) {
      // Non-critical — skip silently
    }
  }

  /// Stop the foreground service if no agents are processing.
  void _stopBackgroundTaskIfIdle() {
    final bgService = ref.read(backgroundTaskServiceProvider);
    if (!bgService.isRunning) return;

    final agents = ref.read(agentProvider).agents;
    final anyProcessing = agents.values.any((a) => a.isProcessing);
    if (!anyProcessing) {
      bgService.stop();
    }
  }
}
