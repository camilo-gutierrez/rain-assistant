import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app/l10n.dart';
import '../services/call_service.dart';
import '../services/voice_mode_service.dart';

/// Premium full-screen call overlay with real-time audio visualization,
/// state transitions, duration timer, and controls.
class CallOverlay extends StatefulWidget {
  final CallService callService;
  final VoidCallback onEnd;
  final String lang;

  const CallOverlay({
    super.key,
    required this.callService,
    required this.onEnd,
    required this.lang,
  });

  @override
  State<CallOverlay> createState() => _CallOverlayState();
}

class _CallOverlayState extends State<CallOverlay>
    with TickerProviderStateMixin {
  late final AnimationController _pulseController;
  late final AnimationController _waveController;
  late final AnimationController _entryController;
  late final Animation<double> _entryFade;
  late final Animation<double> _entryScale;

  @override
  void initState() {
    super.initState();

    // Pulse animation for the central orb
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    // Wave animation for audio bars
    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);

    // Entry animation
    _entryController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );
    _entryFade = CurvedAnimation(
      parent: _entryController,
      curve: Curves.easeOut,
    );
    _entryScale = Tween<double>(begin: 0.8, end: 1.0).animate(
      CurvedAnimation(parent: _entryController, curve: Curves.easeOutBack),
    );
    _entryController.forward();

    // Lock to portrait during call
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _waveController.dispose();
    _entryController.dispose();
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    super.dispose();
  }

  Color _stateColor(VoiceState state, ColorScheme cs) {
    return switch (state) {
      VoiceState.listening || VoiceState.wakeListening => const Color(0xFF4CAF50),
      VoiceState.recording => const Color(0xFFE53935),
      VoiceState.transcribing => const Color(0xFFFFA726),
      VoiceState.processing => cs.primary,
      VoiceState.speaking => const Color(0xFF7C4DFF),
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
      VoiceState.idle => L10n.t('call.connecting', widget.lang),
    };
  }

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes.toString().padLeft(2, '0');
    final seconds = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final voiceService = widget.callService.voiceService;

    return FadeTransition(
      opacity: _entryFade,
      child: Material(
        color: Colors.black.withValues(alpha: 0.95),
        child: SafeArea(
          child: ValueListenableBuilder<VoiceState>(
            valueListenable: voiceService.voiceState,
            builder: (context, voiceState, _) {
              final color = _stateColor(voiceState, cs);
              final isRecordingOrSpeaking =
                  voiceState == VoiceState.recording ||
                  voiceState == VoiceState.speaking;

              return Column(
                children: [
                  // ── Top bar: duration & status ──
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 24, vertical: 16),
                    child: Row(
                      children: [
                        // Status dot
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: color,
                            boxShadow: [
                              BoxShadow(
                                color: color.withValues(alpha: 0.5),
                                blurRadius: 6,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 10),
                        // State label
                        Expanded(
                          child: AnimatedSwitcher(
                            duration: const Duration(milliseconds: 300),
                            child: Text(
                              _stateLabel(voiceState),
                              key: ValueKey(voiceState),
                              style: TextStyle(
                                fontSize: 14,
                                color: Colors.white.withValues(alpha: 0.7),
                                letterSpacing: 0.5,
                              ),
                            ),
                          ),
                        ),
                        // Duration
                        ValueListenableBuilder<Duration>(
                          valueListenable: widget.callService.duration,
                          builder: (context, dur, _) {
                            return Text(
                              _formatDuration(dur),
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: Colors.white.withValues(alpha: 0.9),
                                fontFamily: 'monospace',
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),

                  const Spacer(flex: 2),

                  // ── Central orb ──
                  ScaleTransition(
                    scale: _entryScale,
                    child: ValueListenableBuilder<double>(
                      valueListenable: widget.callService.audioLevel,
                      builder: (context, level, child) {
                        return AnimatedBuilder(
                          animation: _pulseController,
                          builder: (context, child) {
                            // Orb scale: breathing pulse + audio level boost
                            final breathing = isRecordingOrSpeaking
                                ? _pulseController.value * 0.08
                                : _pulseController.value * 0.04;
                            final audioBoost =
                                voiceState == VoiceState.recording
                                    ? level * 0.25
                                    : 0.0;
                            final scale = 1.0 + breathing + audioBoost;

                            return Transform.scale(
                              scale: scale,
                              child: child,
                            );
                          },
                          child: _buildOrb(voiceState, color, level),
                        );
                      },
                    ),
                  ),

                  const SizedBox(height: 32),

                  // ── "Rain" label ──
                  Text(
                    'Rain',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w300,
                      color: Colors.white.withValues(alpha: 0.95),
                      letterSpacing: 2,
                    ),
                  ),

                  const SizedBox(height: 8),

                  // ── State icon + label ──
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 300),
                    child: Row(
                      key: ValueKey(voiceState),
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _stateIcon(voiceState),
                          size: 18,
                          color: color,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _stateLabel(voiceState),
                          style: TextStyle(
                            fontSize: 15,
                            color: color,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // ── Audio visualizer bars (during recording) ──
                  SizedBox(
                    height: 48,
                    child: voiceState == VoiceState.recording
                        ? _AudioVisualizer(
                            controller: _waveController,
                            color: color,
                            audioLevel: widget.callService.audioLevel,
                          )
                        : voiceState == VoiceState.speaking
                            ? _SpeakingWave(
                                controller: _waveController,
                                color: color,
                              )
                            : const SizedBox.shrink(),
                  ),

                  const SizedBox(height: 16),

                  // ── Transcription display ──
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 32),
                    child: SizedBox(
                      height: 60,
                      child: _TranscriptionDisplay(
                        voiceService: voiceService,
                        voiceState: voiceState,
                      ),
                    ),
                  ),

                  const Spacer(flex: 3),

                  // ── Bottom controls ──
                  _buildControls(cs, voiceState),

                  const SizedBox(height: 48),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildOrb(VoiceState state, Color color, double level) {
    final size = 140.0;
    // Outer glow rings
    return SizedBox(
      width: size + 60,
      height: size + 60,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Outer glow ring 2
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, _) {
              final opacity = 0.08 + _pulseController.value * 0.06;
              final ringSize = size + 50 + _pulseController.value * 10;
              return Container(
                width: ringSize,
                height: ringSize,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: color.withValues(alpha: opacity),
                    width: 1.5,
                  ),
                ),
              );
            },
          ),
          // Outer glow ring 1
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, _) {
              final opacity = 0.12 + _pulseController.value * 0.08;
              final ringSize = size + 28 + _pulseController.value * 6;
              return Container(
                width: ringSize,
                height: ringSize,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: color.withValues(alpha: opacity),
                    width: 2,
                  ),
                ),
              );
            },
          ),
          // Main orb
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  color.withValues(alpha: 0.3),
                  color.withValues(alpha: 0.1),
                  Colors.transparent,
                ],
                stops: const [0.0, 0.6, 1.0],
              ),
              border: Border.all(color: color, width: 3),
              boxShadow: [
                BoxShadow(
                  color: color.withValues(alpha: 0.4),
                  blurRadius: 30,
                  spreadRadius: 5,
                ),
              ],
            ),
            child: Icon(
              _stateIcon(state),
              size: 52,
              color: Colors.white.withValues(alpha: 0.95),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControls(ColorScheme cs, VoiceState voiceState) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        // Mute button
        ValueListenableBuilder<bool>(
          valueListenable: widget.callService.isMuted,
          builder: (context, muted, _) {
            return _ControlButton(
              icon: muted ? Icons.mic_off : Icons.mic,
              label: L10n.t(muted ? 'call.unmute' : 'call.mute', widget.lang),
              color: muted ? Colors.red : Colors.white.withValues(alpha: 0.8),
              backgroundColor: muted
                  ? Colors.red.withValues(alpha: 0.2)
                  : Colors.white.withValues(alpha: 0.1),
              onTap: widget.callService.toggleMute,
            );
          },
        ),

        // End call button (large, red)
        GestureDetector(
          onTap: widget.onEnd,
          child: Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.red,
              boxShadow: [
                BoxShadow(
                  color: Colors.red.withValues(alpha: 0.4),
                  blurRadius: 16,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: const Icon(
              Icons.call_end,
              size: 32,
              color: Colors.white,
            ),
          ),
        ),

        // Speaker button (placeholder for future speaker toggle)
        _ControlButton(
          icon: Icons.volume_up,
          label: L10n.t('call.speaker', widget.lang),
          color: Colors.white.withValues(alpha: 0.8),
          backgroundColor: Colors.white.withValues(alpha: 0.1),
          onTap: () => HapticFeedback.selectionClick(),
        ),
      ],
    );
  }
}

