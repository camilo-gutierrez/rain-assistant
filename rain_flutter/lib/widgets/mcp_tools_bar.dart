import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../app/l10n.dart';

/// MCP server status from /api/mcp/status.
class McpServerInfo {
  final String status;
  final String? error;
  final String label;

  const McpServerInfo({
    required this.status,
    this.error,
    required this.label,
  });

  bool get isOk => status == 'ok';

  factory McpServerInfo.fromJson(Map<String, dynamic> json) => McpServerInfo(
        status: json['status'] as String? ?? 'unknown',
        error: json['error'] as String?,
        label: json['label'] as String? ?? '',
      );
}

/// Definition for each MCP category shown as a chip.
class _McpCategory {
  final String id;
  final String serverName;
  final String labelKey;
  final IconData icon;
  final String prompt;
  final String setupPrompt;

  const _McpCategory({
    required this.id,
    required this.serverName,
    required this.labelKey,
    required this.icon,
    required this.prompt,
    required this.setupPrompt,
  });
}

const _categories = <_McpCategory>[
  _McpCategory(
    id: 'hub',
    serverName: 'rain-hub',
    labelKey: 'mcp.hub',
    icon: Icons.hub_outlined,
    prompt: 'Muéstrame el menú de Rain con todas las capacidades disponibles',
    setupPrompt:
        'Quiero configurar Rain. Usa la herramienta rain_setup_guide para guiarme paso a paso.',
  ),
  _McpCategory(
    id: 'email',
    serverName: 'rain-email',
    labelKey: 'mcp.email',
    icon: Icons.mail_outline,
    prompt:
        'Quiero usar las funciones de email. Muéstrame qué puedo hacer con el correo.',
    setupPrompt:
        'Quiero configurar mi correo electrónico. Usa la herramienta email_setup_oauth para ayudarme a conectar mi cuenta de Gmail paso a paso.',
  ),
  _McpCategory(
    id: 'browser',
    serverName: 'rain-browser',
    labelKey: 'mcp.browser',
    icon: Icons.language,
    prompt:
        'Quiero navegar por la web. Muéstrame qué puedo hacer con el navegador.',
    setupPrompt:
        'Quiero usar el navegador web. Ábrelo y muéstrame qué puedo hacer.',
  ),
  _McpCategory(
    id: 'calendar',
    serverName: 'rain-calendar',
    labelKey: 'mcp.calendar',
    icon: Icons.calendar_today_outlined,
    prompt: 'Quiero ver mi calendario. Muéstrame mis eventos próximos.',
    setupPrompt:
        'Quiero configurar mi calendario. Usa la herramienta calendar_setup_oauth para ayudarme a conectar mi Google Calendar paso a paso.',
  ),
  _McpCategory(
    id: 'smarthome',
    serverName: 'rain-smarthome',
    labelKey: 'mcp.smarthome',
    icon: Icons.home_outlined,
    prompt:
        'Quiero controlar mi smart home. Muéstrame los dispositivos disponibles.',
    setupPrompt:
        'Quiero configurar mi smart home. Usa la herramienta home_setup para ayudarme a conectar Home Assistant paso a paso.',
  ),
];

/// Horizontal scrollable bar of MCP integration chips.
///
/// Shows a status dot per chip (green = ok, amber = needs setup, grey = unknown).
/// On tap, sends the appropriate prompt (usage or setup) via [onSendPrompt].
class McpToolsBar extends StatefulWidget {
  final Dio dio;
  final String lang;
  final bool enabled;
  final void Function(String prompt) onSendPrompt;

  const McpToolsBar({
    super.key,
    required this.dio,
    required this.lang,
    required this.enabled,
    required this.onSendPrompt,
  });

  @override
  State<McpToolsBar> createState() => _McpToolsBarState();
}

class _McpToolsBarState extends State<McpToolsBar> {
  Map<String, McpServerInfo> _servers = {};
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _fetchStatus();
  }

  @override
  void didUpdateWidget(McpToolsBar old) {
    super.didUpdateWidget(old);
    // Re-fetch if dio instance changed (reconnection)
    if (old.dio != widget.dio) _fetchStatus();
  }

  Future<void> _fetchStatus() async {
    try {
      final res = await widget.dio.get('/mcp/status');
      if (!mounted) return;
      final data = res.data as Map<String, dynamic>? ?? {};
      final rawServers = data['servers'] as Map<String, dynamic>? ?? {};
      setState(() {
        _servers = rawServers.map(
          (k, v) => MapEntry(k, McpServerInfo.fromJson(v as Map<String, dynamic>)),
        );
        _loaded = true;
      });
    } catch (_) {
      if (mounted) setState(() => _loaded = true);
    }
  }

  String _statusForServer(String serverName) {
    final info = _servers[serverName];
    if (info == null) return 'unknown';
    return info.isOk ? 'ok' : 'error';
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: _categories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final cat = _categories[index];
          final status = _loaded ? _statusForServer(cat.serverName) : 'loading';
          final isOk = status == 'ok';
          final label = L10n.t(cat.labelKey, widget.lang);

          return ActionChip(
            avatar: Stack(
              clipBehavior: Clip.none,
              children: [
                Icon(cat.icon, size: 18),
                // Status dot
                if (_loaded)
                  Positioned(
                    right: -2,
                    top: -2,
                    child: Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isOk
                            ? Colors.green
                            : status == 'error'
                                ? Colors.amber
                                : cs.onSurfaceVariant.withValues(alpha: 0.3),
                        border: Border.all(
                          color: cs.surfaceContainer,
                          width: 1.5,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            label: Text(label, style: const TextStyle(fontSize: 13)),
            tooltip: !isOk && _loaded
                ? L10n.t('mcp.tapToSetup', widget.lang, {'label': label})
                : label,
            onPressed: widget.enabled
                ? () {
                    final prompt = isOk ? cat.prompt : cat.setupPrompt;
                    widget.onSendPrompt(prompt);
                  }
                : null,
            side: BorderSide(
              color: cs.outlineVariant.withValues(alpha: 0.4),
            ),
            backgroundColor: cs.surfaceContainer,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
          );
        },
      ),
    );
  }
}
