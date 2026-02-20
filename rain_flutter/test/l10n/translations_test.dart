import 'package:flutter_test/flutter_test.dart';
import 'package:rain_flutter/app/l10n.dart';

void main() {
  // All known translation keys from the L10n class.
  // We enumerate them so tests catch if a key is removed or misspelled.
  final allKeys = [
    // Status
    'status.connecting', 'status.connected', 'status.disconnected',
    'status.ready', 'status.transcribing', 'status.rainWorking',
    'status.recordingTooShort', 'status.noSpeechDetected',
    'status.transcriptionFailed', 'status.selectProjectFirst',
    'status.connectionError',
    // PIN
    'pin.title', 'pin.instruction', 'pin.submit', 'pin.error',
    'pin.tooManyAttempts', 'pin.incorrectRemaining',
    'pin.incorrectRemainingOne',
    // API Key
    'apiKey.title', 'apiKey.instructionGeneric', 'apiKey.show',
    'apiKey.hide', 'apiKey.savedInfo', 'apiKey.clear', 'apiKey.connect',
    'apiKey.skip', 'apiKey.personalAccount', 'apiKey.personalAccountDesc',
    'apiKey.personalAccountActive', 'apiKey.orEnterKey',
    'apiKey.checkingOAuth',
    // Provider
    'provider.model',
    // File Browser
    'browser.title', 'browser.loading', 'browser.empty',
    'browser.selectBtn',
    // Chat
    'chat.inputPlaceholder', 'chat.sendBtn', 'chat.recording',
    'chat.stop', 'chat.stopping', 'chat.forceStop', 'chat.forceStopped',
    'chat.showFullOutput', 'chat.selectDirFirst', 'chat.sendError',
    'chat.emptyState',
    // Metrics
    'metrics.title', 'metrics.refresh', 'metrics.loading',
    'metrics.noData', 'metrics.totalSpent', 'metrics.sessions',
    'metrics.avgDuration', 'metrics.totalTurns', 'metrics.today',
    'metrics.week', 'metrics.month', 'metrics.avgCost',
    'metrics.inputTokens', 'metrics.outputTokens', 'metrics.rateLimits',
    'metrics.model', 'metrics.usageByHour', 'metrics.usageByDow',
    'metrics.dailySpend', 'metrics.monthlySpend', 'metrics.sessionsLabel',
    // Settings
    'settings.title', 'settings.language', 'settings.theme',
    'settings.theme.dark', 'settings.theme.light', 'settings.voiceLang',
    'settings.tts', 'settings.ttsEnabled', 'settings.ttsAutoPlay',
    'settings.ttsVoice', 'settings.ttsVoice.esFemale',
    'settings.ttsVoice.esMale', 'settings.ttsVoice.enFemale',
    'settings.ttsVoice.enMale', 'settings.provider', 'settings.model',
    'settings.logout', 'settings.logoutConfirm', 'settings.about',
    'settings.version',
    // History
    'history.title', 'history.loading', 'history.empty', 'history.count',
    'history.delete', 'history.confirmDelete', 'history.saveBtn',
    'history.saving',
    // Permissions
    'perm.requestTitle', 'perm.levelYellow', 'perm.levelRed',
    'perm.approve', 'perm.deny', 'perm.enterPin', 'perm.approved',
    'perm.denied', 'perm.expired',
    // Computer Use
    'cu.title', 'cu.modeCoding', 'cu.modeComputer', 'cu.switchToCoding',
    'cu.switchToComputerUse', 'cu.emergencyStop', 'cu.iteration',
    'cu.liveDisplay', 'cu.resolution', 'cu.iterationProgress',
    'cu.noScreenshot', 'cu.tapToExpand',
    // Model Switcher
    'modelSwitcher.keyConfigured', 'modelSwitcher.noKey',
    'modelSwitcher.appliesNext',
    // Notifications
    'settings.notifications', 'settings.notifPermission',
    'settings.notifPermissionDesc', 'settings.notifResult',
    'settings.notifError', 'settings.notifHaptic', 'settings.notifDialog',
    'settings.notifDialogDesc',
    // Toast
    'toast.connectionLost', 'toast.connectionRestored',
    'toast.copySuccess', 'toast.saveSuccess', 'toast.saveFailed',
    'toast.clearSuccess', 'toast.sendFailed', 'toast.deletedConversation',
    // Agent
    'agent.new', 'agent.delete', 'agent.deleteConfirm', 'agent.cancel',
    'agent.create', 'agent.nameHint', 'agent.selectDir', 'agent.useThis',
    // Months
    'month.0', 'month.1', 'month.2', 'month.3', 'month.4', 'month.5',
    'month.6', 'month.7', 'month.8', 'month.9', 'month.10', 'month.11',
    // Days of week
    'dow.Monday', 'dow.Tuesday', 'dow.Wednesday', 'dow.Thursday',
    'dow.Friday', 'dow.Saturday', 'dow.Sunday',
  ];

  group('L10n.supported', () {
    test('contains en and es', () {
      expect(L10n.supported, contains('en'));
      expect(L10n.supported, contains('es'));
    });

    test('has exactly 2 supported languages', () {
      expect(L10n.supported.length, 2);
    });
  });

  group('L10n.t() — English translations', () {
    test('all known keys have English translations', () {
      for (final key in allKeys) {
        final value = L10n.t(key, 'en');
        expect(value, isNot(key),
            reason: 'English translation missing for key: $key');
        expect(value, isNotEmpty,
            reason: 'English translation is empty for key: $key');
      }
    });

    test('returns specific known English strings', () {
      expect(L10n.t('status.connected', 'en'), 'Connected');
      expect(L10n.t('status.disconnected', 'en'), 'Disconnected');
      expect(L10n.t('chat.sendBtn', 'en'), 'Send');
      expect(L10n.t('settings.title', 'en'), 'Settings');
      expect(L10n.t('perm.approve', 'en'), 'Approve');
      expect(L10n.t('perm.deny', 'en'), 'Deny');
    });
  });

  group('L10n.t() — Spanish translations', () {
    test('all known keys have Spanish translations', () {
      for (final key in allKeys) {
        final value = L10n.t(key, 'es');
        expect(value, isNot(key),
            reason: 'Spanish translation missing for key: $key');
        expect(value, isNotEmpty,
            reason: 'Spanish translation is empty for key: $key');
      }
    });

    test('returns specific known Spanish strings', () {
      expect(L10n.t('status.connected', 'es'), 'Conectado');
      expect(L10n.t('status.disconnected', 'es'), 'Desconectado');
      expect(L10n.t('chat.sendBtn', 'es'), 'Enviar');
      expect(L10n.t('settings.title', 'es'), 'Configuraci\u00f3n');
      expect(L10n.t('perm.approve', 'es'), 'Aprobar');
      expect(L10n.t('perm.deny', 'es'), 'Denegar');
    });

    test('Spanish and English values differ for localized keys', () {
      // These are known to be different in each language
      final localizedKeys = [
        'status.connected',
        'status.disconnected',
        'chat.sendBtn',
        'settings.title',
        'perm.approve',
        'history.title',
        'metrics.title',
      ];
      for (final key in localizedKeys) {
        final en = L10n.t(key, 'en');
        final es = L10n.t(key, 'es');
        expect(en, isNot(es),
            reason: 'Key $key should have different en/es values');
      }
    });
  });

  group('L10n.t() — fallback behavior', () {
    test('missing key returns the key itself', () {
      expect(L10n.t('nonexistent.key', 'en'), 'nonexistent.key');
      expect(L10n.t('nonexistent.key', 'es'), 'nonexistent.key');
    });

    test('unsupported language falls back to English', () {
      // Any lang that is not 'es' uses the _en map
      final result = L10n.t('status.connected', 'fr');
      expect(result, 'Connected');
    });

    test('empty key returns empty string (the key itself)', () {
      expect(L10n.t('', 'en'), '');
    });
  });

  group('L10n.t() — parameterized strings', () {
    test('{time} parameter substitution in pin.tooManyAttempts', () {
      final result = L10n.t(
        'pin.tooManyAttempts',
        'en',
        {'time': '5 minutes'},
      );
      expect(result, 'Too many attempts. Try again in 5 minutes');
      expect(result, isNot(contains('{time}')));
    });

    test('{n} parameter substitution in pin.incorrectRemaining', () {
      final result = L10n.t(
        'pin.incorrectRemaining',
        'en',
        {'n': '3'},
      );
      expect(result, contains('3'));
      expect(result, isNot(contains('{n}')));
    });

    test('{n} and {max} substitution in history.count', () {
      final result = L10n.t(
        'history.count',
        'en',
        {'n': '5', 'max': '50'},
      );
      expect(result, '5 of 50 conversations');
      expect(result, isNot(contains('{n}')));
      expect(result, isNot(contains('{max}')));
    });

    test('{provider} substitution in apiKey.instructionGeneric', () {
      final result = L10n.t(
        'apiKey.instructionGeneric',
        'en',
        {'provider': 'Claude'},
      );
      expect(result, contains('Claude'));
      expect(result, isNot(contains('{provider}')));
    });

    test('{current} substitution in cu.iterationProgress', () {
      final result = L10n.t(
        'cu.iterationProgress',
        'en',
        {'current': '7'},
      );
      expect(result, 'Step 7');
    });

    test('{name} substitution in agent.deleteConfirm', () {
      final result = L10n.t(
        'agent.deleteConfirm',
        'en',
        {'name': 'My Agent'},
      );
      expect(result, contains('My Agent'));
      expect(result, isNot(contains('{name}')));
    });

    test('parameterized strings work in Spanish too', () {
      final result = L10n.t(
        'pin.tooManyAttempts',
        'es',
        {'time': '5 minutos'},
      );
      expect(result, contains('5 minutos'));
      expect(result, isNot(contains('{time}')));
    });

    test('params with no matching placeholders leave string unchanged', () {
      final result = L10n.t(
        'status.connected',
        'en',
        {'unused': 'value'},
      );
      expect(result, 'Connected');
    });

    test('null params argument works (no substitution)', () {
      final result = L10n.t('status.connected', 'en', null);
      expect(result, 'Connected');
    });

    test('empty params map works (no substitution)', () {
      final result = L10n.t('status.connected', 'en', {});
      expect(result, 'Connected');
    });

    test('multiple occurrences of same param are all replaced', () {
      // If a key had duplicate placeholders, all should be replaced.
      // We test with history.count which has {n} and {max}
      final result = L10n.t(
        'history.count',
        'es',
        {'n': '10', 'max': '100'},
      );
      expect(result, '10 de 100 conversaciones');
    });
  });

  group('L10n — month translations', () {
    test('all 12 months have English translations', () {
      for (int i = 0; i < 12; i++) {
        final value = L10n.t('month.$i', 'en');
        expect(value, isNotEmpty, reason: 'Month $i EN is empty');
      }
    });

    test('all 12 months have Spanish translations', () {
      for (int i = 0; i < 12; i++) {
        final value = L10n.t('month.$i', 'es');
        expect(value, isNotEmpty, reason: 'Month $i ES is empty');
      }
    });

    test('English month abbreviations are correct', () {
      expect(L10n.t('month.0', 'en'), 'Jan');
      expect(L10n.t('month.5', 'en'), 'Jun');
      expect(L10n.t('month.11', 'en'), 'Dec');
    });

    test('Spanish month abbreviations are correct', () {
      expect(L10n.t('month.0', 'es'), 'Ene');
      expect(L10n.t('month.5', 'es'), 'Jun');
      expect(L10n.t('month.11', 'es'), 'Dic');
    });
  });

  group('L10n — day of week translations', () {
    final days = [
      'Monday', 'Tuesday', 'Wednesday', 'Thursday',
      'Friday', 'Saturday', 'Sunday',
    ];

    test('all 7 days have English translations', () {
      for (final day in days) {
        final value = L10n.t('dow.$day', 'en');
        expect(value, isNotEmpty, reason: 'DOW $day EN is empty');
        expect(value, isNot('dow.$day'), reason: 'DOW $day EN is missing');
      }
    });

    test('all 7 days have Spanish translations', () {
      for (final day in days) {
        final value = L10n.t('dow.$day', 'es');
        expect(value, isNotEmpty, reason: 'DOW $day ES is empty');
        expect(value, isNot('dow.$day'), reason: 'DOW $day ES is missing');
      }
    });

    test('English day abbreviations are correct', () {
      expect(L10n.t('dow.Monday', 'en'), 'Mon');
      expect(L10n.t('dow.Friday', 'en'), 'Fri');
      expect(L10n.t('dow.Sunday', 'en'), 'Sun');
    });

    test('Spanish day abbreviations are correct', () {
      expect(L10n.t('dow.Monday', 'es'), 'Lun');
      expect(L10n.t('dow.Friday', 'es'), 'Vie');
      expect(L10n.t('dow.Sunday', 'es'), 'Dom');
    });
  });
}
