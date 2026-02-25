import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import '../app/l10n.dart';
import '../models/message.dart';

/// Callback that receives the selected images alongside the send action.
typedef OnSendWithImages = void Function(List<ImageAttachment> images);

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
  // Image support
  final List<ImageAttachment> pendingImages;
  final VoidCallback? onPickImage;
  final VoidCallback? onTakePhoto;
  final void Function(int index)? onRemoveImage;

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
    this.pendingImages = const [],
    this.onPickImage,
    this.onTakePhoto,
    this.onRemoveImage,
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

          // Image preview strip
          if (pendingImages.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: SizedBox(
                height: 68,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: pendingImages.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, index) {
                    final img = pendingImages[index];
                    return Stack(
                      clipBehavior: Clip.none,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: Image.memory(
                            base64Decode(img.base64),
                            width: 64,
                            height: 64,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              width: 64,
                              height: 64,
                              color: cs.surfaceContainerHighest,
                              child: const Icon(Icons.broken_image, size: 24),
                            ),
                          ),
                        ),
                        Positioned(
                          top: -4,
                          right: -4,
                          child: GestureDetector(
                            onTap: () => onRemoveImage?.call(index),
                            child: Container(
                              width: 20,
                              height: 20,
                              decoration: BoxDecoration(
                                color: cs.error,
                                shape: BoxShape.circle,
                              ),
                              child: Icon(
                                Icons.close,
                                size: 12,
                                color: cs.onError,
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),

          Row(
            children: [
              // Image attachment button (gallery + camera popup)
              PopupMenuButton<String>(
                enabled: !isProcessing && !isRecording && !isTranscribing,
                onSelected: (value) {
                  if (value == 'gallery') {
                    onPickImage?.call();
                  } else if (value == 'camera') {
                    onTakePhoto?.call();
                  }
                },
                icon: Icon(
                  Icons.add_photo_alternate_outlined,
                  color: isProcessing ? cs.onSurfaceVariant.withValues(alpha: 0.3) : cs.primary,
                ),
                padding: EdgeInsets.zero,
                itemBuilder: (ctx) => [
                  PopupMenuItem(
                    value: 'gallery',
                    child: Row(
                      children: [
                        const Icon(Icons.photo_library_outlined, size: 20),
                        const SizedBox(width: 12),
                        Text(L10n.t('chat.gallery', lang)),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'camera',
                    child: Row(
                      children: [
                        const Icon(Icons.camera_alt_outlined, size: 20),
                        const SizedBox(width: 12),
                        Text(L10n.t('chat.camera', lang)),
                      ],
                    ),
                  ),
                ],
              ),

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
