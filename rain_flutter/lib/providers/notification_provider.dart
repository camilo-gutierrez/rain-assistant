import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/notification_service.dart';

class NotificationSettings {
  final bool permissionNotifications;
  final bool resultNotifications;
  final bool errorNotifications;
  final bool hapticFeedback;
  final bool inAppDialogs;

  const NotificationSettings({
    this.permissionNotifications = true,
    this.resultNotifications = true,
    this.errorNotifications = true,
    this.hapticFeedback = true,
    this.inAppDialogs = true,
  });

  NotificationSettings copyWith({
    bool? permissionNotifications,
    bool? resultNotifications,
    bool? errorNotifications,
    bool? hapticFeedback,
    bool? inAppDialogs,
  }) =>
      NotificationSettings(
        permissionNotifications:
            permissionNotifications ?? this.permissionNotifications,
        resultNotifications: resultNotifications ?? this.resultNotifications,
        errorNotifications: errorNotifications ?? this.errorNotifications,
        hapticFeedback: hapticFeedback ?? this.hapticFeedback,
        inAppDialogs: inAppDialogs ?? this.inAppDialogs,
      );
}

class NotificationSettingsNotifier extends StateNotifier<NotificationSettings> {
  NotificationSettingsNotifier() : super(const NotificationSettings());

  Future<void> loadFromPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    state = NotificationSettings(
      permissionNotifications: prefs.getBool('notif_permission') ?? true,
      resultNotifications: prefs.getBool('notif_result') ?? true,
      errorNotifications: prefs.getBool('notif_error') ?? true,
      hapticFeedback: prefs.getBool('notif_haptic') ?? true,
      inAppDialogs: prefs.getBool('notif_dialog') ?? true,
    );
  }

  Future<void> _save(String key, bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(key, value);
  }

  void setPermissionNotifications(bool v) {
    state = state.copyWith(permissionNotifications: v);
    _save('notif_permission', v);
  }

  void setResultNotifications(bool v) {
    state = state.copyWith(resultNotifications: v);
    _save('notif_result', v);
  }

  void setErrorNotifications(bool v) {
    state = state.copyWith(errorNotifications: v);
    _save('notif_error', v);
  }

  void setHapticFeedback(bool v) {
    state = state.copyWith(hapticFeedback: v);
    _save('notif_haptic', v);
  }

  void setInAppDialogs(bool v) {
    state = state.copyWith(inAppDialogs: v);
    _save('notif_dialog', v);
  }
}

final notificationSettingsProvider =
    StateNotifierProvider<NotificationSettingsNotifier, NotificationSettings>(
        (ref) {
  return NotificationSettingsNotifier();
});

/// Singleton provider for the notification service.
final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService();
});

/// Tracks whether the app is in the foreground or background.
final appLifecycleProvider = StateProvider<AppLifecycleState>((ref) {
  return AppLifecycleState.resumed;
});
