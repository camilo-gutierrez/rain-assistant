import 'package:flutter/material.dart';
import '../app/l10n.dart';

class ChatInputBar extends StatelessWidget {
  final TextEditingController controller;
  final bool isProcessing;
  final bool isRecording;
  final bool isTranscribing;
  final VoidCallback onSend;
  final VoidCallback onToggleRecording;
  final String lang;
  final String voiceMode;
  final bool talkModeActive;
  final VoidCallback? onToggleTalkMode;
  final String? voiceStateLabel;

  const ChatInputBar({
    super.key,
    required this.controller,
    required this.isProcessing,
    required this.isRecording,
    this.isTranscribing = false,
    required this.onSend,
    required this.onToggleRecording,
    required this.lang,
    this.voiceMode = 'push-to-talk',
    this.talkModeActive = false,
    this.onToggleTalkMode,
    this.voiceStateLabel,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Container(
      padding: EdgeInsets.fromLTRB(
          8, 8, 8, MediaQuery.of(context).padding.bottom + 8),
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(
            top: BorderSide(
                color: cs.outlineVariant.withValues(alpha: 0.3))),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Voice state indicator (shown when voice mode is active)
          if (voiceStateLabel != null && voiceStateLabel!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(
                  color: cs.primaryContainer.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 8,
                      height: 8,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          color: Colors.green,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      voiceStateLabel!,
                      style: TextStyle(
                        fontSize: 12,
                        color: cs.onPrimaryContainer,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          Row(
            children: [
              // Mic button
              isTranscribing
                  ? Padding(
                      padding: const EdgeInsets.all(12),
                      child: SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: cs.primary,
                        ),
                      ),
                    )
                  : IconButton(
                      onPressed: isProcessing ? null : onToggleRecording,
                      icon: isRecording
                          ? Icon(Icons.stop, color: cs.error)
                          : const Icon(Icons.mic_none),
                      style: isRecording
                          ? IconButton.styleFrom(
                              backgroundColor:
                                  cs.errorContainer.withValues(alpha: 0.3),
                            )
                          : null,
                    ),
              // Talk Mode button (only shown for non-push-to-talk modes)
              if (voiceMode != 'push-to-talk' && onToggleTalkMode != null)
                IconButton(
                  onPressed: onToggleTalkMode,
                  icon: Icon(
                    talkModeActive ? Icons.phone_disabled : Icons.phone_in_talk,
                    color: talkModeActive ? cs.error : cs.primary,
                  ),
                  style: talkModeActive
                      ? IconButton.styleFrom(
                          backgroundColor:
                              cs.errorContainer.withValues(alpha: 0.3),
                        )
                      : null,
                  tooltip: talkModeActive
                      ? L10n.t('voice.endConversation', lang)
                      : L10n.t('voice.startTalkMode', lang),
                ),
              const SizedBox(width: 4),
              // Text field
              Expanded(
                child: TextField(
                  controller: controller,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => onSend(),
                  maxLines: 4,
                  minLines: 1,
                  enabled: !isRecording && !isTranscribing,
                  decoration: InputDecoration(
                    hintText: isRecording
                        ? L10n.t('chat.recording', lang)
                        : isTranscribing
                            ? L10n.t('chat.transcribing', lang)
                            : L10n.t('chat.inputPlaceholder', lang),
                    filled: true,
                    fillColor: cs.surface,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 20, vertical: 12),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Send button
              IconButton.filled(
                onPressed: isProcessing ? null : onSend,
                icon: isProcessing
                    ? SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: cs.onPrimary,
                        ),
                      )
                    : const Icon(Icons.send),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
