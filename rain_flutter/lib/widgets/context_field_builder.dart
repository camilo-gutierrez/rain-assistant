/// Shared field-rendering utilities for director context forms.
///
/// Used by both [ContextEditorSheet] (per-director) and
/// [TeamSetupWizardScreen] (unified team wizard).
library;

import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../app/l10n.dart';
import '../models/director.dart';
import 'toast.dart';

// ---------------------------------------------------------------------------
// File parsing helper — sends binary files to the backend for text extraction
// ---------------------------------------------------------------------------

/// Extensions that are plain text and can be decoded client-side.
const _textExtensions = {'.txt', '.md', '.csv', '.tsv', '.json'};

/// Extensions that need backend parsing (binary formats).
const _binaryExtensions = {'.pdf', '.docx', '.html', '.htm'};

/// Parse a file's bytes into text. For plain text files, decodes UTF-8
/// client-side. For binary files (PDF, DOCX), sends to the backend endpoint
/// `POST /api/parse-file` for extraction.
///
/// Returns the extracted text, or `null` on failure.
Future<String?> parseFileContent({
  required Uint8List bytes,
  required String filename,
  required Dio? dio,
  required BuildContext context,
  required String lang,
}) async {
  final ext = filename.contains('.')
      ? '.${filename.split('.').last.toLowerCase()}'
      : '';

  // Plain text files: decode client-side
  if (_textExtensions.contains(ext)) {
    try {
      return utf8.decode(bytes, allowMalformed: true);
    } catch (_) {
      return String.fromCharCodes(bytes);
    }
  }

  // Binary files: send to backend for parsing
  if (_binaryExtensions.contains(ext) && dio != null) {
    try {
      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          bytes,
          filename: filename,
        ),
      });

      final response = await dio.post(
        '/parse-file',
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
      );

      if (response.statusCode == 200 && response.data is Map) {
        return response.data['text'] as String?;
      }

      if (context.mounted) {
        final error = response.data is Map
            ? response.data['error'] ?? 'Unknown error'
            : 'Parse failed';
        showToast(context, 'Error: $error', type: ToastType.error);
      }
      return null;
    } catch (e) {
      debugPrint('[parseFileContent] Backend parse failed: $e');
      if (context.mounted) {
        showToast(context, 'Error parsing file: $e', type: ToastType.error);
      }
      return null;
    }
  }

  // Fallback: try to decode as text (may produce garbage for binary files)
  try {
    return utf8.decode(bytes, allowMalformed: true);
  } catch (_) {
    return String.fromCharCodes(bytes);
  }
}

// ---------------------------------------------------------------------------
// Public entry point — builds the right widget for any ContextFieldMeta
// ---------------------------------------------------------------------------

