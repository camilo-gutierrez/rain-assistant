import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Encoded payload attached to notifications for navigation on tap.
class NotificationPayload {
  final String agentId;
  final String type; // 'permission', 'result', 'error'
  final String? requestId;

  NotificationPayload({
    required this.agentId,
    required this.type,
    this.requestId,
  });

  String encode() => '$type|$agentId|${requestId ?? ''}';

  static NotificationPayload? decode(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    final parts = raw.split('|');
    if (parts.length < 2) return null;
    return NotificationPayload(
      type: parts[0],
      agentId: parts[1],
      requestId: parts.length > 2 && parts[2].isNotEmpty ? parts[2] : null,
    );
  }
}

typedef NotificationTapCallback = void Function(NotificationPayload payload);

/// Wraps [FlutterLocalNotificationsPlugin] with two Android channels:
/// one urgent (permission requests) and one default (info/errors).
class NotificationService {
  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  NotificationTapCallback? onNotificationTap;
  int _nextId = 0;

  // -- Android channels --
  static const _permChannelId = 'rain_permission';
  static const _permChannelName = 'Permission Requests';
  static const _permChannelDesc =
      'Urgent notifications when Rain needs permission to execute a tool';

  static const _infoChannelId = 'rain_info';
  static const _infoChannelName = 'Agent Updates';
  static const _infoChannelDesc =
      'Notifications when an agent completes a task or encounters an error';

  Future<void> init() async {
    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _plugin.initialize(
      settings,
      onDidReceiveNotificationResponse: _onResponse,
    );

    // Request runtime permission on Android 13+
    if (Platform.isAndroid) {
      await _plugin
          .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>()
          ?.requestNotificationsPermission();
    }
  }

  void _onResponse(NotificationResponse response) {
    final payload = NotificationPayload.decode(response.payload);
    if (payload != null) onNotificationTap?.call(payload);
  }

  /// Urgent notification for permission requests (sound + vibration).
  Future<void> showPermissionNotification({
    required String agentId,
    required String tool,
    required String level,
    required String requestId,
    required String title,
    required String body,
  }) async {
    final androidDetails = AndroidNotificationDetails(
      _permChannelId,
      _permChannelName,
      channelDescription: _permChannelDesc,
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
      enableVibration: true,
      vibrationPattern: Int64List.fromList([0, 500, 200, 500]),
      category: AndroidNotificationCategory.alarm,
      fullScreenIntent: true,
      autoCancel: true,
    );
    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
      interruptionLevel: InterruptionLevel.timeSensitive,
    );

    final payload = NotificationPayload(
      agentId: agentId,
      type: 'permission',
      requestId: requestId,
    );

    await _plugin.show(
      _nextId++,
      title,
      body,
      NotificationDetails(android: androidDetails, iOS: iosDetails),
      payload: payload.encode(),
    );

    HapticFeedback.heavyImpact();
  }

  /// Informational notification (task completed, etc.).
  Future<void> showInfoNotification({
    required String agentId,
    required String title,
    required String body,
    String type = 'result',
  }) async {
    const androidDetails = AndroidNotificationDetails(
      _infoChannelId,
      _infoChannelName,
      channelDescription: _infoChannelDesc,
      importance: Importance.defaultImportance,
      priority: Priority.defaultPriority,
      playSound: true,
      enableVibration: false,
      autoCancel: true,
    );
    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    final payload = NotificationPayload(agentId: agentId, type: type);

    await _plugin.show(
      _nextId++,
      title,
      body,
      const NotificationDetails(android: androidDetails, iOS: iosDetails),
      payload: payload.encode(),
    );
  }

  /// Error notification with haptic feedback.
  Future<void> showErrorNotification({
    required String agentId,
    required String title,
    required String body,
  }) async {
    await showInfoNotification(
      agentId: agentId,
      title: title,
      body: body,
      type: 'error',
    );
    HapticFeedback.mediumImpact();
  }

  /// Haptic-only feedback (foreground use, no OS notification).
  void hapticForPermission() {
    HapticFeedback.heavyImpact();
  }
}
