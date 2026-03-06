import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/directors_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/context_field_builder.dart';
import '../widgets/toast.dart';

/// Full-screen wizard that collects context fields for ALL directors in a team
/// after a project is created from a team template.
///
/// Features:
/// - Smart deduplication: fields with the same key across directors appear once
/// - Per-director sections with emoji + name headers
/// - Progress indicator showing overall completion
/// - Bulk save to all directors via POST /projects/{id}/setup
class TeamSetupWizardScreen extends ConsumerStatefulWidget {
  final String projectId;
  final String projectName;
  final String projectEmoji;
  final List<Director> directors;

  const TeamSetupWizardScreen({
    super.key,
    required this.projectId,
    required this.projectName,
    required this.projectEmoji,
    required this.directors,
  });

  @override
  ConsumerState<TeamSetupWizardScreen> createState() =>
      _TeamSetupWizardScreenState();
}

class _TeamSetupWizardScreenState
    extends ConsumerState<TeamSetupWizardScreen> {
  final _formKey = GlobalKey<FormState>();
  bool _saving = false;

  // Controllers for director-specific fields: "directorId::fieldKey" -> controller
  final Map<String, TextEditingController> _controllers = {};

  // Controllers for shared fields (same key in 2+ directors): "fieldKey" -> controller
  final Map<String, TextEditingController> _sharedControllers = {};

  // Deduplication data
  late Set<String> _sharedFieldKeys;
  late Map<String, ContextFieldMeta> _sharedFieldMetas;
  // Which directors use each shared key
  late Map<String, List<Director>> _sharedFieldDirectors;

  // Directors that actually have user-editable fields
  late List<Director> _directorsWithFields;

  @override
  void initState() {
    super.initState();
    _computeSharedFields();
    _initControllers();
  }

  void _computeSharedFields() {
    // Count how many directors use each field key (user-editable only)
    final keyUsage = <String, List<Director>>{};
    for (final director in widget.directors) {
      for (final field in director.requiredContext) {
        if (field.readOnly || field.autoManaged) continue;
        keyUsage.putIfAbsent(field.key, () => []).add(director);
      }
    }

    // Fields used by 2+ directors are "shared"
    _sharedFieldKeys = keyUsage.entries
        .where((e) => e.value.length > 1)
        .map((e) => e.key)
        .toSet();

    _sharedFieldDirectors = {};
    for (final key in _sharedFieldKeys) {
      _sharedFieldDirectors[key] = keyUsage[key]!;
    }

    // For shared fields, use the metadata from the first director that defines it
    _sharedFieldMetas = {};
    for (final key in _sharedFieldKeys) {
      for (final director in widget.directors) {
        final field =
            director.requiredContext.where((f) => f.key == key).firstOrNull;
        if (field != null) {
          _sharedFieldMetas[key] = field;
          break;
        }
      }
    }

    // Filter directors that have at least one non-shared user-editable field
    _directorsWithFields = widget.directors.where((d) {
      return d.requiredContext.any((f) =>
          !f.readOnly &&
          !f.autoManaged &&
          !_sharedFieldKeys.contains(f.key));
    }).toList();
  }

  void _initControllers() {
    // Shared controllers
    for (final entry in _sharedFieldMetas.entries) {
      final key = entry.key;
      final field = entry.value;

      // Try to find an existing value from any director
      String initialValue = field.defaultValue;
      for (final director in widget.directors) {
        final raw = director.contextWindow[key];
        if (raw != null && (raw is! String || raw.isNotEmpty)) {
          if (field.type == 'tags' && raw is List) {
            initialValue = raw.map((e) => e.toString()).join(', ');
          } else if (raw is Map || raw is List) {
            initialValue = jsonEncode(raw);
          } else {
            initialValue = raw.toString();
          }
          break;
        }
      }
      _sharedControllers[key] = TextEditingController(text: initialValue);
    }

    // Per-director controllers (only for non-shared, non-readonly fields)
    for (final director in widget.directors) {
      final ctx = director.contextWindow;
      for (final field in director.requiredContext) {
        if (field.readOnly || field.autoManaged) continue;
        if (_sharedFieldKeys.contains(field.key)) continue;

        final raw = ctx[field.key];
        String initialValue;

        if (raw == null || (raw is String && raw.isEmpty)) {
          initialValue = field.defaultValue;
        } else if (field.type == 'tags' && raw is List) {
          initialValue = raw.map((e) => e.toString()).join(', ');
        } else if (raw is Map || raw is List) {
          initialValue = jsonEncode(raw);
        } else {
          initialValue = raw.toString();
        }

        _controllers['${director.id}::${field.key}'] =
            TextEditingController(text: initialValue);
      }
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    for (final c in _sharedControllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  /// Count total user-editable fields and how many are filled.
  (int filled, int total) _countProgress() {
    int total = 0;
    int filled = 0;

    // Shared fields
    for (final key in _sharedFieldKeys) {
      final field = _sharedFieldMetas[key]!;
      if (!field.required) continue;
      total++;
      final controller = _sharedControllers[key];
      if (controller != null && controller.text.trim().isNotEmpty) filled++;
    }

    // Per-director fields
    for (final director in widget.directors) {
      for (final field in director.requiredContext) {
        if (field.readOnly || field.autoManaged) continue;
        if (_sharedFieldKeys.contains(field.key)) continue;
        if (!field.required) continue;
        total++;
        final controller = _controllers['${director.id}::${field.key}'];
        if (controller != null && controller.text.trim().isNotEmpty) filled++;
      }
    }

    return (filled, total);
  }

  String _serializeFieldValue(ContextFieldMeta field, String text) {
    if (field.type == 'tags') {
      final tags = text
          .split(RegExp(r'[,\n]'))
          .map((t) => t.trim())
          .where((t) => t.isNotEmpty)
          .toList();
      return jsonEncode(tags);
    } else if (field.type == 'multiselect') {
      // Already stored as JSON array by the widget
      return text;
    }
    return text;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _saving = true);

    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;

    // Build context_updates: { directorId: { key: value, ... }, ... }
    final contextUpdates = <String, Map<String, dynamic>>{};

    for (final director in widget.directors) {
      final dirContext = <String, dynamic>{};

      for (final field in director.requiredContext) {
        if (field.readOnly || field.autoManaged) continue;

        // Use shared controller if shared, else director-specific
        final TextEditingController? controller;
        if (_sharedFieldKeys.contains(field.key)) {
          controller = _sharedControllers[field.key];
        } else {
          controller = _controllers['${director.id}::${field.key}'];
        }

        if (controller == null) continue;
        final text = controller.text.trim();
        if (text.isEmpty) continue;

        dirContext[field.key] = _serializeFieldValue(field, text);
      }

      if (dirContext.isNotEmpty) {
        contextUpdates[director.id] = dirContext;
      }
    }

    if (contextUpdates.isEmpty) {
      if (mounted) {
        Navigator.of(context).pop();
      }
      return;
    }

    final ok = await ref
        .read(directorsProvider.notifier)
        .bulkUpdateContext(dio, widget.projectId, contextUpdates);

    if (!mounted) return;
    setState(() => _saving = false);

    if (ok) {
      showToast(context, L10n.t('wizard.saved', lang),
          type: ToastType.success);
      Navigator.of(context).pop();
    } else {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  void _skip() {
    final lang = ref.read(settingsProvider).language;
    showToast(context, L10n.t('wizard.skipConfirm', lang),
        type: ToastType.info);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
    final (filled, total) = _countProgress();

    // Get only the shared fields that are required
    final sharedRequiredFields = _sharedFieldMetas.entries
        .where((e) => e.value.required)
        .toList();
    final sharedOptionalFields = _sharedFieldMetas.entries
        .where((e) => !e.value.required)
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Text(widget.projectEmoji,
                style: const TextStyle(fontSize: 22)),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    L10n.t('wizard.title', lang),
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w600),
                  ),
                  Text(
                    widget.projectName,
                    style: TextStyle(
                      fontSize: 12,
                      color: cs.onSurfaceVariant,
                      fontWeight: FontWeight.normal,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: _skip,
            child: Text(L10n.t('wizard.skip', lang)),
          ),
        ],
      ),
      body: Column(
        children: [
          // Progress card
          if (total > 0)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: filled == total
                      ? Colors.green.withValues(alpha: 0.08)
                      : cs.primary.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: filled == total
                        ? Colors.green.withValues(alpha: 0.3)
                        : cs.primary.withValues(alpha: 0.2),
                  ),
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Icon(
                          filled == total
                              ? Icons.check_circle
                              : Icons.checklist_rounded,
                          color: filled == total
                              ? Colors.green
                              : cs.primary,
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          L10n.t('wizard.progress', lang, {
                            'done': '$filled',
                            'total': '$total',
                          }),
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                            color: filled == total
                                ? Colors.green
                                : cs.primary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: total > 0 ? filled / total : 0,
                        backgroundColor: cs.surfaceContainerHighest,
                        color: filled == total
                            ? Colors.green
                            : cs.primary,
                        minHeight: 6,
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // Form
          Expanded(
            child: Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
                children: [
                  // ── Shared fields section ──
                  if (_sharedFieldMetas.isNotEmpty) ...[
                    _WizardSectionHeader(
                      icon: Icons.share,
                      title: L10n.t('wizard.sharedFields', lang),
                      subtitle:
                          L10n.t('wizard.sharedFieldsHint', lang),
                      cs: cs,
                    ),
                    // Required shared fields
                    for (final entry in sharedRequiredFields) ...[
                      _SharedFieldWrapper(
                        field: entry.value,
                        directorNames: _sharedFieldDirectors[entry.key]
                                ?.map((d) => '${d.emoji} ${d.name}')
                                .toList() ??
                            [],
                        cs: cs,
                        child: buildContextField(
                          entry.value,
                          _sharedControllers[entry.key]!,
                          lang,
                          cs,
                          setStateCallback: setState,
                          dio: ref.read(authServiceProvider).authenticatedDio,
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],
                    // Optional shared fields
                    for (final entry in sharedOptionalFields) ...[
                      _SharedFieldWrapper(
                        field: entry.value,
                        directorNames: _sharedFieldDirectors[entry.key]
                                ?.map((d) => '${d.emoji} ${d.name}')
                                .toList() ??
                            [],
                        cs: cs,
                        child: buildContextField(
                          entry.value,
                          _sharedControllers[entry.key]!,
                          lang,
                          cs,
                          setStateCallback: setState,
                          dio: ref.read(authServiceProvider).authenticatedDio,
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],
                    const SizedBox(height: 8),
                  ],

                  // ── Per-director sections ──
                  for (final director in _directorsWithFields) ...[
                    _DirectorSectionHeader(
                      emoji: director.emoji,
                      name: director.name,
                      description: director.description,
                      fieldCount: director.requiredContext
                          .where((f) =>
                              !f.readOnly &&
                              !f.autoManaged &&
                              !_sharedFieldKeys.contains(f.key))
                          .length,
                      lang: lang,
                      cs: cs,
                    ),
                    for (final field in director.requiredContext.where((f) =>
                        !f.readOnly &&
                        !f.autoManaged &&
                        !_sharedFieldKeys.contains(f.key))) ...[
                      buildContextField(
                        field,
                        _controllers['${director.id}::${field.key}']!,
                        lang,
                        cs,
                        setStateCallback: setState,
                        dio: ref.read(authServiceProvider).authenticatedDio,
                      ),
                      const SizedBox(height: 16),
                    ],
                    const SizedBox(height: 8),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),

      // Save button
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: FilledButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.check_circle_outline),
            label: Text(L10n.t('wizard.save', lang)),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(52),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Wizard section header (for "Shared Fields" section)
// ---------------------------------------------------------------------------

class _WizardSectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final ColorScheme cs;

  const _WizardSectionHeader({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.cs,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: cs.primary),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: cs.primary,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child:
                    Divider(color: cs.outlineVariant.withValues(alpha: 0.3)),
              ),
            ],
          ),
          if (subtitle.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4, left: 26),
              child: Text(
                subtitle,
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
              ),
            ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Shared field wrapper — shows which directors use this field
// ---------------------------------------------------------------------------

class _SharedFieldWrapper extends StatelessWidget {
  final ContextFieldMeta field;
  final List<String> directorNames;
  final ColorScheme cs;
  final Widget child;

  const _SharedFieldWrapper({
    required this.field,
    required this.directorNames,
    required this.cs,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        child,
        if (directorNames.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 4),
            child: Wrap(
              spacing: 6,
              runSpacing: 4,
              children: [
                Icon(Icons.share, size: 11, color: cs.onSurfaceVariant.withValues(alpha: 0.5)),
                ...directorNames.map(
                  (name) => Text(
                    name,
                    style: TextStyle(
                      fontSize: 11,
                      color: cs.onSurfaceVariant.withValues(alpha: 0.6),
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Director section header in wizard
// ---------------------------------------------------------------------------

class _DirectorSectionHeader extends StatelessWidget {
  final String emoji;
  final String name;
  final String description;
  final int fieldCount;
  final String lang;
  final ColorScheme cs;

  const _DirectorSectionHeader({
    required this.emoji,
    required this.name,
    required this.description,
    required this.fieldCount,
    required this.lang,
    required this.cs,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: cs.outlineVariant.withValues(alpha: 0.2),
          ),
        ),
        child: Row(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 28)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: cs.onSurface,
                    ),
                  ),
                  if (description.isNotEmpty)
                    Text(
                      description,
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurfaceVariant),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: cs.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '$fieldCount',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: cs.primary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
