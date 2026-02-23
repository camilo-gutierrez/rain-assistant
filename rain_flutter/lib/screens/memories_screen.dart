import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class _Memory {
  final int id;
  final String content;
  final String category;
  final String createdAt;

  _Memory({
    required this.id,
    required this.content,
    required this.category,
    required this.createdAt,
  });

  factory _Memory.fromJson(Map<String, dynamic> json) {
    return _Memory(
      id: json['id'] as int,
      content: json['content'] as String? ?? '',
      category: json['category'] as String? ?? 'fact',
      createdAt: json['created_at'] as String? ?? '',
    );
  }
}

const _categoryColors = <String, Color>{
  'preference': Colors.blue,
  'fact': Colors.green,
  'pattern': Colors.orange,
  'project': Colors.purple,
};

const _categories = ['preference', 'fact', 'pattern', 'project'];

class MemoriesScreen extends ConsumerStatefulWidget {
  const MemoriesScreen({super.key});

  @override
  ConsumerState<MemoriesScreen> createState() => _MemoriesScreenState();
}

class _MemoriesScreenState extends ConsumerState<MemoriesScreen> {
  List<_Memory>? _memories;
  bool _loading = true;
  String? _error;
  String? _confirmDeleteId;
  String? _activeFilter; // null = all

  @override
  void initState() {
    super.initState();
    _loadMemories();
  }

  Future<void> _loadMemories() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/memories');
      if (!mounted) return;
      final list = (res.data['memories'] as List? ?? [])
          .map((e) => _Memory.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() {
        _memories = list;
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

  Future<void> _addMemory(String content, String category) async {
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      await dio.post('/memories', data: {
        'content': content,
        'category': category,
      });
      if (!mounted) return;
      await _loadMemories();
    } catch (_) {
      if (!mounted) return;
      final lang = ref.read(settingsProvider).language;
      showToast(context, L10n.t('toast.sendFailed', lang),
          type: ToastType.error);
    }
  }

  Future<void> _deleteMemory(int id) async {
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      await dio.delete('/memories/$id');
      if (!mounted) return;
      await _loadMemories();
    } catch (_) {}
  }

  Future<void> _clearAll() async {
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      await dio.delete('/memories');
      if (!mounted) return;
      final lang = ref.read(settingsProvider).language;
      showToast(context, L10n.t('toast.clearSuccess', lang),
          type: ToastType.info);
      await _loadMemories();
    } catch (_) {}
  }

  void _showAddDialog() {
    final lang = ref.read(settingsProvider).language;
    final controller = TextEditingController();
    String selectedCategory = 'fact';

    showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            final cs = Theme.of(ctx).colorScheme;
            return AlertDialog(
              title: Text(L10n.t('memories.addTitle', lang)),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: controller,
                    maxLines: 3,
                    decoration: InputDecoration(
                      hintText: L10n.t('memories.placeholder', lang),
                      border: const OutlineInputBorder(),
                    ),
                    autofocus: true,
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 8,
                    children: _categories.map((cat) {
                      final selected = cat == selectedCategory;
                      final color = _categoryColors[cat] ?? cs.primary;
                      return ChoiceChip(
                        label: Text(L10n.t('memories.cat.$cat', lang)),
                        selected: selected,
                        selectedColor: color.withValues(alpha: 0.25),
                        labelStyle: TextStyle(
                          color: selected ? color : cs.onSurfaceVariant,
                          fontWeight:
                              selected ? FontWeight.w600 : FontWeight.normal,
                        ),
                        side: BorderSide(
                          color: selected ? color : cs.outlineVariant,
                        ),
                        onSelected: (_) {
                          setDialogState(() => selectedCategory = cat);
                        },
                      );
                    }).toList(),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: Text(L10n.t('agent.cancel', lang)),
                ),
                FilledButton(
                  onPressed: () {
                    final text = controller.text.trim();
                    if (text.isEmpty) return;
                    Navigator.of(ctx).pop();
                    _addMemory(text, selectedCategory);
                  },
                  child: Text(L10n.t('memories.add', lang)),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showClearAllDialog() {
    final lang = ref.read(settingsProvider).language;
    showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: Text(L10n.t('memories.clearAll', lang)),
          content: Text(L10n.t('memories.clearConfirm', lang)),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text(L10n.t('agent.cancel', lang)),
            ),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: Theme.of(ctx).colorScheme.error,
              ),
              onPressed: () {
                Navigator.of(ctx).pop();
                _clearAll();
              },
              child: Text(L10n.t('memories.clearAll', lang)),
            ),
          ],
        );
      },
    );
  }

  List<_Memory> get _filteredMemories {
    if (_memories == null) return [];
    if (_activeFilter == null) return _memories!;
    return _memories!.where((m) => m.category == _activeFilter).toList();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('memories.title', lang)),
        actions: [
          if (_memories != null && _memories!.isNotEmpty)
            IconButton(
              onPressed: _showClearAllDialog,
              icon: const Icon(Icons.delete_sweep),
              tooltip: L10n.t('memories.clearAll', lang),
            ),
          IconButton(
            onPressed: _loadMemories,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddDialog,
        child: const Icon(Icons.add),
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
                      Text(_error!),
                    ],
                  ),
                )
              : _memories == null || _memories!.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.psychology_outlined,
                              size: 48,
                              color:
                                  cs.onSurfaceVariant.withValues(alpha: 0.3)),
                          const SizedBox(height: 16),
                          Text(L10n.t('memories.empty', lang),
                              style:
                                  TextStyle(color: cs.onSurfaceVariant)),
                        ],
                      ),
                    )
                  : Column(
                      children: [
                        // Category filter chips
                        _CategoryFilter(
                          activeFilter: _activeFilter,
                          lang: lang,
                          totalCount: _memories!.length,
                          onSelected: (cat) {
                            setState(() {
                              _activeFilter = cat;
                              _confirmDeleteId = null;
                            });
                          },
                        ),
                        // Count display
                        Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 4),
                          child: Align(
                            alignment: Alignment.centerLeft,
                            child: Text(
                              L10n.t('memories.count', lang, {
                                'n': _filteredMemories.length.toString(),
                              }),
                              style: TextStyle(
                                fontSize: 12,
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ),
                        ),
                        // Memory list
                        Expanded(
                          child: _filteredMemories.isEmpty
                              ? Center(
                                  child: Text(
                                    L10n.t('memories.empty', lang),
                                    style: TextStyle(
                                        color: cs.onSurfaceVariant),
                                  ),
                                )
                              : ListView.builder(
                                  padding:
                                      const EdgeInsets.only(bottom: 80),
                                  itemCount: _filteredMemories.length,
                                  itemBuilder: (context, index) {
                                    final memory =
                                        _filteredMemories[index];
                                    return _MemoryCard(
                                      memory: memory,
                                      lang: lang,
                                      confirmDelete: _confirmDeleteId ==
                                          memory.id.toString(),
                                      onDelete: () {
                                        if (_confirmDeleteId ==
                                            memory.id.toString()) {
                                          _deleteMemory(memory.id);
                                          setState(() =>
                                              _confirmDeleteId = null);
                                        } else {
                                          setState(() =>
                                              _confirmDeleteId =
                                                  memory.id.toString());
                                        }
                                      },
                                    );
                                  },
                                ),
                        ),
                      ],
                    ),
    );
  }
}

