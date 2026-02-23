import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/auth.dart';
import '../services/auth_service.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';

const _kRevokeAll = '__REVOKE_ALL__';
const _kRetryLogin = '__RETRY_LOGIN__';

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

  // Device replacement flow
  String? _pendingPin;

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
      setState(() => _error = L10n.t('pinScreen.errorEmpty', ref.read(settingsProvider).language));
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
      _remainingAttempts = null;
      _lockedSeconds = null;
    });

    final auth = ref.read(authServiceProvider);

    final AuthResponse result;
    try {
      result = await auth.authenticate(pin);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.toString();
      });
      _focusNode.requestFocus();
      return;
    }

    if (!mounted) return;

    if (result.success) {
      setState(() => _loading = false);
      ref.read(isAuthenticatedProvider.notifier).state = true;
      widget.onAuthenticated();
    } else {
      final lang = ref.read(settingsProvider).language;
      setState(() {
        _loading = false;
        if (result.deviceLimitReached) {
          // Save PIN for the replacement flow
          _pendingPin = pin;
          _error = null; // Don't show error, we'll show the device picker
          _controller.clear();
        } else {
          _error = result.error ?? L10n.t('pinScreen.errorAuth', lang);
          _controller.clear();
        }
        _remainingAttempts = result.remainingAttempts;
        _lockedSeconds = result.locked ? result.remainingSeconds : null;
      });

      if (result.deviceLimitReached) {
        _showDeviceReplacementSheet();
      } else {
        _focusNode.requestFocus();
      }
    }
  }

  Future<void> _showDeviceReplacementSheet() async {
    final auth = ref.read(authServiceProvider);
    final lang = ref.read(settingsProvider).language;
    final pin = _pendingPin;
    if (pin == null) return;

    // Fetch devices using PIN
    final result = await auth.fetchDevicesWithPin(pin);
    if (!mounted) return;

    if (result == null) {
      setState(() {
        _error = L10n.t('devices.loadError', lang);
        _pendingPin = null;
      });
      _focusNode.requestFocus();
      return;
    }

    final devices = result.devices;
    final maxDevices = result.maxDevices;

    if (!mounted) return;

    // Returns device_id to replace, _kRevokeAll, _kRetryLogin, or null for cancel
    final selection = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _DeviceReplacementSheet(
        devices: devices,
        maxDevices: maxDevices,
        lang: lang,
        auth: auth,
        pin: pin,
      ),
    );

    if (!mounted) return;

    if (selection == null) {
      // User cancelled
      setState(() => _pendingPin = null);
      _focusNode.requestFocus();
      return;
    }

    setState(() => _loading = true);

    if (selection == _kRevokeAll) {
      // Revoke all sessions then retry auth
      final ok = await auth.revokeAllWithPin(pin);
      if (!mounted) return;
      if (!ok) {
        setState(() {
          _loading = false;
          _pendingPin = null;
          _error = L10n.t('devices.revokeAllError', lang);
        });
        _focusNode.requestFocus();
        return;
      }
    }

    // Retry auth
    final AuthResponse authResult;
    if (selection == _kRevokeAll || selection == _kRetryLogin) {
      authResult = await auth.authenticate(pin);
    } else {
      authResult = await auth.authenticate(pin, replaceDeviceId: selection);
    }

    if (!mounted) return;

    if (authResult.success) {
      setState(() {
        _loading = false;
        _pendingPin = null;
      });
      ref.read(isAuthenticatedProvider.notifier).state = true;
      widget.onAuthenticated();
    } else {
      setState(() {
        _loading = false;
        _pendingPin = null;
        _error = authResult.error ?? L10n.t('pinScreen.errorAuth', lang);
      });
      _focusNode.requestFocus();
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
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
                    L10n.t('pinScreen.title', lang),
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
                              L10n.t('pinScreen.locked', lang, {'min': '${(_lockedSeconds! / 60).ceil()}'}),
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
                      L10n.t('pinScreen.attemptsRemaining', lang, {'n': '$_remainingAttempts'}),
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
                        : Text(L10n.t('pinScreen.submit', lang)),
                  ),
                  const SizedBox(height: 16),

                  // Change server button
                  TextButton.icon(
                    onPressed: () async {
                      await ref.read(authServiceProvider).clearAll();
                      ref.read(hasServerUrlProvider.notifier).state = false;
                    },
                    icon: const Icon(Icons.dns_outlined, size: 16),
                    label: Text(L10n.t('pinScreen.changeServer', lang)),
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

/// Bottom sheet that shows active devices and lets the user replace or delete them.
class _DeviceReplacementSheet extends StatefulWidget {
  final List<DeviceInfo> devices;
  final int maxDevices;
  final String lang;
  final AuthService auth;
  final String pin;

  const _DeviceReplacementSheet({
    required this.devices,
    required this.maxDevices,
    required this.lang,
    required this.auth,
    required this.pin,
  });

  @override
  State<_DeviceReplacementSheet> createState() => _DeviceReplacementSheetState();
}

class _DeviceReplacementSheetState extends State<_DeviceReplacementSheet> {
  late List<DeviceInfo> _devices;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _devices = List.of(widget.devices);
  }

  String _formatTime(double ts) {
    final d = DateTime.fromMillisecondsSinceEpoch((ts * 1000).toInt());
    final diff = DateTime.now().difference(d);
    if (diff.inMinutes < 1) return L10n.t('devices.justNow', widget.lang);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m';
    if (diff.inHours < 24) return '${diff.inHours}h';
    return '${d.day}/${d.month}/${d.year}';
  }

  Future<void> _deleteDevice(DeviceInfo device) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        final cs = Theme.of(ctx).colorScheme;
        return AlertDialog(
          icon: Icon(Icons.delete_outline, color: cs.error, size: 32),
          title: Text(L10n.t('devices.revokeConfirm', widget.lang)),
          content: Text(device.deviceName.isNotEmpty ? device.deviceName : 'Unknown'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: Text(L10n.t('agent.cancel', widget.lang)),
            ),
            FilledButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              style: FilledButton.styleFrom(backgroundColor: cs.error),
              child: Text(L10n.t('devices.revoke', widget.lang)),
            ),
          ],
        );
      },
    );

    if (confirmed != true || !mounted) return;

    setState(() => _busy = true);
    final ok = await widget.auth.revokeDeviceWithPin(widget.pin, device.deviceId);
    if (!mounted) return;
    setState(() => _busy = false);

    if (ok) {
      setState(() {
        _devices.removeWhere((d) => d.deviceId == device.deviceId);
      });
      // If under limit now, auto-close so parent can retry login
      if (_devices.length < widget.maxDevices) {
        Navigator.of(context).pop(_kRetryLogin);
      }
    }
  }

  void _confirmReplace(DeviceInfo device) {
    showDialog(
      context: context,
      builder: (ctx) {
        final cs = Theme.of(ctx).colorScheme;
        return AlertDialog(
          icon: Icon(Icons.swap_horiz, color: cs.error, size: 32),
          title: Text(L10n.t('devices.replaceConfirmTitle', widget.lang)),
          content: Text(
            L10n.t('devices.replaceConfirmBody', widget.lang, {
              'name': device.deviceName.isNotEmpty ? device.deviceName : 'Unknown',
            }),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text(L10n.t('agent.cancel', widget.lang)),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(ctx).pop();
                Navigator.of(context).pop(device.deviceId);
              },
              style: FilledButton.styleFrom(backgroundColor: cs.error),
              child: Text(L10n.t('devices.replace', widget.lang)),
            ),
          ],
        );
      },
    );
  }

  void _confirmRevokeAll() {
    showDialog(
      context: context,
      builder: (ctx) {
        final cs = Theme.of(ctx).colorScheme;
        return AlertDialog(
          icon: Icon(Icons.delete_sweep, color: cs.error, size: 32),
          title: Text(L10n.t('devices.revokeAllConfirmTitle', widget.lang)),
          content: Text(L10n.t('devices.revokeAllConfirmBody', widget.lang)),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text(L10n.t('agent.cancel', widget.lang)),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(ctx).pop();
                Navigator.of(context).pop(_kRevokeAll);
              },
              style: FilledButton.styleFrom(backgroundColor: cs.error),
              child: Text(L10n.t('devices.revokeAll', widget.lang)),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return DraggableScrollableSheet(
      initialChildSize: 0.55,
      minChildSize: 0.3,
      maxChildSize: 0.85,
      expand: false,
      builder: (ctx, scrollController) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Drag handle
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: cs.onSurfaceVariant.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(2),
              ),
            ),

            // Header
            Icon(Icons.devices, size: 32, color: cs.primary),
            const SizedBox(height: 8),
            Text(
              L10n.t('devices.replaceTitle', widget.lang),
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            Text(
              L10n.t('devices.replaceSubtitle', widget.lang, {'max': '${widget.maxDevices}'}),
              style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),

            // Device list
            Expanded(
              child: ListView.builder(
                controller: scrollController,
                itemCount: _devices.length,
                itemBuilder: (ctx, i) {
                  final device = _devices[i];
                  final isMobile = RegExp(r'mobile|android|iphone|telegram', caseSensitive: false)
                      .hasMatch(device.deviceName);

                  return Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      child: Row(
                        children: [
                          CircleAvatar(
                            backgroundColor: cs.secondaryContainer,
                            child: Icon(
                              isMobile ? Icons.smartphone : Icons.computer,
                              color: cs.onSecondaryContainer,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  device.deviceName.isNotEmpty ? device.deviceName : 'Unknown',
                                  style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14),
                                  overflow: TextOverflow.ellipsis,
                                ),
                                Text(
                                  '${device.clientIp} · ${_formatTime(device.lastActivity)}',
                                  style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          // Delete button
                          IconButton(
                            onPressed: _busy ? null : () => _deleteDevice(device),
                            icon: Icon(Icons.delete_outline, size: 20, color: cs.error),
                            tooltip: L10n.t('devices.revoke', widget.lang),
                            padding: EdgeInsets.zero,
                            constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                          ),
                          const SizedBox(width: 4),
                          // Replace button
                          FilledButton.tonal(
                            onPressed: _busy ? null : () => _confirmReplace(device),
                            style: FilledButton.styleFrom(
                              backgroundColor: cs.primaryContainer,
                              foregroundColor: cs.primary,
                              padding: const EdgeInsets.symmetric(horizontal: 12),
                              minimumSize: const Size(0, 34),
                            ),
                            child: Text(
                              L10n.t('devices.replace', widget.lang),
                              style: const TextStyle(fontSize: 12),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),

            // Revoke all button
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _busy ? null : () => _confirmRevokeAll(),
                icon: const Icon(Icons.delete_sweep, size: 18),
                label: Text(L10n.t('devices.revokeAll', widget.lang)),
                style: FilledButton.styleFrom(
                  backgroundColor: cs.error,
                  foregroundColor: cs.onError,
                ),
              ),
            ),

            // Cancel button
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(L10n.t('agent.cancel', widget.lang)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
