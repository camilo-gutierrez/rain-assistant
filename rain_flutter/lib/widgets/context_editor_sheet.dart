import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/l10n.dart';
import '../models/director.dart';
import '../providers/connection_provider.dart';
import '../providers/directors_provider.dart';
import '../providers/settings_provider.dart';
import 'toast.dart';

/// Shows a full-height bottom sheet to configure a director's context fields.
///
/// If the director was created from a template that defines [requiredContext],
/// the sheet renders a dynamic form with the right input type for each field.
/// Otherwise, it shows a raw JSON editor for free-form context.
void showContextEditorSheet(BuildContext context, Director director) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (_) => _ContextEditorSheet(director: director),
  );
}

class _ContextEditorSheet extends ConsumerStatefulWidget {
  final Director director;

  const _ContextEditorSheet({required this.director});

  @override
  ConsumerState<_ContextEditorSheet> createState() =>
      _ContextEditorSheetState();
}

class _ContextEditorSheetState extends ConsumerState<_ContextEditorSheet> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _controllers = {};
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _initControllers();
  }

  void _initControllers() {
    final ctx = widget.director.contextWindow;

    for (final field in widget.director.requiredContext) {
      final raw = ctx[field.key];
      String initialValue;

      if (raw == null || (raw is String && raw.isEmpty)) {
        initialValue = field.defaultValue;
      } else if (field.type == 'tags' && raw is List) {
        // Tags are stored as JSON arrays — show as comma-separated
        initialValue = raw.map((e) => e.toString()).join(', ');
      } else if (raw is Map || raw is List) {
        initialValue = jsonEncode(raw);
      } else {
        initialValue = raw.toString();
      }

      _controllers[field.key] = TextEditingController(text: initialValue);
    }

    // Also handle any extra context keys not in required_context
    final knownKeys =
        widget.director.requiredContext.map((f) => f.key).toSet();
    for (final entry in ctx.entries) {
      if (!knownKeys.contains(entry.key)) {
        final val = entry.value is String
            ? entry.value as String
            : jsonEncode(entry.value);
        _controllers[entry.key] = TextEditingController(text: val);
      }
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _saving = true);

    final lang = ref.read(settingsProvider).language;
    final dio = ref.read(authServiceProvider).authenticatedDio;

    // Build the new context_window
    final newContext = <String, dynamic>{};

    // First: structured fields
    for (final field in widget.director.requiredContext) {
      // Preserve original value for read-only fields
      if (field.readOnly) {
        final original = widget.director.contextWindow[field.key];
        if (original != null) {
          newContext[field.key] =
              original is String ? original : jsonEncode(original);
        }
        continue;
      }

      final controller = _controllers[field.key];
      if (controller == null) continue;
      final text = controller.text.trim();

      if (text.isEmpty) continue;

      if (field.type == 'tags') {
        // Convert comma-separated to JSON array
        final tags = text
            .split(RegExp(r'[,\n]'))
            .map((t) => t.trim())
            .where((t) => t.isNotEmpty)
            .toList();
        newContext[field.key] = jsonEncode(tags);
      } else if (field.type == 'number') {
        newContext[field.key] = text;
      } else if (field.type == 'toggle') {
        newContext[field.key] = text;
      } else {
        newContext[field.key] = text;
      }
    }

    // Preserve extra context keys not in required_context
    final knownKeys =
        widget.director.requiredContext.map((f) => f.key).toSet();
    for (final entry in widget.director.contextWindow.entries) {
      if (!knownKeys.contains(entry.key)) {
        final controller = _controllers[entry.key];
        if (controller != null && controller.text.trim().isNotEmpty) {
          newContext[entry.key] = controller.text.trim();
        } else {
          // Preserve original value
          newContext[entry.key] = entry.value is String
              ? entry.value
              : jsonEncode(entry.value);
        }
      }
    }

    final ok = await ref
        .read(directorsProvider.notifier)
        .updateContext(dio, widget.director.id, newContext);

    if (!mounted) return;
    setState(() => _saving = false);

    if (ok) {
      showToast(
          context, L10n.t('directors.contextSaved', lang),
          type: ToastType.success);
      Navigator.of(context).pop();
    } else {
      showToast(context, 'Error', type: ToastType.error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
    final d = widget.director;

    // Separate fields into required, optional, and runtime
    final requiredFields = d.requiredContext
        .where((f) => f.required && !f.readOnly && !f.autoManaged)
        .toList();
    final optionalFields = d.requiredContext
        .where((f) => !f.required && !f.readOnly && !f.autoManaged)
        .toList();
    final runtimeFields = d.requiredContext
        .where((f) => f.readOnly || f.autoManaged)
        .toList();

    // Extra keys not in required_context
    final knownKeys = d.requiredContext.map((f) => f.key).toSet();
    final extraKeys = d.contextWindow.keys
        .where((k) => !knownKeys.contains(k))
        .toList();

    final filledRequired = requiredFields
        .where((f) => !d.missingFields.contains(f.key))
        .length;
    final totalRequired = requiredFields.length;

    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Stack(
          children: [
            Column(
          children: [
            // Drag handle
            Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 8),
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: cs.onSurfaceVariant.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // Title
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Text(d.emoji, style: const TextStyle(fontSize: 24)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          d.name,
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                            color: cs.onSurface,
                          ),
                        ),
                        Text(
                          L10n.t('directors.contextEditor', lang),
                          style: TextStyle(
                            fontSize: 13,
                            color: cs.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 12),

            // Setup progress indicator (when setup needed)
            if (d.needsSetup && totalRequired > 0)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.amber.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                        color: Colors.amber.withValues(alpha: 0.3)),
                  ),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Icon(Icons.checklist_rounded,
                              color: Colors.amber.shade700, size: 18),
                          const SizedBox(width: 8),
                          Text(
                            L10n.t('directors.setupProgress', lang, {
                              'done': '$filledRequired',
                              'total': '$totalRequired',
                            }),
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                              color: Colors.amber.shade700,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: totalRequired > 0
                              ? filledRequired / totalRequired
                              : 0,
                          backgroundColor: cs.surfaceContainerHighest,
                          color: Colors.amber.shade700,
                          minHeight: 6,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            const SizedBox(height: 8),

            // Form
            Expanded(
              child: Form(
                key: _formKey,
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  children: [
                    // ── Required fields section ──
                    if (requiredFields.isNotEmpty) ...[
                      _GroupHeader(
                        group: '_required',
                        lang: lang,
                        cs: cs,
                      ),
                      for (final field in requiredFields) ...[
                        _buildField(field, lang, cs),
                        const SizedBox(height: 16),
                      ],
                    ],

                    // ── Optional fields section (collapsible) ──
                    if (optionalFields.isNotEmpty)
                      _CollapsibleOptionalGroup(
                        fields: optionalFields,
                        lang: lang,
                        cs: cs,
                        buildField: (f) => _buildField(f, lang, cs),
                      ),

                    // Extra context keys (not from template)
                    if (extraKeys.isNotEmpty) ...[
                      _GroupHeader(
                        group: 'extra',
                        lang: lang,
                        cs: cs,
                      ),
                      for (final key in extraKeys) ...[
                        TextFormField(
                          controller: _controllers[key],
                          decoration: InputDecoration(
                            labelText: key,
                            border: const OutlineInputBorder(),
                          ),
                          maxLines: 3,
                          minLines: 1,
                        ),
                        const SizedBox(height: 16),
                      ],
                    ],

                    // Runtime / auto-managed fields (collapsible)
                    if (runtimeFields.isNotEmpty)
                      _CollapsibleRuntimeGroup(
                        fields: runtimeFields,
                        contextWindow: widget.director.contextWindow,
                        lang: lang,
                        cs: cs,
                      ),

                    const SizedBox(height: 80), // Space for FAB
                  ],
                ),
              ),
            ),
          ],
        ),
        // Save button
        Positioned(
          bottom: 16,
          left: 20,
          right: 20,
          child: FilledButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.save_outlined),
            label: Text(L10n.t('directors.contextSave', lang)),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
          ],
        );
      },
    );
  }

  Widget _buildField(ContextFieldMeta field, String lang, ColorScheme cs) {
    final controller = _controllers[field.key]!;
    final label = field.localizedLabel(lang);
    final hint = field.localizedHint(lang);

    final requiredSuffix = field.required
        ? Text(' *',
            style: TextStyle(
                color: cs.error, fontSize: 14, fontWeight: FontWeight.w700))
        : null;

    Widget fieldWidget = switch (field.type) {
      'textarea' => TextFormField(
          controller: controller,
          decoration: InputDecoration(
            labelText: label,
            hintText: hint,
            border: const OutlineInputBorder(),
            suffix: requiredSuffix,
            alignLabelWithHint: true,
          ),
          maxLines: 6,
          minLines: 3,
          validator: field.required
              ? (v) => (v == null || v.trim().isEmpty)
                  ? L10n.t('directors.fieldRequired', lang)
                  : null
              : null,
        ),
      'tags' => _TagsFormField(
          controller: controller,
          label: label,
          hint: hint,
          required: field.required,
          lang: lang,
          cs: cs,
        ),
      'number' => TextFormField(
          controller: controller,
          decoration: InputDecoration(
            labelText: label,
            hintText: hint,
            border: const OutlineInputBorder(),
            suffix: requiredSuffix,
          ),
          keyboardType: TextInputType.number,
          validator: field.required
              ? (v) => (v == null || v.trim().isEmpty)
                  ? L10n.t('directors.fieldRequired', lang)
                  : null
              : null,
        ),
      'select' => DropdownButtonFormField<String>(
          initialValue: controller.text.isNotEmpty ? controller.text : null,
          items: field.options
              .map((o) => DropdownMenuItem(value: o, child: Text(o)))
              .toList(),
          onChanged: (v) => controller.text = v ?? '',
          decoration: InputDecoration(
            labelText: label,
            border: const OutlineInputBorder(),
          ),
          validator: field.required
              ? (v) => (v == null || v.isEmpty)
                  ? L10n.t('directors.fieldRequired', lang)
                  : null
              : null,
        ),
      'toggle' => SwitchListTile(
          title: Text(label),
          subtitle: hint.isNotEmpty
              ? Text(hint, style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant))
              : null,
          value: controller.text == 'true',
          onChanged: (v) => setState(() => controller.text = v.toString()),
          contentPadding: EdgeInsets.zero,
        ),
      _ => TextFormField(
          controller: controller,
          decoration: InputDecoration(
            labelText: label,
            hintText: hint,
            border: const OutlineInputBorder(),
            suffix: requiredSuffix,
          ),
          validator: field.required
              ? (v) => (v == null || v.trim().isEmpty)
                  ? L10n.t('directors.fieldRequired', lang)
                  : null
              : null,
        ),
    };

    // Add file upload card for textarea fields that allow file attach
    if (field.allowFileAttach && field.type == 'textarea') {
      fieldWidget = Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Prominent file upload card
          _FileUploadCard(controller: controller, lang: lang, cs: cs),
          const SizedBox(height: 8),
          // Separator with "or type manually"
          Row(
            children: [
              Expanded(
                child: Divider(
                    color: cs.outlineVariant.withValues(alpha: 0.3)),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Text(
                  L10n.t('directors.orTypeManually', lang),
                  style: TextStyle(
                      fontSize: 11, color: cs.onSurfaceVariant),
                ),
              ),
              Expanded(
                child: Divider(
                    color: cs.outlineVariant.withValues(alpha: 0.3)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          fieldWidget,
        ],
      );
    }

    // Add info tooltip for hint text on non-file fields
    if (!field.allowFileAttach && hint.isNotEmpty) {
      fieldWidget = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          fieldWidget,
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 4),
            child: Row(
              children: [
                Icon(Icons.info_outline,
                    size: 12, color: cs.onSurfaceVariant.withValues(alpha: 0.6)),
                const SizedBox(width: 4),
                Flexible(
                  child: Text(
                    hint,
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

    return fieldWidget;
  }
}

// ---------------------------------------------------------------------------
// Group header
// ---------------------------------------------------------------------------

class _GroupHeader extends StatelessWidget {
  final String group;
  final String lang;
  final ColorScheme cs;

  const _GroupHeader({
    required this.group,
    required this.lang,
    required this.cs,
  });

  @override
  Widget build(BuildContext context) {
    final label = switch (group) {
      '_required' => L10n.t('directors.requiredFields', lang),
      '_optional' => L10n.t('directors.optionalFields', lang),
      'profile' => L10n.t('directors.contextGroups.profile', lang),
      'search' => L10n.t('directors.contextGroups.search', lang),
      'filters' => L10n.t('directors.contextGroups.filters', lang),
      'extra' => L10n.t('directors.contextGroups.extra', lang),
      'runtime' => L10n.t('directors.contextGroups.runtime', lang),
      _ => L10n.t('directors.contextGroups.general', lang),
    };

    final icon = switch (group) {
      '_required' => Icons.star_rounded,
      '_optional' => Icons.tune,
      'profile' => Icons.person_outline,
      'search' => Icons.search,
      'filters' => Icons.filter_list,
      'extra' => Icons.more_horiz,
      'runtime' => Icons.auto_mode_outlined,
      _ => Icons.settings_outlined,
    };

    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 12),
      child: Row(
        children: [
          Icon(icon, size: 18, color: cs.primary),
          const SizedBox(width: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: cs.primary,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Divider(color: cs.outlineVariant.withValues(alpha: 0.3)),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Tags form field — chips + add input
// ---------------------------------------------------------------------------

class _TagsFormField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final bool required;
  final String lang;
  final ColorScheme cs;

  const _TagsFormField({
    required this.controller,
    required this.label,
    required this.hint,
    required this.required,
    required this.lang,
    required this.cs,
  });

  @override
  State<_TagsFormField> createState() => _TagsFormFieldState();
}

class _TagsFormFieldState extends State<_TagsFormField> {
  late List<String> _tags;
  final _addController = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _parseTags();
  }

  void _parseTags() {
    final text = widget.controller.text.trim();
    if (text.isEmpty) {
      _tags = [];
      return;
    }

    // Try JSON array first, then comma-separated
    try {
      final decoded = jsonDecode(text);
      if (decoded is List) {
        _tags = decoded.map((e) => e.toString()).toList();
        return;
      }
    } catch (_) {}

    _tags = text
        .split(RegExp(r'[,\n]'))
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .toList();
  }

  void _syncToController() {
    widget.controller.text = _tags.join(', ');
  }

  void _addTag(String tag) {
    final trimmed = tag.trim();
    if (trimmed.isEmpty || _tags.contains(trimmed)) return;
    setState(() {
      _tags.add(trimmed);
      _syncToController();
      _addController.clear();
    });
  }

  void _removeTag(int index) {
    setState(() {
      _tags.removeAt(index);
      _syncToController();
    });
  }

  @override
  void dispose() {
    _addController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final requiredStar = widget.required
        ? Text(' *',
            style: TextStyle(
                color: widget.cs.error,
                fontSize: 14,
                fontWeight: FontWeight.w700))
        : null;

    return FormField<String>(
      validator: widget.required
          ? (_) => _tags.isEmpty
              ? L10n.t('directors.fieldRequired', widget.lang)
              : null
          : null,
      builder: (state) {
        return InputDecorator(
          decoration: InputDecoration(
            labelText: widget.label,
            hintText: _tags.isEmpty ? widget.hint : null,
            border: const OutlineInputBorder(),
            suffix: requiredStar,
            errorText: state.errorText,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_tags.isNotEmpty)
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (var i = 0; i < _tags.length; i++)
                      InputChip(
                        label: Text(_tags[i],
                            style: const TextStyle(fontSize: 12)),
                        onDeleted: () => _removeTag(i),
                        deleteIconColor: widget.cs.onSurfaceVariant,
                        materialTapTargetSize:
                            MaterialTapTargetSize.shrinkWrap,
                        visualDensity: VisualDensity.compact,
                      ),
                  ],
                ),
              if (_tags.isNotEmpty) const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _addController,
                      focusNode: _focusNode,
                      decoration: InputDecoration(
                        hintText: L10n.t('directors.addTag', widget.lang),
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding: EdgeInsets.zero,
                      ),
                      style: const TextStyle(fontSize: 13),
                      onSubmitted: (v) {
                        _addTag(v);
                        _focusNode.requestFocus();
                      },
                    ),
                  ),
                  IconButton(
                    icon: Icon(Icons.add_circle_outline,
                        size: 20, color: widget.cs.primary),
                    onPressed: () {
                      _addTag(_addController.text);
                      _focusNode.requestFocus();
                    },
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Collapsible optional group — collapsed by default when director needs setup
// ---------------------------------------------------------------------------

class _CollapsibleOptionalGroup extends StatefulWidget {
  final List<ContextFieldMeta> fields;
  final String lang;
  final ColorScheme cs;
  final Widget Function(ContextFieldMeta) buildField;

  const _CollapsibleOptionalGroup({
    required this.fields,
    required this.lang,
    required this.cs,
    required this.buildField,
  });

  @override
  State<_CollapsibleOptionalGroup> createState() =>
      _CollapsibleOptionalGroupState();
}

class _CollapsibleOptionalGroupState extends State<_CollapsibleOptionalGroup> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        InkWell(
          onTap: () => setState(() => _expanded = !_expanded),
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 12),
            child: Row(
              children: [
                Icon(Icons.tune, size: 18, color: widget.cs.primary),
                const SizedBox(width: 8),
                Text(
                  L10n.t('directors.optionalFields', widget.lang),
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: widget.cs.primary,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  '(${widget.fields.length})',
                  style: TextStyle(
                      fontSize: 12, color: widget.cs.onSurfaceVariant),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Divider(
                      color:
                          widget.cs.outlineVariant.withValues(alpha: 0.3)),
                ),
                const SizedBox(width: 4),
                Icon(
                  _expanded ? Icons.expand_less : Icons.expand_more,
                  size: 20,
                  color: widget.cs.onSurfaceVariant,
                ),
              ],
            ),
          ),
        ),
        if (_expanded)
          ...widget.fields.map((field) => Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: widget.buildField(field),
              )),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// File upload card — prominent card for uploading CV / documents
// ---------------------------------------------------------------------------

class _FileUploadCard extends StatelessWidget {
  final TextEditingController controller;
  final String lang;
  final ColorScheme cs;

  const _FileUploadCard({
    required this.controller,
    required this.lang,
    required this.cs,
  });

  Future<void> _pickFile(BuildContext context) async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['txt', 'md', 'csv', 'json', 'pdf', 'docx'],
      withData: true,
    );

    if (result == null || result.files.single.bytes == null) return;

    final bytes = result.files.single.bytes!;
    final text = String.fromCharCodes(bytes);
    final fileName = result.files.single.name;

    if (!context.mounted) return;

    if (controller.text.trim().isEmpty) {
      controller.text = text;
      showToast(
        context,
        L10n.t('directors.fileLoaded', lang, {'name': fileName}),
        type: ToastType.success,
      );
    } else {
      final action = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(L10n.t('directors.fileAttachAction', lang)),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop('replace'),
              child: Text(L10n.t('directors.fileReplace', lang)),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop('append'),
              child: Text(L10n.t('directors.fileAppend', lang)),
            ),
          ],
        ),
      );
      if (action == 'replace') {
        controller.text = text;
      } else if (action == 'append') {
        controller.text = '${controller.text}\n\n$text';
      }
      if (context.mounted && action != null) {
        showToast(
          context,
          L10n.t('directors.fileLoaded', lang, {'name': fileName}),
          type: ToastType.success,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasContent = controller.text.trim().isNotEmpty;

    return InkWell(
      onTap: () => _pickFile(context),
      borderRadius: BorderRadius.circular(14),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: cs.primary.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: cs.primary.withValues(alpha: 0.25),
            width: 1.5,
          ),
        ),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: cs.primary.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(
                hasContent ? Icons.description : Icons.upload_file,
                size: 28,
                color: cs.primary,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              L10n.t('directors.uploadCV', lang),
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 14,
                color: cs.primary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              hasContent
                  ? '${controller.text.trim().length} chars'
                  : L10n.t('directors.uploadCVHint', lang),
              style: TextStyle(
                fontSize: 12,
                color: cs.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Collapsible runtime group — collapsed by default, shows auto-managed fields
// ---------------------------------------------------------------------------

class _CollapsibleRuntimeGroup extends StatefulWidget {
  final List<ContextFieldMeta> fields;
  final Map<String, dynamic> contextWindow;
  final String lang;
  final ColorScheme cs;

  const _CollapsibleRuntimeGroup({
    required this.fields,
    required this.contextWindow,
    required this.lang,
    required this.cs,
  });

  @override
  State<_CollapsibleRuntimeGroup> createState() =>
      _CollapsibleRuntimeGroupState();
}

class _CollapsibleRuntimeGroupState extends State<_CollapsibleRuntimeGroup> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        InkWell(
          onTap: () => setState(() => _expanded = !_expanded),
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 12),
            child: Row(
              children: [
                Icon(Icons.auto_mode_outlined,
                    size: 18, color: widget.cs.primary),
                const SizedBox(width: 8),
                Text(
                  L10n.t('directors.contextGroups.runtime', widget.lang),
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: widget.cs.primary,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  '(${widget.fields.length})',
                  style: TextStyle(
                      fontSize: 12, color: widget.cs.onSurfaceVariant),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Divider(
                      color: widget.cs.outlineVariant.withValues(alpha: 0.3)),
                ),
                const SizedBox(width: 4),
                Icon(
                  _expanded ? Icons.expand_less : Icons.expand_more,
                  size: 20,
                  color: widget.cs.onSurfaceVariant,
                ),
              ],
            ),
          ),
        ),
        if (_expanded)
          ...widget.fields.map((field) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _ReadOnlyField(
                  label: field.localizedLabel(widget.lang),
                  hint: field.localizedHint(widget.lang),
                  value: _resolveValue(field),
                  autoManaged: field.autoManaged,
                  cs: widget.cs,
                  lang: widget.lang,
                ),
              )),
      ],
    );
  }

  String _resolveValue(ContextFieldMeta field) {
    final raw = widget.contextWindow[field.key];
    if (raw == null) return field.defaultValue;
    if (raw is String) return raw;
    return jsonEncode(raw);
  }
}