class _CategoryFilter extends StatelessWidget {
  final String? activeFilter;
  final String lang;
  final int totalCount;
  final ValueChanged<String?> onSelected;

  const _CategoryFilter({
    required this.activeFilter,
    required this.lang,
    required this.totalCount,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          // "All" chip
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: Text(L10n.t('memories.all', lang)),
              selected: activeFilter == null,
              onSelected: (_) => onSelected(null),
              selectedColor: cs.primaryContainer,
              labelStyle: TextStyle(
                color: activeFilter == null
                    ? cs.onPrimaryContainer
                    : cs.onSurfaceVariant,
                fontWeight: activeFilter == null
                    ? FontWeight.w600
                    : FontWeight.normal,
              ),
            ),
          ),
          // Category chips
          ..._categories.map((cat) {
            final selected = activeFilter == cat;
            final color = _categoryColors[cat] ?? cs.primary;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilterChip(
                label: Text(L10n.t('memories.cat.$cat', lang)),
                selected: selected,
                selectedColor: color.withValues(alpha: 0.25),
                labelStyle: TextStyle(
                  color: selected ? color : cs.onSurfaceVariant,
                  fontWeight:
                      selected ? FontWeight.w600 : FontWeight.normal,
                ),
                side: BorderSide(
                  color: selected ? color : cs.outlineVariant,
                ),
                onSelected: (_) => onSelected(selected ? null : cat),
              ),
            );
          }),
        ],
      ),
    );
  }
}

class _MemoryCard extends StatelessWidget {
  final _Memory memory;
  final String lang;
  final bool confirmDelete;
  final VoidCallback onDelete;

  const _MemoryCard({
    required this.memory,
    required this.lang,
    required this.confirmDelete,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final catColor = _categoryColors[memory.category] ?? cs.primary;

    // Format timestamp
    String dateStr = memory.createdAt;
    try {
      final date = DateTime.parse(memory.createdAt);
      dateStr =
          '${date.day}/${date.month}/${date.year} ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
    } catch (_) {}

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: catColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: catColor.withValues(alpha: 0.4),
                    ),
                  ),
                  child: Text(
                    L10n.t('memories.cat.${memory.category}', lang),
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: catColor,
                    ),
                  ),
                ),
                const Spacer(),
                TextButton(
                  onPressed: onDelete,
                  style: TextButton.styleFrom(
                    foregroundColor:
                        confirmDelete ? cs.error : cs.onSurfaceVariant,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text(
                    confirmDelete
                        ? L10n.t('history.confirmDelete', lang)
                        : L10n.t('history.delete', lang),
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              memory.content,
              style: const TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 8),
            Text(
              dateStr,
              style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}
