import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/agent_provider.dart';
import '../providers/notification_provider.dart';

/// Observes app lifecycle and updates [appLifecycleProvider].
/// Persists agent session when app goes to background.
class AppLifecycleObserver extends WidgetsBindingObserver {
  final WidgetRef ref;

  AppLifecycleObserver(this.ref);

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    ref.read(appLifecycleProvider.notifier).state = state;

    // Persist agent session when app is paused/backgrounded
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      ref.read(agentProvider.notifier).persistSession();
    }
  }
}
