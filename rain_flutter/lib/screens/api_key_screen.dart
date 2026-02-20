import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
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

  // OAuth detection state
  bool _checkingOAuth = true;
  bool _oauthDetected = false;
  String _subscriptionType = '';

  @override
  void initState() {
    super.initState();
    _checkOAuth();
  }

  @override
  void dispose() {
    _keyController.dispose();
    super.dispose();
  }

  Future<void> _checkOAuth() async {
    try {
      final auth = ref.read(authServiceProvider);
      final dio = auth.authenticatedDio;
      final res = await dio.get('/check-oauth');
      if (!mounted) return;
      setState(() {
        _checkingOAuth = false;
        _oauthDetected = res.data['available'] == true &&
            res.data['expired'] != true;
        _subscriptionType = res.data['subscriptionType'] ?? '';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _checkingOAuth = false);
    }
  }

  void _usePersonalAccount() {
    final settings = ref.read(settingsProvider);
    final ws = ref.read(webSocketServiceProvider);

    ws.send({
      'type': 'set_api_key',
      'auth_mode': 'oauth',
      'model': settings.aiModel,
    });

    widget.onConfigured();
  }

  void _submit() {
    final key = _keyController.text.trim();
    if (key.isEmpty) return;

    final settings = ref.read(settingsProvider);
    final ws = ref.read(webSocketServiceProvider);

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
    final lang = settings.language;
    final isClaude = settings.aiProvider == AIProvider.claude;

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
                  // Icon
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
                    L10n.t('apiKey.title', lang),
                    style: Theme.of(context)
                        .textTheme
                        .headlineMedium
                        ?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 32),

                  // ── Personal account section (always visible for Claude) ──
                  if (isClaude) ...[
                    // Detected badge (only if check succeeded)
                    if (_oauthDetected)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.green.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.check_circle,
                                  size: 14, color: Colors.green),
                              const SizedBox(width: 6),
                              Text(
                                '${L10n.t('apiKey.personalAccountActive', lang)} (${_subscriptionType.toUpperCase()})',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.green,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                    // Personal account button (always shown for Claude)
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _checkingOAuth ? null : _usePersonalAccount,
                        icon: _checkingOAuth
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.person_outlined),
                        label: Text(
                          L10n.t('apiKey.personalAccount', lang),
                        ),
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          textStyle: const TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      L10n.t('apiKey.personalAccountDesc', lang),
                      style: TextStyle(
                        fontSize: 12,
                        color: cs.onSurfaceVariant,
                      ),
                    ),

                    // Divider
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 20),
                      child: Row(
                        children: [
                          Expanded(
                            child: Divider(
                                color: cs.outlineVariant
                                    .withValues(alpha: 0.5)),
                          ),
                          Padding(
                            padding:
                                const EdgeInsets.symmetric(horizontal: 16),
                            child: Text(
                              L10n.t('apiKey.orEnterKey', lang),
                              style: TextStyle(
                                fontSize: 12,
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ),
                          Expanded(
                            child: Divider(
                                color: cs.outlineVariant
                                    .withValues(alpha: 0.5)),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // ── Provider selector ──
                  SegmentedButton<AIProvider>(
                    segments: AIProvider.values.map((p) {
                      return ButtonSegment(
                        value: p,
                        label: Text(providerInfo[p]!.name),
                      );
                    }).toList(),
                    selected: {settings.aiProvider},
                    onSelectionChanged: (selection) {
                      ref
                          .read(settingsProvider.notifier)
                          .setAIProvider(selection.first);
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
                          _obscureKey
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                        onPressed: () =>
                            setState(() => _obscureKey = !_obscureKey),
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
                    decoration: InputDecoration(
                      labelText: L10n.t('provider.model', lang),
                      prefixIcon: const Icon(Icons.psychology_outlined),
                    ),
                    items:
                        (providerModels[settings.aiProvider] ?? []).map((m) {
                      return DropdownMenuItem(
                          value: m.id, child: Text(m.name));
                    }).toList(),
                    onChanged: (v) {
                      if (v != null) {
                        ref.read(settingsProvider.notifier).setAIModel(v);
                      }
                    },
                  ),
                  const SizedBox(height: 32),

                  // Submit button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _submit,
                      child: Text(L10n.t('apiKey.connect', lang)),
                    ),
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