/// Renders a single context field based on its [ContextFieldMeta.type].
///
/// The returned widget is self-contained: it reads/writes from [controller]
/// and validates according to [field.required].
Widget buildContextField(
  ContextFieldMeta field,
  TextEditingController controller,
  String lang,
  ColorScheme cs, {
  void Function(VoidCallback)? setStateCallback,
  Dio? dio,
}) {
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
    'tags' => TagsFormField(
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
            ? Text(hint,
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant))
            : null,
        value: controller.text == 'true',
        onChanged: (v) {
          controller.text = v.toString();
          setStateCallback?.call(() {});
        },
        contentPadding: EdgeInsets.zero,
      ),
    // ── New field types ──────────────────────────────────────────────
    'file' => FileOnlyUploadCard(
        controller: controller,
        label: label,
        hint: hint,
        required: field.required,
        acceptedExtensions: field.acceptedExtensions.isNotEmpty
            ? field.acceptedExtensions
            : const ['txt', 'md', 'csv', 'json', 'pdf', 'docx'],
        lang: lang,
        cs: cs,
        dio: dio,
      ),
    'date' => DatePickerField(
        controller: controller,
        label: label,
        hint: hint,
        required: field.required,
        lang: lang,
        cs: cs,
      ),
    'radio' => RadioGroupField(
        controller: controller,
        label: label,
        hint: hint,
        options: field.options,
        required: field.required,
        lang: lang,
        cs: cs,
        setStateCallback: setStateCallback,
      ),
    'multiselect' => MultiselectField(
        controller: controller,
        label: label,
        hint: hint,
        options: field.options,
        required: field.required,
        lang: lang,
        cs: cs,
        setStateCallback: setStateCallback,
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
        FileUploadCard(controller: controller, lang: lang, cs: cs, dio: dio),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child:
                  Divider(color: cs.outlineVariant.withValues(alpha: 0.3)),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text(
                L10n.t('directors.orTypeManually', lang),
                style:
                    TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
              ),
            ),
            Expanded(
              child:
                  Divider(color: cs.outlineVariant.withValues(alpha: 0.3)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        fieldWidget,
      ],
    );
  }

  // Add info tooltip for hint text on non-file fields
  if (!field.allowFileAttach &&
      field.type != 'file' &&
      field.type != 'radio' &&
      field.type != 'multiselect' &&
      field.type != 'toggle' &&
      field.type != 'date' &&
      hint.isNotEmpty) {
    fieldWidget = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        fieldWidget,
        Padding(
          padding: const EdgeInsets.only(top: 4, left: 4),
          child: Row(
            children: [
              Icon(Icons.info_outline,
                  size: 12,
                  color: cs.onSurfaceVariant.withValues(alpha: 0.6)),
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

// ---------------------------------------------------------------------------
// Tags form field — chips + add input
// ---------------------------------------------------------------------------

class TagsFormField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final bool required;
  final String lang;
  final ColorScheme cs;

  const TagsFormField({
    super.key,
    required this.controller,
    required this.label,
    required this.hint,
    required this.required,
    required this.lang,
    required this.cs,
  });

  @override
  State<TagsFormField> createState() => _TagsFormFieldState();
}

class _TagsFormFieldState extends State<TagsFormField> {
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
// File upload card — for textarea fields with allowFileAttach
// ---------------------------------------------------------------------------

class FileUploadCard extends StatefulWidget {
  final TextEditingController controller;
  final String lang;
  final ColorScheme cs;
  final Dio? dio;

  const FileUploadCard({
    super.key,
    required this.controller,
    required this.lang,
    required this.cs,
    this.dio,
  });

  @override
  State<FileUploadCard> createState() => _FileUploadCardState();
}

class _FileUploadCardState extends State<FileUploadCard> {
  bool _parsing = false;

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['txt', 'md', 'csv', 'json', 'pdf', 'docx'],
      withData: true,
    );

    if (result == null || result.files.single.bytes == null) return;

    final bytes = result.files.single.bytes!;
    final fileName = result.files.single.name;

    if (!context.mounted) return;
    setState(() => _parsing = true);

    final text = await parseFileContent(
      bytes: bytes,
      filename: fileName,
      dio: widget.dio,
      context: context,
      lang: widget.lang,
    );

    if (!mounted) return;
    setState(() => _parsing = false);

    if (text == null) return; // parseFileContent already showed error toast

    if (widget.controller.text.trim().isEmpty) {
      widget.controller.text = text;
      if (context.mounted) {
        showToast(
          context,
          L10n.t('directors.fileLoaded', widget.lang, {'name': fileName}),
          type: ToastType.success,
        );
      }
    } else {
      if (!context.mounted) return;
      final action = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(L10n.t('directors.fileAttachAction', widget.lang)),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop('replace'),
              child: Text(L10n.t('directors.fileReplace', widget.lang)),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop('append'),
              child: Text(L10n.t('directors.fileAppend', widget.lang)),
            ),
          ],
        ),
      );
      if (action == 'replace') {
        widget.controller.text = text;
      } else if (action == 'append') {
        widget.controller.text = '${widget.controller.text}\n\n$text';
      }
      if (context.mounted && action != null) {
        showToast(
          context,
          L10n.t('directors.fileLoaded', widget.lang, {'name': fileName}),
          type: ToastType.success,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasContent = widget.controller.text.trim().isNotEmpty;

    return InkWell(
      onTap: _parsing ? null : _pickFile,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: widget.cs.primary.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: widget.cs.primary.withValues(alpha: 0.25),
            width: 1.5,
          ),
        ),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: widget.cs.primary.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: _parsing
                  ? SizedBox(
                      width: 28,
                      height: 28,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: widget.cs.primary,
                      ),
                    )
                  : Icon(
                      hasContent ? Icons.description : Icons.upload_file,
                      size: 28,
                      color: widget.cs.primary,
                    ),
            ),
            const SizedBox(height: 10),
            Text(
              _parsing
                  ? 'Parsing...'
                  : L10n.t('directors.uploadCV', widget.lang),
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 14,
                color: widget.cs.primary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              _parsing
                  ? ''
                  : hasContent
                      ? '${widget.controller.text.trim().length} chars'
                      : L10n.t('directors.uploadCVHint', widget.lang),
              style: TextStyle(
                fontSize: 12,
                color: widget.cs.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// File-only upload card — dedicated file field (no textarea fallback)
// ---------------------------------------------------------------------------

class FileOnlyUploadCard extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final bool required;
  final List<String> acceptedExtensions;
  final String lang;
  final ColorScheme cs;
  final Dio? dio;

  const FileOnlyUploadCard({
    super.key,
    required this.controller,
    required this.label,
    required this.hint,
    required this.required,
    required this.acceptedExtensions,
    required this.lang,
    required this.cs,
    this.dio,
  });

  @override
  State<FileOnlyUploadCard> createState() => _FileOnlyUploadCardState();
}

class _FileOnlyUploadCardState extends State<FileOnlyUploadCard> {
  String? _fileName;
  int? _fileSize;

  @override
  void initState() {
    super.initState();
    // If controller already has content, show as "loaded"
    if (widget.controller.text.trim().isNotEmpty) {
      _fileName = '(previously loaded)';
      _fileSize = widget.controller.text.length;
    }
  }

  bool _parsing = false;

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: widget.acceptedExtensions,
      withData: true,
    );

    if (result == null || result.files.single.bytes == null) return;

    final bytes = result.files.single.bytes!;
    final fileName = result.files.single.name;
    final fileSize = bytes.length;

    if (!mounted) return;
    setState(() => _parsing = true);

    final text = await parseFileContent(
      bytes: bytes,
      filename: fileName,
      dio: widget.dio,
      context: context,
      lang: widget.lang,
    );

    if (!mounted) return;
    setState(() => _parsing = false);

    if (text == null) return; // parseFileContent already showed error toast

    widget.controller.text = text;

    setState(() {
      _fileName = fileName;
      _fileSize = fileSize;
    });

    if (context.mounted) {
      showToast(
        context,
        L10n.t('directors.fileLoaded', widget.lang, {'name': fileName}),
        type: ToastType.success,
      );
    }
  }

  void _clearFile() {
    widget.controller.clear();
    setState(() {
      _fileName = null;
      _fileSize = null;
    });
  }

  String _formatSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  @override
  Widget build(BuildContext context) {
    final hasFile = _fileName != null;
    final extStr = widget.acceptedExtensions.map((e) => '.$e').join(', ');

    return FormField<String>(
      validator: widget.required
          ? (_) => widget.controller.text.trim().isEmpty
              ? L10n.t('directors.fieldRequired', widget.lang)
              : null
          : null,
      builder: (state) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Label
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Text(
                    widget.label,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: widget.cs.onSurface,
                    ),
                  ),
                  if (widget.required)
                    Text(' *',
                        style: TextStyle(
                            color: widget.cs.error,
                            fontSize: 14,
                            fontWeight: FontWeight.w700)),
                ],
              ),
            ),
            // Upload card
            InkWell(
              onTap: _pickFile,
              borderRadius: BorderRadius.circular(14),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: hasFile
                      ? Colors.green.withValues(alpha: 0.06)
                      : widget.cs.primary.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: hasFile
                        ? Colors.green.withValues(alpha: 0.3)
                        : state.hasError
                            ? widget.cs.error.withValues(alpha: 0.5)
                            : widget.cs.primary.withValues(alpha: 0.25),
                    width: 1.5,
                  ),
                ),
                child: Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: hasFile
                            ? Colors.green.withValues(alpha: 0.1)
                            : widget.cs.primary.withValues(alpha: 0.1),
                        shape: BoxShape.circle,
                      ),
                      child: _parsing
                          ? SizedBox(
                              width: 28,
                              height: 28,
                              child: CircularProgressIndicator(
                                strokeWidth: 2.5,
                                color: widget.cs.primary,
                              ),
                            )
                          : Icon(
                              hasFile ? Icons.check_circle : Icons.upload_file,
                              size: 28,
                              color: hasFile ? Colors.green : widget.cs.primary,
                            ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      _parsing
                          ? 'Parsing...'
                          : hasFile
                              ? _fileName!
                              : L10n.t('directors.uploadFile', widget.lang),
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: hasFile ? Colors.green : widget.cs.primary,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      hasFile
                          ? _formatSize(_fileSize ?? 0)
                          : widget.hint.isNotEmpty
                              ? widget.hint
                              : extStr,
                      style: TextStyle(
                        fontSize: 12,
                        color: widget.cs.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            // Clear button
            if (hasFile)
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: _clearFile,
                  icon: Icon(Icons.clear, size: 16, color: widget.cs.error),
                  label: Text(
                    L10n.t('directors.clearFile', widget.lang),
                    style: TextStyle(fontSize: 12, color: widget.cs.error),
                  ),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                  ),
                ),
              ),
            // Error
            if (state.hasError)
              Padding(
                padding: const EdgeInsets.only(top: 4, left: 12),
                child: Text(
                  state.errorText!,
                  style: TextStyle(fontSize: 12, color: widget.cs.error),
                ),
              ),
          ],
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Date picker field
// ---------------------------------------------------------------------------

