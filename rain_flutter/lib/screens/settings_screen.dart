import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/provider_info.dart';
import '../providers/connection_provider.dart';
import '../providers/notification_provider.dart';
import '../providers/settings_provider.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final settings = ref.watch(settingsProvider);
    final notifier = ref.read(settingsProvider.notifier);
    final lang = settings.language;

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('settings.title', lang)),
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          // ── Theme ──
          _SectionHeader(L10n.t('settings.theme', lang)),
          SwitchListTile(
            title: Text(L10n.t('settings.theme', lang)),
            subtitle: Text(settings.darkMode
                ? L10n.t('settings.theme.dark', lang)
                : L10n.t('settings.theme.light', lang)),
            secondary: Icon(
              settings.darkMode ? Icons.dark_mode : Icons.light_mode,
              color: cs.primary,
            ),
            value: settings.darkMode,
            onChanged: notifier.setDarkMode,
          ),

          const Divider(),

          // ── Language ──
          _SectionHeader(L10n.t('settings.language', lang)),
          _LanguageSelector(
            language: settings.language,
            onChanged: notifier.setLanguage,
          ),

          const Divider(),

          // ── AI Provider & Model ──
          _SectionHeader(L10n.t('settings.provider', lang)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: SegmentedButton<AIProvider>(
              segments: AIProvider.values
                  .map((p) => ButtonSegment(
                        value: p,
                        label: Text(providerInfo[p]!.name),
                      ))
                  .toList(),
              selected: {settings.aiProvider},
              onSelectionChanged: (s) {
                notifier.setAIProvider(s.first);
              },
            ),
          ),
          _ModelDropdown(
            label: L10n.t('settings.model', lang),
            currentModel: settings.aiModel,
            provider: settings.aiProvider,
            onChanged: notifier.setAIModel,
          ),

          const Divider(),

          // ── TTS ──
          _SectionHeader(L10n.t('settings.tts', lang)),
          SwitchListTile(
            title: Text(L10n.t('settings.ttsEnabled', lang)),
            secondary: Icon(Icons.volume_up, color: cs.primary),
            value: settings.ttsEnabled,
            onChanged: notifier.setTtsEnabled,
          ),
          SwitchListTile(
            title: Text(L10n.t('settings.ttsAutoPlay', lang)),
            secondary: const Icon(Icons.play_circle_outline),
            value: settings.ttsAutoPlay,
            onChanged: settings.ttsEnabled ? notifier.setTtsAutoPlay : null,
          ),
          _VoiceDropdown(
            lang: lang,
            currentVoice: settings.ttsVoice,
            enabled: settings.ttsEnabled,
            onChanged: notifier.setTtsVoice,
          ),

          const Divider(),

          // ── Voice Mode ──
          _SectionHeader(L10n.t('settings.voiceMode', lang)),
          _VoiceModeSelector(
            voiceMode: settings.voiceMode,
            lang: lang,
            onChanged: notifier.setVoiceMode,
          ),
          if (settings.voiceMode != 'push-to-talk') ...[
            _SliderTile(
              title: L10n.t('settings.vadSensitivity', lang),
              value: settings.vadSensitivity,
              min: 0.3,
              max: 0.9,
              divisions: 12,
              labelSuffix: '',
              onChanged: notifier.setVadSensitivity,
            ),
            _SliderTile(
              title: L10n.t('settings.silenceTimeout', lang),
              value: settings.silenceTimeout.toDouble(),
              min: 400,
              max: 2000,
              divisions: 8,
              labelSuffix: 'ms',
              onChanged: (v) => notifier.setSilenceTimeout(v.round()),
            ),
          ],

          const Divider(),

          // ── Notifications ──
          _NotificationSection(lang: lang),

          const Divider(),

          // ── Logout ──
          ListTile(
            leading: Icon(Icons.logout, color: cs.error),
            title: Text(L10n.t('settings.logout', lang),
                style: TextStyle(color: cs.error)),
            onTap: () => _confirmLogout(context, ref, lang),
          ),

          const SizedBox(height: 32),

          // ── About ──
          Center(
            child: Text(
              'Rain Assistant v1.0.0',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  void _confirmLogout(BuildContext context, WidgetRef ref, String lang) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(L10n.t('settings.logout', lang)),
        content: Text(L10n.t('settings.logoutConfirm', lang)),
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
              final auth = ref.read(authServiceProvider);
              auth.logout();
              ref.read(webSocketServiceProvider).disconnect();
              ref.read(isAuthenticatedProvider.notifier).state = false;
              Navigator.of(context).popUntil((route) => route.isFirst);
            },
            child: Text(L10n.t('settings.logout', lang)),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.primary,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

/// Language selector using ListTiles instead of deprecated RadioListTile.
class _LanguageSelector extends StatelessWidget {
  final String language;
  final ValueChanged<String> onChanged;

  const _LanguageSelector({required this.language, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Column(
      children: [
        ListTile(
          leading: Icon(
            language == 'es' ? Icons.radio_button_checked : Icons.radio_button_unchecked,
            color: language == 'es' ? cs.primary : cs.onSurfaceVariant,
          ),
          title: const Text('Español'),
          onTap: () => onChanged('es'),
        ),
        ListTile(
          leading: Icon(
            language == 'en' ? Icons.radio_button_checked : Icons.radio_button_unchecked,
            color: language == 'en' ? cs.primary : cs.onSurfaceVariant,
          ),
          title: const Text('English'),
          onTap: () => onChanged('en'),
        ),
      ],
    );
  }
}

/// Model dropdown that rebuilds correctly when provider changes.
class _ModelDropdown extends StatelessWidget {
  final String label;
  final String currentModel;
  final AIProvider provider;
  final ValueChanged<String> onChanged;

  const _ModelDropdown({
    required this.label,
    required this.currentModel,
    required this.provider,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final models = providerModels[provider] ?? [];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: DropdownMenu<String>(
        initialSelection: currentModel,
        label: Text(label),
        leadingIcon: const Icon(Icons.smart_toy_outlined),
        expandedInsets: EdgeInsets.zero,
        onSelected: (v) {
          if (v != null) onChanged(v);
        },
        dropdownMenuEntries: models
            .map((m) => DropdownMenuEntry(value: m.id, label: m.name))
            .toList(),
      ),
    );
  }
}

/// Voice dropdown.
class _VoiceDropdown extends StatelessWidget {
  final String lang;
  final String currentVoice;
  final bool enabled;
  final ValueChanged<String> onChanged;

  const _VoiceDropdown({
    required this.lang,
    required this.currentVoice,
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: DropdownMenu<String>(
        initialSelection: currentVoice,
        label: Text(L10n.t('settings.ttsVoice', lang)),
        leadingIcon: const Icon(Icons.record_voice_over),
        expandedInsets: EdgeInsets.zero,
        enabled: enabled,
        onSelected: (v) {
          if (v != null) onChanged(v);
        },
        dropdownMenuEntries: [
          DropdownMenuEntry(
            value: 'es-MX-DaliaNeural',
            label: L10n.t('settings.ttsVoice.esFemale', lang),
          ),
          DropdownMenuEntry(
            value: 'es-MX-JorgeNeural',
            label: L10n.t('settings.ttsVoice.esMale', lang),
          ),
          DropdownMenuEntry(
            value: 'en-US-JennyNeural',
            label: L10n.t('settings.ttsVoice.enFemale', lang),
          ),
          DropdownMenuEntry(
            value: 'en-US-GuyNeural',
            label: L10n.t('settings.ttsVoice.enMale', lang),
          ),
        ],
      ),
    );
  }
}

/// Notification settings section with 5 toggles.
class _NotificationSection extends ConsumerWidget {
  final String lang;
  const _NotificationSection({required this.lang});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final notifSettings = ref.watch(notificationSettingsProvider);
    final notifNotifier = ref.read(notificationSettingsProvider.notifier);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(L10n.t('settings.notifications', lang)),
        SwitchListTile(
          title: Text(L10n.t('settings.notifPermission', lang)),
          subtitle: Text(L10n.t('settings.notifPermissionDesc', lang)),
          secondary: Icon(Icons.shield_outlined, color: cs.primary),
          value: notifSettings.permissionNotifications,
          onChanged: notifNotifier.setPermissionNotifications,
        ),
        SwitchListTile(
          title: Text(L10n.t('settings.notifResult', lang)),
          secondary: const Icon(Icons.check_circle_outline),
          value: notifSettings.resultNotifications,
          onChanged: notifNotifier.setResultNotifications,
        ),
        SwitchListTile(
          title: Text(L10n.t('settings.notifError', lang)),
          secondary: Icon(Icons.error_outline, color: cs.error),
          value: notifSettings.errorNotifications,
          onChanged: notifNotifier.setErrorNotifications,
        ),
        SwitchListTile(
          title: Text(L10n.t('settings.notifHaptic', lang)),
          secondary: const Icon(Icons.vibration),
          value: notifSettings.hapticFeedback,
          onChanged: notifNotifier.setHapticFeedback,
        ),
        SwitchListTile(
          title: Text(L10n.t('settings.notifDialog', lang)),
          subtitle: Text(L10n.t('settings.notifDialogDesc', lang)),
          secondary: const Icon(Icons.picture_in_picture),
          value: notifSettings.inAppDialogs,
          onChanged: notifNotifier.setInAppDialogs,
        ),
      ],
    );
  }
}