// ---------------------------------------------------------------------------
// Read-only field display
// ---------------------------------------------------------------------------

class _ReadOnlyField extends StatefulWidget {
  final String label;
  final String hint;
  final String value;
  final bool autoManaged;
  final ColorScheme cs;
  final String lang;

  const _ReadOnlyField({
    required this.label,
    required this.hint,
    required this.value,
    required this.autoManaged,
    required this.cs,
    required this.lang,
  });

  @override
  State<_ReadOnlyField> createState() => _ReadOnlyFieldState();
}

class _ReadOnlyFieldState extends State<_ReadOnlyField> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final isLong = widget.value.length > 100;
    final display = _expanded || !isLong
        ? widget.value
        : '${widget.value.substring(0, 100)}...';
    final isEmpty = widget.value.isEmpty;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: widget.cs.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: widget.cs.outlineVariant.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (widget.autoManaged)
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: Icon(Icons.auto_mode,
                      size: 14, color: widget.cs.onSurfaceVariant),
                ),
              Expanded(
                child: Text(
                  widget.label,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: widget.cs.onSurfaceVariant,
                  ),
                ),
              ),
              if (widget.autoManaged)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: widget.cs.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    L10n.t('directors.autoManaged', widget.lang),
                    style: TextStyle(fontSize: 10, color: widget.cs.primary),
                  ),
                ),
            ],
          ),
          if (widget.hint.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                widget.hint,
                style: TextStyle(
                    fontSize: 11, color: widget.cs.onSurfaceVariant),
              ),
            ),
          const SizedBox(height: 6),
          Text(
            isEmpty
                ? L10n.t('directors.noValueYet', widget.lang)
                : display,
            style: TextStyle(
              fontSize: 13,
              color: isEmpty
                  ? widget.cs.onSurfaceVariant.withValues(alpha: 0.5)
                  : widget.cs.onSurface,
              fontFamily: _looksLikeJson(widget.value) ? 'monospace' : null,
            ),
          ),
          if (isLong)
            GestureDetector(
              onTap: () => setState(() => _expanded = !_expanded),
              child: Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  _expanded
                      ? L10n.t('directors.showLess', widget.lang)
                      : L10n.t('directors.showMore', widget.lang),
                  style: TextStyle(fontSize: 12, color: widget.cs.primary),
                ),
              ),
            ),
        ],
      ),
    );
  }

  bool _looksLikeJson(String text) =>
      text.startsWith('{') || text.startsWith('[');
}

// ---------------------------------------------------------------------------
// Save FAB — used externally to overlay on the bottom sheet
// ---------------------------------------------------------------------------

/// A floating save button to place at the bottom of the context editor.
/// This is called from the sheet's build method.
class ContextEditorSaveFab extends StatelessWidget {
  final VoidCallback onPressed;
  final bool saving;
  final String lang;

  const ContextEditorSaveFab({
    super.key,
    required this.onPressed,
    required this.saving,
    required this.lang,
  });

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton.extended(
      onPressed: saving ? null : onPressed,
      icon: saving
          ? const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.save_outlined),
      label: Text(L10n.t('directors.contextSave', lang)),
    );
  }
}