class DatePickerField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final bool required;
  final String lang;
  final ColorScheme cs;

  const DatePickerField({
    super.key,
    required this.controller,
    required this.label,
    required this.hint,
    required this.required,
    required this.lang,
    required this.cs,
  });

  @override
  State<DatePickerField> createState() => _DatePickerFieldState();
}

class _DatePickerFieldState extends State<DatePickerField> {
  Future<void> _pickDate() async {
    final initial = DateTime.tryParse(widget.controller.text) ?? DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2020),
      lastDate: DateTime(2040),
      locale: widget.lang == 'es' ? const Locale('es') : const Locale('en'),
    );
    if (picked != null) {
      final formatted =
          '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
      widget.controller.text = formatted;
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final requiredSuffix = widget.required
        ? Text(' *',
            style: TextStyle(
                color: widget.cs.error,
                fontSize: 14,
                fontWeight: FontWeight.w700))
        : null;

    return TextFormField(
      controller: widget.controller,
      readOnly: true,
      onTap: _pickDate,
      decoration: InputDecoration(
        labelText: widget.label,
        hintText: widget.hint.isNotEmpty
            ? widget.hint
            : L10n.t('directors.selectDate', widget.lang),
        border: const OutlineInputBorder(),
        suffix: requiredSuffix,
        suffixIcon: Icon(Icons.calendar_today, size: 20, color: widget.cs.primary),
      ),
      validator: widget.required
          ? (v) => (v == null || v.trim().isEmpty)
              ? L10n.t('directors.fieldRequired', widget.lang)
              : null
          : null,
    );
  }
}

