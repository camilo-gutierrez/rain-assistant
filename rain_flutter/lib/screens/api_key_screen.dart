import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/provider_info.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';

class ApiKeyScreen extends ConsumerStatefulWidget {
  final VoidCallback onConfigured;

  const ApiKeyScreen({super.key, required this.onConfigured});

  @override
  ConsumerState<ApiKeyScreen> createState() => _ApiKeyScreenState();
}

class _ApiKeyScreenState extends ConsumerState<ApiKeyScreen> {
  final _keyController = TextEditingController();
  bool _obscureKey = true;

  @override
  void dispose() {
    _keyController.dispose();
    super.dispose();
  }

  void _submit() {
    final key = _keyController.text.trim();
    if (key.isEmpty) return;

    final settings = ref.read(settingsProvider);
    final ws = ref.read(webSocketServiceProvider);

    // Send API key to server via WebSocket
    ws.send({
      'type': 'set_api_key',
      'key': key,
      'provider': settings.aiProvider.name,
      'model': settings.aiModel,
    });

    widget.onConfigured();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final settings = ref.watch(settingsProvider);
    final info = providerInfo[settings.aiProvider]!;

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
                  // Key icon
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: cs.primaryContainer,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Icon(
                      Icons.key_outlined,
                      size: 40,
                      color: cs.primary,
                    ),
                  ),
                  const SizedBox(height: 24),

                  Text(
                    'API Key',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Configura tu clave de API para usar Rain',
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: cs.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 32),

                  // Provider selector
                  SegmentedButton<AIProvider>(
                    segments: AIProvider.values.map((p) {
                      return ButtonSegment(
                        value: p,
                        label: Text(providerInfo[p]!.name),
                      );
                    }).toList(),
                    selected: {settings.aiProvider},
                    onSelectionChanged: (selection) {
                      ref.read(settingsProvider.notifier).setAIProvider(selection.first);
                    },
                  ),
                  const SizedBox(height: 24),

                  // API Key input
                  TextField(
                    controller: _keyController,
                    obscureText: _obscureKey,
                    autocorrect: false,
                    onSubmitted: (_) => _submit(),
                    decoration: InputDecoration(
                      labelText: '${info.name} API Key',
                      hintText: info.keyPlaceholder,
                      prefixIcon: const Icon(Icons.vpn_key_outlined),
                      suffixIcon: IconButton(
                        icon: Icon(
                          _obscureKey ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                        ),
                        onPressed: () => setState(() => _obscureKey = !_obscureKey),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Console link hint
                  Align(
                    alignment: Alignment.centerRight,
                    child: Text(
                      info.consoleUrl,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: cs.primary,
                          ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Model selector
                  DropdownButtonFormField<String>(
                    initialValue: settings.aiModel,
                    decoration: const InputDecoration(
                      labelText: 'Modelo',
                      prefixIcon: Icon(Icons.psychology_outlined),
                    ),
                    items: (providerModels[settings.aiProvider] ?? []).map((m) {
                      return DropdownMenuItem(value: m.id, child: Text(m.name));
                    }).toList(),
                    onChanged: (v) {
                      if (v != null) ref.read(settingsProvider.notifier).setAIModel(v);
                    },
                  ),
                  const SizedBox(height: 32),

                  // Submit button
                  ElevatedButton(
                    onPressed: _submit,
                    child: const Text('Continuar'),
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