/// Circular control button for the bottom bar.
class _ControlButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final Color backgroundColor;
  final VoidCallback onTap;

  const _ControlButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.backgroundColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: backgroundColor,
            ),
            child: Icon(icon, size: 26, color: color),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: Colors.white.withValues(alpha: 0.6),
            ),
          ),
        ],
      ),
    );
  }
}

/// Real-time audio visualizer that responds to microphone level.
class _AudioVisualizer extends StatelessWidget {
  final AnimationController controller;
  final Color color;
  final ValueNotifier<double> audioLevel;

  const _AudioVisualizer({
    required this.controller,
    required this.color,
    required this.audioLevel,
  });

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<double>(
      valueListenable: audioLevel,
      builder: (context, level, _) {
        return AnimatedBuilder(
          animation: controller,
          builder: (context, _) {
            return Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: List.generate(20, (i) {
                final phase = (i * 0.12 + controller.value) % 1.0;
                final waveHeight = math.sin(phase * math.pi);
                // Combine animation with real audio level
                final h = 6.0 + (36.0 * waveHeight * (0.3 + level * 0.7));
                return Container(
                  width: 3,
                  height: h.clamp(4.0, 42.0),
                  margin: const EdgeInsets.symmetric(horizontal: 1.5),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.6 + level * 0.4),
                    borderRadius: BorderRadius.circular(2),
                  ),
                );
              }),
            );
          },
        );
      },
    );
  }
}