// ---------------------------------------------------------------------------
// Radio group field — all options visible at once
// ---------------------------------------------------------------------------

class RadioGroupField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final List<String> options;
  final bool required;
  final String lang;
  final ColorScheme cs;
  final void Function(VoidCallback)? setStateCallback;

  const RadioGroupField({
    super.key,
    required this.controller,
    required this.label,
    required this.hint,
    required this.options,
    required this.required,
    required this.lang,
    required this.cs,
    this.setStateCallback,
  });

  @override
  State<RadioGroupField> createState() => _RadioGroupFieldState();
}

class _RadioGroupFieldState extends State<RadioGroupField> {
  late String? _selected;

  @override
  void initState() {
    super.initState();
    _selected =
        widget.controller.text.isNotEmpty ? widget.controller.text : null;
  }

  @override
  Widget build(BuildContext context) {
    // Fallback: if no options, render as text field
    if (widget.options.isEmpty) {
      return TextFormField(
        controller: widget.controller,
        decoration: InputDecoration(
          labelText: widget.label,
          hintText: widget.hint,
          border: const OutlineInputBorder(),
        ),
      );
    }

    return FormField<String>(
      initialValue: _selected,
      validator: widget.required
          ? (v) => (v == null || v.isEmpty)
              ? L10n.t('directors.fieldRequired', widget.lang)
              : null
          : null,
      builder: (state) {
        return InputDecorator(
          decoration: InputDecoration(
            labelText: widget.label,
            border: const OutlineInputBorder(),
            errorText: state.errorText,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (widget.hint.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    widget.hint,
                    style: TextStyle(
                        fontSize: 12, color: widget.cs.onSurfaceVariant),
                  ),
                ),
              RadioGroup<String>(
                groupValue: _selected ?? '',
                onChanged: (String? v) {
                  setState(() => _selected = v);
                  widget.controller.text = v ?? '';
                  state.didChange(v);
                  widget.setStateCallback?.call(() {});
                },
                child: Column(
                  children: widget.options
                      .map(
                        (option) => RadioListTile<String>(
                          title: Text(option,
                              style: const TextStyle(fontSize: 14)),
                          value: option,
                          contentPadding: EdgeInsets.zero,
                          visualDensity: VisualDensity.compact,
                          dense: true,
                        ),
                      )
                      .toList(),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Multiselect field — filter chips for multiple selection
// ---------------------------------------------------------------------------

class MultiselectField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final List<String> options;
  final bool required;
  final String lang;
  final ColorScheme cs;
  final void Function(VoidCallback)? setStateCallback;

  const MultiselectField({
    super.key,
    required this.controller,
    required this.label,
    required this.hint,
    required this.options,
    required this.required,
    required this.lang,
    required this.cs,
    this.setStateCallback,
  });

  @override
  State<MultiselectField> createState() => _MultiselectFieldState();
}

class _MultiselectFieldState extends State<MultiselectField> {
  late Set<String> _selected;

  @override
  void initState() {
    super.initState();
    _parseSelected();
  }

  void _parseSelected() {
    final text = widget.controller.text.trim();
    if (text.isEmpty) {
      _selected = {};
      return;
    }
    try {
      final decoded = jsonDecode(text);
      if (decoded is List) {
        _selected = decoded.map((e) => e.toString()).toSet();
        return;
      }
    } catch (_) {}
    _selected = text
        .split(RegExp(r'[,\n]'))
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .toSet();
  }

  void _syncToController() {
    widget.controller.text = jsonEncode(_selected.toList());
  }

  @override
  Widget build(BuildContext context) {
    // Fallback: if no options, render as tags field
    if (widget.options.isEmpty) {
      return TagsFormField(
        controller: widget.controller,
        label: widget.label,
        hint: widget.hint,
        required: widget.required,
        lang: widget.lang,
        cs: widget.cs,
      );
    }

    return FormField<Set<String>>(
      initialValue: _selected,
      validator: widget.required
          ? (v) => (v == null || v.isEmpty)
              ? L10n.t('directors.fieldRequired', widget.lang)
              : null
          : null,
      builder: (state) {
        return InputDecorator(
          decoration: InputDecoration(
            labelText: widget.label,
            border: const OutlineInputBorder(),
            errorText: state.errorText,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (widget.hint.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    widget.hint,
                    style: TextStyle(
                        fontSize: 12, color: widget.cs.onSurfaceVariant),
                  ),
                ),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: widget.options.map((option) {
                  final isSelected = _selected.contains(option);
                  return FilterChip(
                    label: Text(option, style: const TextStyle(fontSize: 13)),
                    selected: isSelected,
                    onSelected: (selected) {
                      setState(() {
                        if (selected) {
                          _selected.add(option);
                        } else {
                          _selected.remove(option);
                        }
                        _syncToController();
                        state.didChange(_selected);
                      });
                      widget.setStateCallback?.call(() {});
                    },
                    selectedColor: widget.cs.primary.withValues(alpha: 0.15),
                    checkmarkColor: widget.cs.primary,
                    visualDensity: VisualDensity.compact,
                  );
                }).toList(),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Group header (reusable across editor sheet and wizard)
// ---------------------------------------------------------------------------

class ContextGroupHeader extends StatelessWidget {
  final String group;
  final String lang;
  final ColorScheme cs;

  const ContextGroupHeader({
    super.key,
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