/// Voice mode selector using ListTiles.
class _VoiceModeSelector extends StatelessWidget {
  final String voiceMode;
  final String lang;
  final ValueChanged<String> onChanged;

  const _VoiceModeSelector({
    required this.voiceMode,
    required this.lang,
    required this.onChanged,
  });

  static const _modes = [
    ('push-to-talk', Icons.touch_app, 'settings.voiceMode.pushToTalk'),
    ('vad', Icons.graphic_eq, 'settings.voiceMode.vad'),
    ('talk-mode', Icons.phone_in_talk, 'settings.voiceMode.talkMode'),
    ('wake-word', Icons.hearing, 'settings.voiceMode.wakeWord'),
  ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Column(
      children: _modes.map((m) {
        final (value, icon, l10nKey) = m;
        final selected = voiceMode == value;
        return ListTile(
          leading: Icon(
            selected ? Icons.radio_button_checked : Icons.radio_button_unchecked,
            color: selected ? cs.primary : cs.onSurfaceVariant,
          ),
          title: Row(
            children: [
              Icon(icon, size: 18, color: selected ? cs.primary : cs.onSurfaceVariant),
              const SizedBox(width: 8),
              Text(L10n.t(l10nKey, lang)),
            ],
          ),
          onTap: () => onChanged(value),
        );
      }).toList(),
    );
  }
}

/// Reusable slider tile for numeric settings.
class _SliderTile extends StatelessWidget {
  final String title;
  final double value;
  final double min;
  final double max;
  final int divisions;
  final String labelSuffix;
  final ValueChanged<double> onChanged;

  const _SliderTile({
    required this.title,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.labelSuffix,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final displayValue = labelSuffix == 'ms'
        ? '${value.round()}$labelSuffix'
        : value.toStringAsFixed(2);
    return ListTile(
      title: Text(title),
      subtitle: Slider(
        value: value.clamp(min, max),
        min: min,
        max: max,
        divisions: divisions,
        label: displayValue,
        onChanged: onChanged,
      ),
      trailing: Text(
        displayValue,
        style: TextStyle(
          fontSize: 13,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}
