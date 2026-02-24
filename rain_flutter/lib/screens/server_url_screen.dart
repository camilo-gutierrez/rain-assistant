import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';

class ServerUrlScreen extends ConsumerStatefulWidget {
  final VoidCallback onConnected;

  const ServerUrlScreen({super.key, required this.onConnected});

  @override
  ConsumerState<ServerUrlScreen> createState() => _ServerUrlScreenState();
}

class _ServerUrlScreenState extends ConsumerState<ServerUrlScreen> {
  final _controller = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    // Pre-populate with saved URL if available
    final savedUrl = ref.read(authServiceProvider).serverUrl;
    if (savedUrl != null) {
      _controller.text = savedUrl;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final url = _controller.text.trim();
    if (url.isEmpty) {
      setState(() => _error = L10n.t('serverUrl.errorEmpty', ref.read(settingsProvider).language));
      return;
    }

    // Basic validation
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      setState(() => _error = L10n.t('serverUrl.errorProtocol', ref.read(settingsProvider).language));
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    final auth = ref.read(authServiceProvider);
    await auth.setServerUrl(url);

    final reachable = await auth.pingServer();
    if (!reachable) {
      setState(() {
        _loading = false;
        _error = L10n.t('serverUrl.errorUnreachable', ref.read(settingsProvider).language);
      });
      return;
    }

    setState(() => _loading = false);
    ref.read(hasServerUrlProvider.notifier).state = true;
    widget.onConnected();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Logo
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: cs.primaryContainer,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Icon(
                      Icons.cloud_outlined,
                      size: 40,
                      color: cs.primary,
                    ),
                  ),
                  const SizedBox(height: 24),

                  Text(
                    'Rain Assistant',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    L10n.t('serverUrl.subtitle', lang),
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: cs.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 40),

                  // URL input
                  TextField(
                    controller: _controller,
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    textInputAction: TextInputAction.go,
                    onSubmitted: (_) => _connect(),
                    decoration: InputDecoration(
                      labelText: L10n.t('serverUrl.label', lang),
                      hintText: L10n.t('serverUrl.hint', lang),
                      prefixIcon: const Icon(Icons.link),
                      errorText: _error,
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Helper text
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.info_outline, size: 16, color: cs.onSurfaceVariant),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            L10n.t('serverUrl.helperText', lang),
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: cs.onSurfaceVariant,
                                ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Connect button
                  ElevatedButton(
                    onPressed: _loading ? null : _connect,
                    child: _loading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(L10n.t('serverUrl.connect', lang)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
