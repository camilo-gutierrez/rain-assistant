import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../app/l10n.dart';
import '../services/voice_mode_service.dart';

/// Full-screen overlay for Talk Mode (continuous voice conversation).
class TalkModeOverlay extends StatefulWidget {
  final VoiceModeService voiceService;
  final VoidCallback onEnd;
  final String lang;

  const TalkModeOverlay({
    super.key,
    required this.voiceService,
    required this.onEnd,
    required this.lang,
  });

  @override
  State<TalkModeOverlay> createState() => _TalkModeOverlayState();
}

class _TalkModeOverlayState extends State<TalkModeOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Color _stateColor(VoiceState state, ColorScheme cs) {
    return switch (state) {
      VoiceState.listening || VoiceState.wakeListening => Colors.green,
      VoiceState.recording => cs.error,
      VoiceState.transcribing => Colors.orange,
      VoiceState.processing => cs.tertiary,
      VoiceState.speaking => cs.primary,
      VoiceState.idle => cs.onSurfaceVariant,
    };
  }

  IconData _stateIcon(VoiceState state) {
    return switch (state) {
      VoiceState.listening || VoiceState.wakeListening => Icons.hearing,
      VoiceState.recording => Icons.mic,
      VoiceState.transcribing => Icons.text_fields,
      VoiceState.processing => Icons.psychology,
      VoiceState.speaking => Icons.volume_up,
      VoiceState.idle => Icons.mic_none,
    };
  }

  String _stateLabel(VoiceState state) {
    return switch (state) {
      VoiceState.listening => L10n.t('voice.listening', widget.lang),
      VoiceState.wakeListening => L10n.t('voice.wakeListening', widget.lang),
      VoiceState.recording => L10n.t('voice.recording', widget.lang),
      VoiceState.transcribing => L10n.t('voice.transcribing', widget.lang),
      VoiceState.processing => L10n.t('voice.processing', widget.lang),
      VoiceState.speaking => L10n.t('voice.speaking', widget.lang),
      VoiceState.idle => '',
    };
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Material(
      color: cs.surface.withValues(alpha: 0.97),
      child: SafeArea(
        child: ValueListenableBuilder<VoiceState>(
          valueListenable: widget.voiceService.voiceState,
          builder: (context, voiceState, _) {
            final color = _stateColor(voiceState, cs);
            final isActive =
                voiceState == VoiceState.recording || voiceState == VoiceState.speaking;

            return Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Spacer(flex: 2),

                // Central orb with pulse
                AnimatedBuilder(
                  animation: _pulseController,
                  builder: (context, child) {
                    final scale = isActive
                        ? 1.0 + _pulseController.value * 0.15
                        : 1.0;
                    return Transform.scale(
                      scale: scale,
                      child: child,
                    );
                  },
                  child: Container(
                    width: 120,
                    height: 120,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: color, width: 4),
                      boxShadow: [
                        BoxShadow(
                          color: color.withValues(alpha: 0.3),
                          blurRadius: 24,
                          spreadRadius: 4,
                        ),
                      ],
                    ),
                    child: Icon(
                      _stateIcon(voiceState),
                      size: 48,
                      color: color,
                    ),
                  ),
                ),

                const SizedBox(height: 24),

                // State label
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 300),
                  child: Text(
                    _stateLabel(voiceState),
                    key: ValueKey(voiceState),
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w500,
                      color: cs.onSurface,
                    ),
                  ),
                ),

                const SizedBox(height: 16),

                // Partial transcription
                ValueListenableBuilder<String>(
                  valueListenable: widget.voiceService.partialTranscription,
                  builder: (context, partial, _) {
                    if (partial.isEmpty) {
                      return ValueListenableBuilder<String>(
                        valueListenable: widget.voiceService.lastTranscription,
                        builder: (context, last, _) {
                          if (last.isEmpty ||
                              voiceState != VoiceState.processing) {
                            return const SizedBox(height: 20);
                          }
                          return Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 32),
                            child: Text(
                              '\u201c$last\u201d',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 14,
                                fontStyle: FontStyle.italic,
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          );
                        },
                      );
                    }
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 32),
                      child: Text(
                        '\u201c$partial\u201d',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 14,
                          fontStyle: FontStyle.italic,
                          color: cs.onSurfaceVariant,
                        ),
                      ),
                    );
                  },
                ),

                const SizedBox(height: 16),

                // Audio wave during recording
                if (voiceState == VoiceState.recording) _AudioWave(color: color),

                const Spacer(flex: 3),

                // End button
                FilledButton.tonalIcon(
                  onPressed: widget.onEnd,
                  icon: const Icon(Icons.phone_disabled),
                  label: Text(L10n.t('voice.endConversation', widget.lang)),
                  style: FilledButton.styleFrom(
                    backgroundColor: cs.errorContainer,
                    foregroundColor: cs.onErrorContainer,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 24, vertical: 14),
                  ),
                ),

                const SizedBox(height: 48),
              ],
            );
          },
        ),
      ),
    );
  }
}

/// Animated audio wave bars.
class _AudioWave extends StatefulWidget {
  final Color color;
  const _AudioWave({required this.color});

  @override
  State<_AudioWave> createState() => _AudioWaveState();
}

class _AudioWaveState extends State<_AudioWave>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 32,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(12, (i) {
              final phase = (i * 0.15 + _controller.value) % 1.0;
              final height = 8.0 + 20.0 * math.sin(phase * math.pi);
              return Container(
                width: 3,
                height: height,
                margin: const EdgeInsets.symmetric(horizontal: 1.5),
                decoration: BoxDecoration(
                  color: widget.color.withValues(alpha: 0.7),
                  borderRadius: BorderRadius.circular(2),
                ),
              );
            }),
          );
        },
      ),
    );
  }
}
