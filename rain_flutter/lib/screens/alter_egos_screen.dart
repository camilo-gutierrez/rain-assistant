import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class AlterEgosScreen extends ConsumerStatefulWidget {
  const AlterEgosScreen({super.key});

  @override
  ConsumerState<AlterEgosScreen> createState() => _AlterEgosScreenState();
}

class _AlterEgosScreenState extends ConsumerState<AlterEgosScreen> {
  List<Map<String, dynamic>>? _egos;
  String? _activeEgoId;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadEgos();
  }

  Future<void> _loadEgos() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/alter-egos');
      if (!mounted) return;
      final data = res.data as Map<String, dynamic>;
      final list = (data['egos'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      setState(() {
        _egos = list;
        _activeEgoId = data['active_ego_id'] as String? ?? 'rain';
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  void _switchEgo(String egoId) {
    final ws = ref.read(webSocketServiceProvider);
    ws.send({'type': 'set_alter_ego', 'ego_id': egoId});
    setState(() => _activeEgoId = egoId);
    final lang = ref.read(settingsProvider).language;
    showToast(context, L10n.t('egos.switchTo', lang), type: ToastType.success);
  }

  Future<void> _deleteEgo(String egoId) async {
    final lang = ref.read(settingsProvider).language;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(L10n.t('egos.delete', lang)),
        content: Text(L10n.t('egos.deleteConfirm', lang)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(L10n.t('agent.cancel', lang)),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(L10n.t('egos.delete', lang)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      await dio.delete('/alter-egos/$egoId');
      if (!mounted) return;
      await _loadEgos();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    }
  }

  void _showCreateSheet() {
    final lang = ref.read(settingsProvider).language;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _CreateEgoSheet(
        lang: lang,
        onCreated: (data) async {
          Navigator.of(ctx).pop();
          try {
            final auth = ref.read(authServiceProvider);
            final dio = auth.authenticatedDio;
            await dio.post('/alter-egos', data: data);
            if (!mounted) return;
            showToast(context, L10n.t('egos.create', lang),
                type: ToastType.success);
            await _loadEgos();
          } catch (e) {
            if (!mounted) return;
            showToast(context, e.toString(), type: ToastType.error);
          }
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('egos.title', lang)),
        actions: [
          IconButton(
            onPressed: _loadEgos,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateSheet,
        icon: const Icon(Icons.add),
        label: Text(L10n.t('egos.create', lang)),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.error_outline, size: 48, color: cs.error),
                      const SizedBox(height: 16),
                      Text(_error!,
                          textAlign: TextAlign.center,
                          style: TextStyle(color: cs.onSurfaceVariant)),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: _loadEgos,
                        icon: const Icon(Icons.refresh),
                        label: Text(L10n.t('metrics.refresh', lang)),
                      ),
                    ],
                  ),
                )
              : _egos == null || _egos!.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.person_outline,
                              size: 48,
                              color:
                                  cs.onSurfaceVariant.withValues(alpha: 0.3)),
                          const SizedBox(height: 16),
                          Text(L10n.t('egos.empty', lang),
                              style: TextStyle(color: cs.onSurfaceVariant)),
                        ],
                      ),
                    )
                  : _buildEgoList(cs, lang),
    );
  }

  Widget _buildEgoList(ColorScheme cs, String lang) {
    // Separate built-in and custom egos
    final builtIn =
        _egos!.where((e) => e['built_in'] == true).toList();
    final custom =
        _egos!.where((e) => e['built_in'] != true).toList();

    return ListView(
      padding: const EdgeInsets.only(bottom: 80),
      children: [
        if (builtIn.isNotEmpty) ...[
          _SectionHeader(L10n.t('egos.builtIn', lang)),
          ...builtIn.map((ego) => _EgoCard(
                ego: ego,
                isActive: ego['id'] == _activeEgoId,
                lang: lang,
                onTap: () => _switchEgo(ego['id'] as String),
                onDelete: null,
              )),
        ],
        if (custom.isNotEmpty) ...[
          _SectionHeader(L10n.t('egos.custom', lang)),
          ...custom.map((ego) => _EgoCard(
                ego: ego,
                isActive: ego['id'] == _activeEgoId,
                lang: lang,
                onTap: () => _switchEgo(ego['id'] as String),
                onDelete: () => _deleteEgo(ego['id'] as String),
              )),
        ],
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Ego card
// ---------------------------------------------------------------------------

class _EgoCard extends StatelessWidget {
  final Map<String, dynamic> ego;
  final bool isActive;
  final String lang;
  final VoidCallback onTap;
  final VoidCallback? onDelete;

  const _EgoCard({
    required this.ego,
    required this.isActive,
    required this.lang,
    required this.onTap,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final emoji = (ego['emoji'] as String?) ?? '';
    final name = (ego['name'] as String?) ?? '';
    final description = (ego['description'] as String?) ?? '';
    final builtIn = ego['built_in'] == true;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Card(
        elevation: isActive ? 3 : 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: isActive
              ? BorderSide(color: cs.primary, width: 2)
              : BorderSide.none,
        ),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                // Emoji avatar
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isActive
                        ? cs.primaryContainer
                        : cs.surfaceContainerHighest,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    emoji,
                    style: const TextStyle(fontSize: 26),
                  ),
                ),
                const SizedBox(width: 14),

                // Name + description
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              name,
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 15,
                                color: isActive ? cs.primary : cs.onSurface,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (isActive) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: cs.primary,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                L10n.t('egos.active', lang),
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: cs.onPrimary,
                                ),
                              ),
                            ),
                          ],
                          if (builtIn && !isActive) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: cs.surfaceContainerHighest,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                L10n.t('egos.builtIn', lang),
                                style: TextStyle(
                                  fontSize: 10,
                                  color: cs.onSurfaceVariant,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      if (description.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          description,
                          style: TextStyle(
                            fontSize: 12,
                            color: cs.onSurfaceVariant,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),

                // Delete button (only for custom egos)
                if (onDelete != null)
                  IconButton(
                    onPressed: onDelete,
                    icon: Icon(Icons.delete_outline, color: cs.error),
                    tooltip: L10n.t('egos.delete', lang),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Create ego bottom sheet
// ---------------------------------------------------------------------------

class _CreateEgoSheet extends StatefulWidget {
  final String lang;
  final Future<void> Function(Map<String, dynamic> data) onCreated;

  const _CreateEgoSheet({
    required this.lang,
    required this.onCreated,
  });

  @override
  State<_CreateEgoSheet> createState() => _CreateEgoSheetState();
}

class _CreateEgoSheetState extends State<_CreateEgoSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _emojiCtrl = TextEditingController(text: '\u{1F916}');
  final _descCtrl = TextEditingController();
  final _promptCtrl = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _emojiCtrl.dispose();
    _descCtrl.dispose();
    _promptCtrl.dispose();
    super.dispose();
  }

  String _generateId(String name) {
    return name
        .toLowerCase()
        .trim()
        .replaceAll(RegExp(r'[^a-z0-9]+'), '_')
        .replaceAll(RegExp(r'^_+|_+$'), '');
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);

    final data = <String, dynamic>{
      'id': _generateId(_nameCtrl.text),
      'name': _nameCtrl.text.trim(),
      'emoji': _emojiCtrl.text.trim(),
      'description': _descCtrl.text.trim(),
      'system_prompt': _promptCtrl.text.trim(),
    };

    await widget.onCreated(data);

    if (mounted) setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = widget.lang;

    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Drag handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: cs.onSurfaceVariant.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Title
              Text(
                L10n.t('egos.createTitle', lang),
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: cs.onSurface,
                ),
              ),
              const SizedBox(height: 20),

              // Emoji + Name row
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Emoji field
                  SizedBox(
                    width: 72,
                    child: TextFormField(
                      controller: _emojiCtrl,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 28),
                      decoration: InputDecoration(
                        labelText: L10n.t('egos.emoji', lang),
                        border: const OutlineInputBorder(),
                        contentPadding: const EdgeInsets.symmetric(
                            vertical: 12, horizontal: 8),
                      ),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? '' : null,
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Name field
                  Expanded(
                    child: TextFormField(
                      controller: _nameCtrl,
                      decoration: InputDecoration(
                        labelText: L10n.t('egos.name', lang),
                        border: const OutlineInputBorder(),
                      ),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? '' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Description
              TextFormField(
                controller: _descCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('egos.description', lang),
                  border: const OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 14),

              // System prompt
              TextFormField(
                controller: _promptCtrl,
                decoration: InputDecoration(
                  labelText: L10n.t('egos.systemPrompt', lang),
                  border: const OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
                maxLines: 5,
                minLines: 3,
              ),
              const SizedBox(height: 20),

              // Buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed:
                          _saving ? null : () => Navigator.of(context).pop(),
                      child: Text(L10n.t('agent.cancel', lang)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: _saving ? null : _submit,
                      child: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child:
                                  CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(L10n.t('egos.create', lang)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }
}
