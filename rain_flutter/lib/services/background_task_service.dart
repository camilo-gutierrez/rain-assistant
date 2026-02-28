import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

/// Manages an Android foreground service (+ iOS background mode) to keep
/// the Flutter process alive while agents are working in the background.
///
/// The WebSocket and all Dart state remain in the main isolate.
/// This service only prevents the OS from killing the process.
class BackgroundTaskService {
  bool _isRunning = false;
  bool get isRunning => _isRunning;

  /// Configure the foreground task. Call once during app startup.
  void init() {
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'rain_background',
        channelName: 'Rain Background Task',
        channelDescription: 'Keeps Rain connected while agents are working',
        channelImportance: NotificationChannelImportance.LOW,
        priority: NotificationPriority.LOW,
      ),
      iosNotificationOptions: const IOSNotificationOptions(
        showNotification: true,
        playSound: false,
      ),
      foregroundTaskOptions: ForegroundTaskOptions(
        eventAction: ForegroundTaskEventAction.repeat(30000),
        autoRunOnBoot: false,
        autoRunOnMyPackageReplaced: false,
        allowWakeLock: true,
        allowWifiLock: true,
      ),
    );
  }

  /// Start the foreground service with a persistent notification.
  Future<void> start({required String title, required String body}) async {
    if (_isRunning) return;
    _isRunning = true;

    await FlutterForegroundTask.startService(
      notificationTitle: title,
      notificationText: body,
      callback: _backgroundCallback,
    );

    // Prevent CPU deep sleep while agents are working
    await WakelockPlus.enable();
  }

  /// Update the persistent notification text.
  Future<void> updateNotification({
    required String title,
    required String body,
  }) async {
    if (!_isRunning) return;
    await FlutterForegroundTask.updateService(
      notificationTitle: title,
      notificationText: body,
    );
  }

  /// Stop the foreground service.
  Future<void> stop() async {
    if (!_isRunning) return;
    _isRunning = false;
    await FlutterForegroundTask.stopService();
    await WakelockPlus.disable();
  }

  /// Check if battery optimization is disabled for this app.
  Future<bool> isBatteryOptimizationDisabled() async {
    return await FlutterForegroundTask.isIgnoringBatteryOptimizations;
  }

  /// Request the user to disable battery optimization.
  Future<void> requestBatteryOptimizationExemption() async {
    await FlutterForegroundTask.requestIgnoreBatteryOptimization();
  }
}

// Top-level callback required by flutter_foreground_task.
// We keep everything in the main isolate, so this is a no-op.
@pragma('vm:entry-point')
void _backgroundCallback() {
  FlutterForegroundTask.setTaskHandler(_NoOpTaskHandler());
}

class _NoOpTaskHandler extends TaskHandler {
  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {}

  @override
  void onRepeatEvent(DateTime timestamp) {}

  @override
  Future<void> onDestroy(DateTime timestamp) async {}
}