/// Gentle wave animation during TTS playback.
class _SpeakingWave extends StatelessWidget {
  final AnimationController controller;
  final Color color;

  const _SpeakingWave({required this.controller, required this.color});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: List.generate(16, (i) {
            final phase = (i * 0.18 + controller.value * 2) % 1.0;
            final h = 8.0 + 24.0 * math.sin(phase * math.pi);
            return Container(
              width: 3,
              height: h,
              margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(2),
              ),
            );
          }),
        );
      },
    );
  }
}

/// Displays partial and final transcription text.
class _TranscriptionDisplay extends StatelessWidget {
  final VoiceModeService voiceService;
  final VoiceState voiceState;

  const _TranscriptionDisplay({
    required this.voiceService,
    required this.voiceState,
  });

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: voiceService.partialTranscription,
      builder: (context, partial, _) {
        if (partial.isNotEmpty) {
          return _buildText(partial, isPartial: true);
        }
        return ValueListenableBuilder<String>(
          valueListenable: voiceService.lastTranscription,
          builder: (context, last, _) {
            if (last.isNotEmpty &&
                (voiceState == VoiceState.processing ||
                    voiceState == VoiceState.transcribing)) {
              return _buildText(last, isPartial: false);
            }
            return const SizedBox.shrink();
          },
        );
      },
    );
  }

  Widget _buildText(String text, {required bool isPartial}) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: Text(
        '\u201c$text\u201d',
        key: ValueKey(text),
        textAlign: TextAlign.center,
        maxLines: 3,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          fontSize: 15,
          fontStyle: FontStyle.italic,
          color: Colors.white.withValues(alpha: isPartial ? 0.5 : 0.7),
          height: 1.4,
        ),
      ),
    );
  }
}
