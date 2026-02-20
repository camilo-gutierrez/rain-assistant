import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';

class CwdPickerSheet extends ConsumerStatefulWidget {
  final String agentId;
  final ValueChanged<String> onSelected;

  const CwdPickerSheet({
    super.key,
    required this.agentId,
    required this.onSelected,
  });

  @override
  ConsumerState<CwdPickerSheet> createState() => _CwdPickerSheetState();
}

class _CwdPickerSheetState extends ConsumerState<CwdPickerSheet> {
  List<Map<String, dynamic>> _entries = [];
  String _currentPath = '~';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadDirectory('~');
  }

  Future<void> _loadDirectory(String path) async {
    setState(() => _loading = true);
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/browse', queryParameters: {'path': path});
      if (!mounted) return;
      setState(() {
        _currentPath = res.data['current'] ?? path;
        _entries =
            List<Map<String, dynamic>>.from(res.data['entries'] ?? []);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    return SizedBox(
      height: MediaQuery.of(context).size.height * 0.65,
      child: Column(
        children: [
          // Handle
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: 12, bottom: 8),
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
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                Text(L10n.t('agent.selectDir', lang),
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600)),
                const Spacer(),
                FilledButton.tonal(
                  onPressed: () => widget.onSelected(_currentPath),
                  child: Text(L10n.t('agent.useThis', lang)),
                ),
              ],
            ),
          ),
          // Path bar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: cs.surfaceContainer,
            child: Text(
              _currentPath,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: cs.onSurfaceVariant,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          // Directory listing
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    itemCount: _entries.length,
                    itemBuilder: (context, index) {
                      final entry = _entries[index];
                      final isDir = entry['is_dir'] == true;
                      final name = entry['name'] as String;
                      return ListTile(
                        dense: true,
                        leading: Icon(
                          isDir
                              ? Icons.folder
                              : Icons.insert_drive_file_outlined,
                          size: 20,
                          color: isDir ? cs.primary : cs.onSurfaceVariant,
                        ),
                        title:
                            Text(name, style: const TextStyle(fontSize: 14)),
                        onTap: isDir
                            ? () => _loadDirectory(entry['path'] as String)
                            : null,
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
