import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../providers/agent_provider.dart';
import '../providers/connection_provider.dart';
import 'screenshot_fullscreen.dart';

/// Persistent live display panel showing the last screenshot when in
/// computer_use mode. Sits above the message list and includes display
/// info (resolution, iteration), multi-monitor selector, interactive
/// click hints, pinch-to-zoom, and screenshot diff overlay.
class ComputerLiveDisplay extends ConsumerStatefulWidget {
  final String lang;
  const ComputerLiveDisplay({super.key, required this.lang});

  @override
  ConsumerState<ComputerLiveDisplay> createState() =>
      _ComputerLiveDisplayState();
}

class _ComputerLiveDisplayState extends ConsumerState<ComputerLiveDisplay> {
  final _imageKey = GlobalKey();
  final _transformController = TransformationController();
  Offset? _tapMarker;
  Timer? _tapTimer;
  bool _showDiff = false;

  @override
  void dispose() {
    _tapTimer?.cancel();
    _transformController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final agent = ref.watch(agentProvider).activeAgent;
    if (agent == null || agent.mode != AgentMode.computerUse) {
      return const SizedBox.shrink();
    }

    final lang = widget.lang;
    final hasScreenshot =
        agent.lastScreenshot != null && agent.lastScreenshot!.isNotEmpty;
    final hasPrevious =
        agent.previousScreenshot != null && agent.previousScreenshot!.isNotEmpty;
    final displayInfo = agent.displayInfo;

    return Container(
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(
          bottom: BorderSide(
            color: cs.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // ── Info bar ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Row(
              children: [
                Icon(Icons.monitor, size: 16, color: cs.primary),
                const SizedBox(width: 6),
                Text(
                  L10n.t('cu.liveDisplay', lang),
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: cs.onSurface,
                  ),
                ),
                // ── Multi-monitor selector ──
                if (displayInfo != null && displayInfo.monitorCount > 1) ...[
                  const SizedBox(width: 8),
                  _MonitorSelector(
                    displayInfo: displayInfo,
                    lang: lang,
                    cs: cs,
                    onChanged: (index) {
                      ref.read(webSocketServiceProvider).send({
                        'type': 'set_monitor',
                        'agent_id': agent.id,
                        'monitor_index': index,
                      });
                    },
                  ),
                ],
                const Spacer(),
                // ── Diff toggle ──
                if (hasPrevious)
                  _ToggleChip(
                    icon: Icons.difference,
                    active: _showDiff,
                    cs: cs,
                    onTap: () => setState(() => _showDiff = !_showDiff),
                  ),
                if (hasPrevious) const SizedBox(width: 8),
                if (displayInfo != null) ...[
                  _InfoChip(
                    icon: Icons.aspect_ratio,
                    label:
                        '${displayInfo.screenWidth}x${displayInfo.screenHeight}',
                    cs: cs,
                  ),
                  const SizedBox(width: 8),
                ],
                _InfoChip(
                  icon: Icons.repeat,
                  label: L10n.t('cu.iterationProgress', lang,
                      {'current': '${agent.computerIteration}'}),
                  cs: cs,
                ),
              ],
            ),
          ),
          // ── Screenshot preview ──
          if (hasScreenshot)
            GestureDetector(
              onTapDown: (details) => _handleTap(details, agent),
              onDoubleTap: () {
                // Double-tap resets zoom if zoomed, otherwise no-op
                _transformController.value = Matrix4.identity();
              },
              onLongPress: () => ScreenshotFullscreen.show(
                context,
                agent.lastScreenshot!,
                title: L10n.t('cu.liveDisplay', lang),
              ),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 220),
                child: Stack(
                  alignment: Alignment.bottomRight,
                  children: [
                    // Main screenshot with zoom
                    ClipRect(
                      child: InteractiveViewer(
                        transformationController: _transformController,
                        minScale: 1.0,
                        maxScale: 3.0,
                        child: Image.memory(
                          key: _imageKey,
                          base64Decode(agent.lastScreenshot!),
                          fit: BoxFit.contain,
                          width: double.infinity,
                          errorBuilder: (_, __, ___) => SizedBox(
                            height: 100,
                            child: Center(
                              child: Icon(Icons.broken_image,
                                  size: 32, color: cs.onSurfaceVariant),
                            ),
                          ),
                        ),
                      ),
                    ),
                    // ── Diff overlay ──
                    if (_showDiff && hasPrevious)
                      Positioned.fill(
                        child: IgnorePointer(
                          child: Opacity(
                            opacity: 0.7,
                            child: Image.memory(
                              base64Decode(agent.previousScreenshot!),
                              fit: BoxFit.contain,
                              width: double.infinity,
                              colorBlendMode: BlendMode.difference,
                              color: Colors.white,
                              errorBuilder: (_, __, ___) =>
                                  const SizedBox.shrink(),
                            ),
                          ),
                        ),
                      ),
                    // ── Tap crosshair marker ──
                    if (_tapMarker != null)
                      Positioned(
                        left: _tapMarker!.dx - 12,
                        top: _tapMarker!.dy - 12,
                        child: IgnorePointer(
                          child: Container(
                            width: 24,
                            height: 24,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: cs.primary, width: 2),
                            ),
                            child: Center(
                              child: Container(
                                width: 4,
                                height: 4,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: cs.primary,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    // Expand hint
                    Container(
                      margin: const EdgeInsets.all(8),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black54,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.fullscreen,
                              size: 14, color: Colors.white70),
                          const SizedBox(width: 4),
                          Text(
                            L10n.t('cu.longPressExpand', lang),
                            style: const TextStyle(
                              fontSize: 10,
                              color: Colors.white70,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                L10n.t('cu.noScreenshot', lang),
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
              ),
            ),
        ],
      ),
    );
  }

  /// Handle a tap on the screenshot: calculate screen coordinates and send hint.
  void _handleTap(TapDownDetails details, Agent agent) {
    final displayInfo = agent.displayInfo;
    if (displayInfo == null) return;

    final renderBox =
        _imageKey.currentContext?.findRenderObject() as RenderBox?;
    if (renderBox == null) return;

    // Account for InteractiveViewer transform
    final matrix = _transformController.value;
    final inverted = Matrix4.inverted(matrix);
    final globalPos = details.globalPosition;
    final localPos = renderBox.globalToLocal(globalPos);
    final transformed = MatrixUtils.transformPoint(
      inverted,
      localPos,
    );

    final imageSize = renderBox.size;
    if (imageSize.width == 0 || imageSize.height == 0) return;

    final screenX =
        (transformed.dx / imageSize.width * displayInfo.screenWidth).round();
    final screenY =
        (transformed.dy / imageSize.height * displayInfo.screenHeight).round();

    // Clamp to valid range
    final clampedX = screenX.clamp(0, displayInfo.screenWidth);
    final clampedY = screenY.clamp(0, displayInfo.screenHeight);

    // Send hint to backend
    ref.read(webSocketServiceProvider).send({
      'type': 'computer_use_hint',
      'agent_id': agent.id,
      'text': 'Click at position ($clampedX, $clampedY)',
      'x': clampedX,
      'y': clampedY,
    });

    // Show crosshair at tap position (in widget-local coords)
    final stackBox = context.findRenderObject() as RenderBox?;
    if (stackBox != null) {
      final stackLocal = stackBox.globalToLocal(globalPos);
      setState(() => _tapMarker = stackLocal);
      _tapTimer?.cancel();
      _tapTimer = Timer(const Duration(seconds: 2), () {
        if (mounted) setState(() => _tapMarker = null);
      });
    }
  }
}

/// Dropdown to select which monitor to use for computer use.
class _MonitorSelector extends StatelessWidget {
  final DisplayInfo displayInfo;
  final String lang;
  final ColorScheme cs;
  final ValueChanged<int> onChanged;

  const _MonitorSelector({
    required this.displayInfo,
    required this.lang,
    required this.cs,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: cs.primaryContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<int>(
          value: displayInfo.monitorIndex,
          isDense: true,
          style: TextStyle(
            fontSize: 11,
            color: cs.onPrimaryContainer,
            fontFamily: 'monospace',
          ),
          dropdownColor: cs.surfaceContainer,
          items: List.generate(displayInfo.monitorCount, (i) {
            final index = i + 1; // monitors are 1-based
            return DropdownMenuItem(
              value: index,
              child: Text(L10n.t('cu.monitor', lang, {'n': '$index'})),
            );
          }),
          onChanged: (v) {
            if (v != null && v != displayInfo.monitorIndex) onChanged(v);
          },
        ),
      ),
    );
  }
}

/// Toggle chip button (e.g. for diff mode).
class _ToggleChip extends StatelessWidget {
  final IconData icon;
  final bool active;
  final ColorScheme cs;
  final VoidCallback onTap;

  const _ToggleChip({
    required this.icon,
    required this.active,
    required this.cs,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: active
              ? cs.primary.withValues(alpha: 0.2)
              : cs.primaryContainer.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(10),
          border: active ? Border.all(color: cs.primary, width: 1) : null,
        ),
        child: Icon(icon, size: 14,
            color: active ? cs.primary : cs.onPrimaryContainer),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final ColorScheme cs;

  const _InfoChip({
    required this.icon,
    required this.label,
    required this.cs,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: cs.primaryContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: cs.onPrimaryContainer),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: cs.onPrimaryContainer,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }
}
