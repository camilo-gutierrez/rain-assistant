import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/provider_info.dart';
import '../providers/metrics_provider.dart';
import '../providers/settings_provider.dart';

/// Compact model/provider info chip shown in the AppBar or status area.
class ModelSwitcher extends ConsumerWidget {
  const ModelSwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final settings = ref.watch(settingsProvider);
    final currentModel = ref.watch(currentModelProvider);
    final lang = settings.language;

    final displayModel = currentModel.isNotEmpty
        ? formatModelName(currentModel)
        : settings.aiModel;

    return GestureDetector(
      onTap: () => _showModelSheet(context, ref, lang),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: cs.primaryContainer.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.smart_toy_outlined, size: 14, color: cs.primary),
            const SizedBox(width: 4),
            Text(
              displayModel,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: cs.onPrimaryContainer,
              ),
            ),
            Icon(Icons.arrow_drop_down, size: 16, color: cs.onPrimaryContainer),
          ],
        ),
      ),
    );
  }

  void _showModelSheet(BuildContext context, WidgetRef ref, String lang) {
    final settings = ref.read(settingsProvider);
    final notifier = ref.read(settingsProvider.notifier);

    showModalBottomSheet(
      context: context,
      builder: (ctx) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text(
                  L10n.t('settings.provider', lang),
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 16),
                ),
              ),
              // Provider selector
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
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
                    Navigator.of(ctx).pop();
                    // Re-open to reflect new models
                    _showModelSheet(context, ref, lang);
                  },
                ),
              ),
              const SizedBox(height: 12),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  L10n.t('provider.model', lang),
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 14),
                ),
              ),
              const SizedBox(height: 4),
              ...(providerModels[settings.aiProvider] ?? []).map((m) {
                final isSelected = m.id == settings.aiModel;
                return ListTile(
                  dense: true,
                  leading: Icon(
                    isSelected
                        ? Icons.radio_button_checked
                        : Icons.radio_button_unchecked,
                    color: isSelected
                        ? Theme.of(context).colorScheme.primary
                        : null,
                    size: 20,
                  ),
                  title: Text(m.name),
                  onTap: () {
                    notifier.setAIModel(m.id);
                    Navigator.of(ctx).pop();
                  },
                );
              }),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                child: Text(
                  L10n.t('modelSwitcher.appliesNext', lang),
                  style: TextStyle(
                    fontSize: 11,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
