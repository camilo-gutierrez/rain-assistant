import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/connection_provider.dart';

class PinScreen extends ConsumerStatefulWidget {
  final VoidCallback onAuthenticated;

  const PinScreen({super.key, required this.onAuthenticated});

  @override
  ConsumerState<PinScreen> createState() => _PinScreenState();
}

class _PinScreenState extends ConsumerState<PinScreen> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();
  bool _loading = false;
  String? _error;
  int? _remainingAttempts;
  int? _lockedSeconds;

  @override
  void initState() {
    super.initState();
    // Auto-focus the PIN field
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final pin = _controller.text.trim();
    if (pin.isEmpty) {
      setState(() => _error = 'Ingresa el PIN');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
      _remainingAttempts = null;
      _lockedSeconds = null;
    });

    final auth = ref.read(authServiceProvider);
    final result = await auth.authenticate(pin);

    if (!mounted) return;

    if (result.success) {
      setState(() => _loading = false);
      ref.read(isAuthenticatedProvider.notifier).state = true;
      widget.onAuthenticated();
    } else {
      setState(() {
        _loading = false;
        _error = result.error ?? 'Error de autenticación';
        _remainingAttempts = result.remainingAttempts;
        _lockedSeconds = result.locked ? result.remainingSeconds : null;
        _controller.clear();
      });
      _focusNode.requestFocus();
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final serverUrl = ref.read(authServiceProvider).serverUrl ?? '';

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
                  // Lock icon
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: cs.primaryContainer,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Icon(
                      Icons.lock_outline,
                      size: 40,
                      color: cs.primary,
                    ),
                  ),
                  const SizedBox(height: 24),

                  Text(
                    'Ingresa tu PIN',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    serverUrl,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: cs.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 40),

                  // PIN input
                  TextField(
                    controller: _controller,
                    focusNode: _focusNode,
                    keyboardType: TextInputType.number,
                    obscureText: true,
                    textAlign: TextAlign.center,
                    inputFormatters: [
                      LengthLimitingTextInputFormatter(20),
                    ],
                    onSubmitted: (_) => _submit(),
                    style: const TextStyle(
                      fontSize: 24,
                      letterSpacing: 8,
                      fontWeight: FontWeight.bold,
                    ),
                    decoration: InputDecoration(
                      hintText: '• • • • • •',
                      errorText: _error,
                      prefixIcon: const Icon(Icons.pin),
                    ),
                  ),

                  // Lockout warning
                  if (_lockedSeconds != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: cs.errorContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.timer, size: 16, color: cs.error),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Bloqueado por ${(_lockedSeconds! / 60).ceil()} minutos',
                              style: TextStyle(color: cs.error, fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Remaining attempts
                  if (_remainingAttempts != null && _lockedSeconds == null) ...[
                    const SizedBox(height: 12),
                    Text(
                      '$_remainingAttempts intento(s) restante(s)',
                      style: TextStyle(color: cs.error, fontSize: 13),
                    ),
                  ],

                  const SizedBox(height: 24),

                  // Submit button
                  ElevatedButton(
                    onPressed: _loading || _lockedSeconds != null ? null : _submit,
                    child: _loading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Ingresar'),
                  ),
                  const SizedBox(height: 16),

                  // Change server button
                  TextButton.icon(
                    onPressed: () async {
                      await ref.read(authServiceProvider).clearAll();
                      ref.read(hasServerUrlProvider.notifier).state = false;
                    },
                    icon: const Icon(Icons.dns_outlined, size: 16),
                    label: const Text('Cambiar servidor'),
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
