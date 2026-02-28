import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

/// Centralized crash reporting service wrapping Sentry.
///
/// Set your DSN in [sentryDsn] before building for production.
/// If the DSN is empty, crash reporting degrades gracefully to console logging.
class CrashReportingService {
  CrashReportingService._();

  static final instance = CrashReportingService._();

  /// Replace with your Sentry DSN from https://sentry.io
  /// Leave empty to disable Sentry (errors will only print to console).
  static const sentryDsn = String.fromEnvironment(
    'SENTRY_DSN',
    defaultValue: '',
  );

  bool _initialized = false;
  bool get isEnabled => _initialized && sentryDsn.isNotEmpty;

  /// Initialize Sentry. Call this from [main] before [runApp].
  ///
  /// Returns the [AppRunner] callback that wraps `runApp`.
  /// Usage:
  /// ```dart
  /// await CrashReportingService.instance.init(
  ///   appRunner: () => runApp(const MyApp()),
  /// );
  /// ```
  Future<void> init({required AppRunner appRunner}) async {
    if (sentryDsn.isEmpty) {
      if (kDebugMode) {
        print('[CrashReporting] No SENTRY_DSN configured — running without Sentry');
      }
      // Still set up Flutter error handlers for console logging
      _setupLocalErrorHandlers();
      await appRunner();
      return;
    }

    await SentryFlutter.init(
      (options) {
        options.dsn = sentryDsn;
        options.environment = kDebugMode ? 'debug' : 'production';
        options.tracesSampleRate = kDebugMode ? 1.0 : 0.2;
        options.attachScreenshot = true;
        options.reportSilentFlutterErrors = true;
        options.enableAutoNativeBreadcrumbs = true;
        options.enableAppLifecycleBreadcrumbs = true;
        options.enableAutoPerformanceTracing = true;
        options.maxBreadcrumbs = 100;

        // Don't send PII by default
        options.sendDefaultPii = false;

        // Filter out debug-mode noise
        if (kDebugMode) {
          options.beforeSend = (event, hint) {
            // In debug, print but still send
            if (event.throwable != null) {
              print('[CrashReporting] Captured: ${event.throwable}');
            }
            return event;
          };
        }
      },
      appRunner: appRunner,
    );

    _initialized = true;
  }

  /// Set up local-only error handlers when Sentry is not configured.
  void _setupLocalErrorHandlers() {
    final originalOnError = FlutterError.onError;
    FlutterError.onError = (details) {
      FlutterError.presentError(details);
      originalOnError?.call(details);
      _logError(details.exception, details.stack);
    };

    PlatformDispatcher.instance.onError = (error, stack) {
      _logError(error, stack);
      return true;
    };
  }

  void _logError(Object error, StackTrace? stack) {
    if (kDebugMode) {
      print('[CrashReporting] Unhandled error: $error');
      if (stack != null) print(stack);
    }
  }

  // ── Public API ──

  /// Report a caught exception with optional context.
  Future<void> captureException(
    Object exception, {
    StackTrace? stackTrace,
    String? context,
    Map<String, dynamic>? extras,
  }) async {
    if (kDebugMode) {
      print('[CrashReporting] $context: $exception');
    }

    if (!isEnabled) return;

    await Sentry.captureException(
      exception,
      stackTrace: stackTrace,
      withScope: (scope) {
        if (context != null) {
          scope.setTag('context', context);
        }
        if (extras != null) {
          scope.setContexts('extras', extras);
        }
      },
    );
  }

  /// Record a breadcrumb for debugging context.
  void addBreadcrumb({
    required String message,
    String? category,
    Map<String, dynamic>? data,
    SentryLevel level = SentryLevel.info,
  }) {
    if (!isEnabled) return;

    Sentry.addBreadcrumb(Breadcrumb(
      message: message,
      category: category,
      data: data,
      level: level,
      timestamp: DateTime.now().toUtc(),
    ));
  }

  /// Set user identity for crash grouping (anonymous by default).
  void setUser({String? id, String? provider, String? model}) {
    if (!isEnabled) return;

    Sentry.configureScope((scope) {
      scope.setUser(SentryUser(
        id: id,
        data: {
          if (provider != null) 'provider': provider,
          if (model != null) 'model': model,
        },
      ));
    });
  }

  /// Clear user identity (e.g. on logout).
  void clearUser() {
    if (!isEnabled) return;
    Sentry.configureScope((scope) => scope.setUser(null));
  }

  /// Set a tag that appears on all future events.
  void setTag(String key, String value) {
    if (!isEnabled) return;
    Sentry.configureScope((scope) => scope.setTag(key, value));
  }
}
