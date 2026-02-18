import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/provider_info.dart';
import '../providers/connection_provider.dart';
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
