import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/agent_provider.dart';
import '../providers/connection_provider.dart';

/// Simple directory selector for setting the agent's CWD.
/// Full file browser comes in Phase 7.
class FileBrowserScreen extends ConsumerStatefulWidget {
  final VoidCallback onSelected;

  const FileBrowserScreen({super.key, required this.onSelected});

  @override
  ConsumerState<FileBrowserScreen> createState() => _FileBrowserScreenState();
}

class _FileBrowserScreenState extends ConsumerState<FileBrowserScreen> {
  List<Map<String, dynamic>> _entries = [];
  String _currentPath = '~';
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDirectory('~');
  }

  Future<void> _loadDirectory(String path) async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/browse', queryParameters: {'path': path});

      if (!mounted) return;

      setState(() {
        _currentPath = res.data['current'] ?? path;
        _entries = List<Map<String, dynamic>>.from(res.data['entries'] ?? []);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Error cargando directorio';
      });
    }
  }

  void _selectDirectory() {
    final agentNotifier = ref.read(agentProvider.notifier);
    final agentId = agentNotifier.ensureDefaultAgent();

    // Set CWD on server
    final ws = ref.read(webSocketServiceProvider);
    final agent = ref.read(agentProvider).agents[agentId];
    ws.send({
      'type': 'set_cwd',
      'path': _currentPath,
      'agent_id': agentId,
      if (agent?.sessionId != null) 'session_id': agent!.sessionId,
    });

    widget.onSelected();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Seleccionar directorio'),
      ),
      body: Column(
        children: [
          // Current path bar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            color: cs.surfaceContainer,
            child: Row(
              children: [
                Icon(Icons.folder_open, size: 18, color: cs.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _currentPath,
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 13,
                      color: cs.onSurface,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),

          // Directory listing
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.error_outline, size: 48, color: cs.error),
                            const SizedBox(height: 8),
                            Text(_error!, style: TextStyle(color: cs.error)),
                            const SizedBox(height: 16),
                            OutlinedButton(
                              onPressed: () => _loadDirectory(_currentPath),
                              child: const Text('Reintentar'),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        itemCount: _entries.length,
                        itemBuilder: (context, index) {
                          final entry = _entries[index];
                          final isDir = entry['is_dir'] == true;
                          final name = entry['name'] as String;

                          return ListTile(
                            leading: Icon(
                              isDir ? Icons.folder : Icons.insert_drive_file_outlined,
                              color: isDir ? cs.primary : cs.onSurfaceVariant,
                            ),
                            title: Text(name),
                            trailing: isDir
                                ? const Icon(Icons.chevron_right, size: 20)
                                : null,
                            onTap: isDir
                                ? () => _loadDirectory(entry['path'] as String)
                                : null,
                          );
                        },
                      ),
          ),

          // Select button
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: ElevatedButton.icon(
                onPressed: _selectDirectory,
                icon: const Icon(Icons.check),
                label: const Text('Usar este directorio'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
