import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../models/message.dart';
import 'a2ui_surface.dart';
import '../providers/agent_provider.dart';
import '../providers/audio_provider.dart';
import '../services/audio_service.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import 'computer_action_block.dart';
import 'computer_screenshot.dart';

// ── Message tile (pattern match on sealed Message) ──

class MessageTile extends ConsumerWidget {
  final Message message;
  const MessageTile({super.key, required this.message});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(settingsProvider).language;
    return switch (message) {
      UserMessage(:final text, :final images) =>
        UserBubble(text: text, images: images),
      AssistantMessage(:final text, :final isStreaming) =>
        AssistantBubble(text: text, isStreaming: isStreaming),
      SystemMessage(:final text) => SystemLine(text: text),
      ToolUseMessage() => ToolUseBlock(message: message as ToolUseMessage),
      ToolResultMessage() =>
        ToolResultBlock(message: message as ToolResultMessage),
      PermissionRequestMessage() =>
        PermissionBlock(message: message as PermissionRequestMessage),
      ComputerScreenshotMessage() => ComputerScreenshotBlock(
          message: message as ComputerScreenshotMessage, lang: lang),
      ComputerActionMessage() => ComputerActionBlock(
          message: message as ComputerActionMessage, lang: lang),
      SubAgentMessage() =>
        _SubAgentBubble(message: message as SubAgentMessage, lang: lang),
      A2UISurfaceMessage() =>
        A2UISurfaceWidget(surface: (message as A2UISurfaceMessage).surface),
    };
  }
}

// ── User bubble ──

class UserBubble extends StatelessWidget {
  final String text;
  final List<ImageAttachment>? images;
  const UserBubble({super.key, required this.text, this.images});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final hasImages = images != null && images!.isNotEmpty;

    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        constraints:
            BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: cs.primaryContainer,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Image gallery
            if (hasImages) ...[
              if (images!.length == 1)
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: Image.memory(
                    base64Decode(images!.first.base64),
                    fit: BoxFit.cover,
                    width: double.infinity,
                    errorBuilder: (_, __, ___) => const Icon(Icons.broken_image),
                  ),
                )
              else
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 6,
                  crossAxisSpacing: 6,
                  children: images!.map((img) {
                    return ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.memory(
                        base64Decode(img.base64),
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) =>
                            const Icon(Icons.broken_image),
                      ),
                    );
                  }).toList(),
                ),
              if (text.isNotEmpty) const SizedBox(height: 8),
            ],
            if (text.isNotEmpty)
              SelectableText(
                text,
                style: TextStyle(color: cs.onPrimaryContainer, fontSize: 15),
              ),
          ],
        ),
      ),
    );
  }
}

// ── Assistant bubble with markdown + TTS play button ──

class AssistantBubble extends ConsumerWidget {
  final String text;
  final bool isStreaming;
  const AssistantBubble(
      {super.key, required this.text, required this.isStreaming});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final displayText = isStreaming ? '$text ▍' : text;
    final settings = ref.watch(settingsProvider);
    final showTtsButton =
        settings.ttsEnabled && !isStreaming && text.isNotEmpty;

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            MarkdownBody(
              data: displayText,
              selectable: true,
              builders: {
                'code': _CodeBlockBuilder(context),
              },
              styleSheet: MarkdownStyleSheet(
                p: TextStyle(color: cs.onSurface, fontSize: 15, height: 1.5),
                code: TextStyle(
                  color: cs.onSurface,
                  backgroundColor: cs.surfaceContainer,
                  fontSize: 13,
                  fontFamily: 'monospace',
                ),
                codeblockDecoration: const BoxDecoration(),
                codeblockPadding: EdgeInsets.zero,
                blockquoteDecoration: BoxDecoration(
                  border: Border(
                    left: BorderSide(color: cs.primary, width: 3),
                  ),
                ),
                blockquotePadding: const EdgeInsets.only(left: 12),
                h1: TextStyle(
                    color: cs.onSurface,
                    fontSize: 22,
                    fontWeight: FontWeight.bold),
                h2: TextStyle(
                    color: cs.onSurface,
                    fontSize: 19,
                    fontWeight: FontWeight.bold),
                h3: TextStyle(
                    color: cs.onSurface,
                    fontSize: 17,
                    fontWeight: FontWeight.w600),
                listBullet: TextStyle(color: cs.onSurface, fontSize: 15),
                a: TextStyle(color: cs.primary),
                strong:
                    TextStyle(color: cs.onSurface, fontWeight: FontWeight.bold),
                em: TextStyle(
                    color: cs.onSurface, fontStyle: FontStyle.italic),
              ),
            ),
            if (showTtsButton || (!isStreaming && text.isNotEmpty))
              Align(
                alignment: Alignment.centerRight,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (!isStreaming && text.isNotEmpty)
                      _CopyButton(text: text),
                    if (showTtsButton)
                      TtsPlayButton(text: text),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Small play/stop button for TTS on individual messages.
class TtsPlayButton extends ConsumerStatefulWidget {
  final String text;
  const TtsPlayButton({super.key, required this.text});

  @override
  ConsumerState<TtsPlayButton> createState() => _TtsPlayButtonState();
}

class _TtsPlayButtonState extends ConsumerState<TtsPlayButton> {
  bool _isThisPlaying = false;

  void _onPlaybackChanged() {
    if (!mounted) return;
    final state = ref.read(audioServiceProvider).playbackState.value;
    setState(() {
      if (state != TtsPlaybackState.playing &&
          state != TtsPlaybackState.loading) {
        _isThisPlaying = false;
      }
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref
          .read(audioServiceProvider)
          .playbackState
          .addListener(_onPlaybackChanged);
    });
  }

  @override
  void dispose() {
    ref
        .read(audioServiceProvider)
        .playbackState
        .removeListener(_onPlaybackChanged);
    super.dispose();
  }

  Future<void> _togglePlay() async {
    final audioService = ref.read(audioServiceProvider);
    final settings = ref.read(settingsProvider);

    if (_isThisPlaying) {
      await audioService.stop();
      setState(() => _isThisPlaying = false);
    } else {
      setState(() => _isThisPlaying = true);
      await audioService.synthesize(widget.text, settings.ttsVoice);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final audioService = ref.watch(audioServiceProvider);

    return ValueListenableBuilder<TtsPlaybackState>(
      valueListenable: audioService.playbackState,
      builder: (context, playbackState, _) {
        final isLoading =
            _isThisPlaying && playbackState == TtsPlaybackState.loading;
        final isPlaying =
            _isThisPlaying && playbackState == TtsPlaybackState.playing;

        return SizedBox(
          width: 32,
          height: 32,
          child: IconButton(
            onPressed: isLoading ? null : _togglePlay,
            padding: EdgeInsets.zero,
            visualDensity: VisualDensity.compact,
            icon: isLoading
                ? SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: cs.primary,
                    ),
                  )
                : Icon(
                    isPlaying
                        ? Icons.stop_circle_outlined
                        : Icons.volume_up_outlined,
                    size: 18,
                    color: isPlaying ? cs.primary : cs.onSurfaceVariant,
                  ),
            tooltip: isPlaying ? 'Stop' : 'Play',
          ),
        );
      },
    );
  }
}

// ── Copy button (reused for message-level and code-block-level copy) ──

class _CopyButton extends StatelessWidget {
  final String text;
  const _CopyButton({required this.text});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return SizedBox(
      width: 32,
      height: 32,
      child: IconButton(
        onPressed: () {
          Clipboard.setData(ClipboardData(text: text));
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Copied!'),
              duration: Duration(seconds: 1),
              behavior: SnackBarBehavior.floating,
            ),
          );
        },
        padding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
        icon: Icon(Icons.content_copy, size: 16, color: cs.onSurfaceVariant),
        tooltip: 'Copy',
      ),
    );
  }
}

// ── Code block builder for fenced code blocks with header + copy button ──

class _CodeBlockBuilder extends MarkdownElementBuilder {
  final BuildContext _context;

  _CodeBlockBuilder(this._context);

  @override
  Widget? visitElementAfter(element, TextStyle? preferredStyle) {
    // Inline code: element has no children that are themselves elements,
    // and its textContent is short / has no newlines typically.
    // For fenced blocks, the element is inside a <pre> tag.
    // We detect fenced blocks by checking if the parent tag is 'pre'.
    final isBlock = element.attributes.containsKey('class') ||
        (element.textContent.contains('\n'));

    if (!isBlock) {
      // Inline code: return null to let flutter_markdown use default styling
      return null;
    }

    final cs = Theme.of(_context).colorScheme;

    // Extract language from class attribute (e.g. "language-dart")
    String? language;
    final cls = element.attributes['class'];
    if (cls != null && cls.startsWith('language-')) {
      language = cls.substring('language-'.length);
    }

    final codeText = element.textContent.trimRight();

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header bar with language label and copy button
          Container(
            padding: const EdgeInsets.only(left: 12, right: 4, top: 2, bottom: 2),
            decoration: BoxDecoration(
              color: cs.surfaceContainerHighest,
            ),
            child: Row(
              children: [
                if (language != null)
                  Text(
                    language,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: cs.onSurfaceVariant,
                      fontFamily: 'monospace',
                    ),
                  ),
                const Spacer(),
                SizedBox(
                  width: 28,
                  height: 28,
                  child: IconButton(
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: codeText));
                      ScaffoldMessenger.of(_context).showSnackBar(
                        const SnackBar(
                          content: Text('Copied!'),
                          duration: Duration(seconds: 1),
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    },
                    padding: EdgeInsets.zero,
                    visualDensity: VisualDensity.compact,
                    icon: Icon(Icons.content_copy, size: 14, color: cs.onSurfaceVariant),
                    tooltip: 'Copy code',
                  ),
                ),
              ],
            ),
          ),
          // Code content
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: SelectableText(
                codeText,
                style: TextStyle(
                  fontSize: 13,
                  fontFamily: 'monospace',
                  color: cs.onSurface,
                  height: 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── System message line ──

class SystemLine extends StatelessWidget {
  final String text;
  const SystemLine({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: cs.surfaceContainerHigh.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            text,
            style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
          ),
        ),
      ),
    );
  }
}

// ── Expandable tool_use block ──

class ToolUseBlock extends StatelessWidget {
  final ToolUseMessage message;
  const ToolUseBlock({super.key, required this.message});

  IconData _toolIcon(String tool) {
    return switch (tool) {
      'bash' || 'execute' => Icons.terminal,
      'write' || 'create_file' => Icons.edit_note,
      'read' || 'read_file' => Icons.description_outlined,
      'search' || 'grep' || 'find' => Icons.search,
      'browser' || 'web' => Icons.language,
      _ => Icons.build_outlined,
    };
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final inputJson =
        const JsonEncoder.withIndent('  ').convert(message.input);

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
          border:
              Border.all(color: cs.outlineVariant.withValues(alpha: 0.3)),
        ),
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          dense: true,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading:
              Icon(_toolIcon(message.tool), size: 18, color: cs.primary),
          title: Text(
            message.tool,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: cs.onSurface,
            ),
          ),
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: cs.surfaceContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                inputJson,
                style: TextStyle(
                  fontSize: 12,
                  fontFamily: 'monospace',
                  color: cs.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Expandable tool_result block ──

class ToolResultBlock extends StatelessWidget {
  final ToolResultMessage message;
  const ToolResultBlock({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isError = message.isError;
    final preview = message.content.length > 80
        ? '${message.content.substring(0, 80)}...'
        : message.content;

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 3),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: isError
              ? cs.errorContainer.withValues(alpha: 0.3)
              : cs.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isError
                ? cs.error.withValues(alpha: 0.3)
                : cs.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          dense: true,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading: Icon(
            isError ? Icons.error_outline : Icons.check_circle_outline,
            size: 18,
            color: isError ? cs.error : Colors.green,
          ),
          title: Text(
            isError ? 'Error' : preview,
            style: TextStyle(
              fontSize: 12,
              color: isError ? cs.error : cs.onSurfaceVariant,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          children: [
            Container(
              width: double.infinity,
              constraints: const BoxConstraints(maxHeight: 300),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: cs.surfaceContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SingleChildScrollView(
                child: SelectableText(
                  message.content,
                  style: TextStyle(
                    fontSize: 12,
                    fontFamily: 'monospace',
                    color: isError ? cs.error : cs.onSurfaceVariant,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Permission request block with PIN input + countdown ──

class PermissionBlock extends ConsumerStatefulWidget {
  final PermissionRequestMessage message;
  const PermissionBlock({super.key, required this.message});

  @override
  ConsumerState<PermissionBlock> createState() => _PermissionBlockState();
}

class _PermissionBlockState extends ConsumerState<PermissionBlock> {
  final _pinController = TextEditingController();
  Timer? _countdownTimer;
  int _remainingSeconds = 0;

  @override
  void initState() {
    super.initState();
    if (widget.message.status == PermissionStatus.pending) {
      _startCountdown();
    }
  }

  void _startCountdown() {
    const timeoutMs = 5 * 60 * 1000;
    final elapsed =
        DateTime.now().millisecondsSinceEpoch - widget.message.timestamp;
    final remaining = timeoutMs - elapsed;

    if (remaining <= 0) {
      _remainingSeconds = 0;
      _expire();
      return;
    }

    _remainingSeconds = (remaining / 1000).ceil();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) {
        _countdownTimer?.cancel();
        return;
      }
      setState(() {
        _remainingSeconds--;
        if (_remainingSeconds <= 0) {
          _countdownTimer?.cancel();
          _expire();
        }
      });
    });
  }

  void _expire() {
    final agentId = ref.read(agentProvider).activeAgentId;
    ref.read(agentProvider.notifier).updatePermissionStatus(
          agentId,
          widget.message.requestId,
          PermissionStatus.expired,
        );
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _pinController.dispose();
    super.dispose();
  }

  String _formatTime(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '$m:${s.toString().padLeft(2, '0')}';
  }

  void _respond(bool approved) {
    _countdownTimer?.cancel();
    final agentId = ref.read(agentProvider).activeAgentId;

    final ws = ref.read(webSocketServiceProvider);
    final payload = <String, dynamic>{
      'type': 'permission_response',
      'request_id': widget.message.requestId,
      'agent_id': agentId,
      'approved': approved,
    };

    if (widget.message.level == PermissionLevel.red && approved) {
      payload['pin'] = _pinController.text;
    }

    ws.send(payload);

    ref.read(agentProvider.notifier).updatePermissionStatus(
          agentId,
          widget.message.requestId,
          approved ? PermissionStatus.approved : PermissionStatus.denied,
        );

    if (approved) {
      ref.read(agentProvider.notifier).setProcessing(agentId, true);
      ref
          .read(agentProvider.notifier)
          .setAgentStatus(agentId, AgentStatus.working);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
    final isRed = widget.message.level == PermissionLevel.red;
    final isPending = widget.message.status == PermissionStatus.pending;
    final inputJson =
        const JsonEncoder.withIndent('  ').convert(widget.message.input);

    final fgColor = isRed ? cs.onErrorContainer : cs.onTertiaryContainer;
    final bgColor = isRed ? cs.errorContainer : cs.tertiaryContainer;

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ListTile(
              dense: true,
              leading: Icon(
                isRed ? Icons.gpp_bad : Icons.shield_outlined,
                color: isRed ? cs.error : cs.tertiary,
              ),
              title: Text(
                '${L10n.t('perm.requestTitle', lang)}:',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                  color: fgColor,
                ),
              ),
              subtitle: Text(
                widget.message.tool,
                style: TextStyle(
                  fontSize: 12,
                  color: fgColor.withValues(alpha: 0.8),
                ),
              ),
              trailing: isPending && _remainingSeconds > 0
                  ? Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: (_remainingSeconds < 60
                                ? cs.error
                                : cs.onSurfaceVariant)
                            .withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _formatTime(_remainingSeconds),
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          fontFamily: 'monospace',
                          color: _remainingSeconds < 60
                              ? cs.error
                              : cs.onSurfaceVariant,
                        ),
                      ),
                    )
                  : null,
            ),
            if (isPending && isRed)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: TextField(
                  controller: _pinController,
                  obscureText: true,
                  decoration: InputDecoration(
                    hintText: L10n.t('perm.enterPin', lang),
                    filled: true,
                    fillColor: cs.surface.withValues(alpha: 0.5),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                    isDense: true,
                    prefixIcon:
                        Icon(Icons.lock_outline, size: 18, color: cs.error),
                  ),
                  style: const TextStyle(fontSize: 14),
                ),
              ),
            if (isPending)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => _respond(false),
                        icon: const Icon(Icons.close, size: 16),
                        label: Text(L10n.t('perm.deny', lang)),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: fgColor,
                          side: BorderSide(
                            color: fgColor.withValues(alpha: 0.4),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: () => _respond(true),
                        icon: const Icon(Icons.check, size: 16),
                        label: Text(L10n.t('perm.approve', lang)),
                        style: FilledButton.styleFrom(
                          backgroundColor: isRed ? cs.error : fgColor,
                          foregroundColor: isRed ? cs.onError : bgColor,
                        ),
                      ),
                    ),
                  ],
                ),
              )
            else
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                child: Row(
                  children: [
                    Icon(
                      widget.message.status == PermissionStatus.approved
                          ? Icons.check_circle
                          : widget.message.status == PermissionStatus.denied
                              ? Icons.cancel
                              : Icons.timer_off,
                      size: 16,
                      color:
                          widget.message.status == PermissionStatus.approved
                              ? Colors.green
                              : cs.error,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      widget.message.status == PermissionStatus.approved
                          ? L10n.t('perm.approved', lang)
                          : widget.message.status == PermissionStatus.denied
                              ? L10n.t('perm.denied', lang)
                              : L10n.t('perm.expired', lang),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: widget.message.status ==
                                PermissionStatus.approved
                            ? Colors.green
                            : cs.error,
                      ),
                    ),
                  ],
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Theme(
                data: Theme.of(context).copyWith(
                  dividerColor: Colors.transparent,
                ),
                child: ExpansionTile(
                  dense: true,
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(bottom: 4),
                  initiallyExpanded: false,
                  title: Text(
                    L10n.t('perm.details', lang),
                    style: TextStyle(
                      fontSize: 12,
                      color: fgColor.withValues(alpha: 0.6),
                    ),
                  ),
                  children: [
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(8),
                      constraints: const BoxConstraints(maxHeight: 150),
                      decoration: BoxDecoration(
                        color: cs.surface.withValues(alpha: 0.5),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: SingleChildScrollView(
                        child: SelectableText(
                          inputJson,
                          style: TextStyle(
                            fontSize: 11,
                            fontFamily: 'monospace',
                            color: fgColor,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Sub-agent status bubble ──

class _SubAgentBubble extends StatelessWidget {
  final SubAgentMessage message;
  final String lang;
  const _SubAgentBubble({required this.message, required this.lang});

  Color _statusColor(ColorScheme cs) {
    return switch (message.status) {
      'spawned' => Colors.blue,
      'running' => Colors.orange,
      'completed' => Colors.green,
      'error' => cs.error,
      'cancelled' => Colors.amber,
      _ => cs.onSurfaceVariant,
    };
  }

  IconData _statusIcon() {
    return switch (message.status) {
      'spawned' => Icons.play_arrow,
      'running' => Icons.sync,
      'completed' => Icons.check_circle,
      'error' => Icons.error,
      'cancelled' => Icons.stop_circle,
      _ => Icons.help_outline,
    };
  }

  String _statusLabel() {
    return switch (message.status) {
      'spawned' => L10n.t('subagent.spawned', lang),
      'running' => L10n.t('subagent.running', lang),
      'completed' => L10n.t('subagent.completed', lang),
      'error' => L10n.t('subagent.error', lang),
      'cancelled' => L10n.t('subagent.cancelled', lang),
      _ => message.status,
    };
  }

  /// Extract short name from sub-agent ID (format: "parent::child").
  String get _displayName {
    final id = message.subAgentId;
    if (id.contains('::')) {
      return id.split('::').last;
    }
    return L10n.t('subagent.title', lang);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = _statusColor(cs);

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85),
        child: Card(
          elevation: 0,
          margin: EdgeInsets.zero,
          color: cs.surfaceContainerHigh,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(
              color: cs.outlineVariant.withValues(alpha: 0.3),
            ),
          ),
          clipBehavior: Clip.antiAlias,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Colored left border
                Container(
                  width: 4,
                  color: color,
                ),
                // Content
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Header row: icon + name + status badge
                        Row(
                          children: [
                            Icon(_statusIcon(), size: 18, color: color),
                            const SizedBox(width: 8),
                            Flexible(
                              child: Text(
                                _displayName,
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: cs.onSurface,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: color.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                _statusLabel(),
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w500,
                                  color: color,
                                ),
                              ),
                            ),
                          ],
                        ),
                        // Task description
                        if (message.task.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            message.task,
                            style: TextStyle(
                              fontSize: 13,
                              color: cs.onSurface,
                              height: 1.4,
                            ),
                          ),
                        ],
                        // Preview text (if available)
                        if (message.preview.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            message.preview,
                            style: TextStyle(
                              fontSize: 12,
                              color: cs.onSurfaceVariant,
                              height: 1.3,
                            ),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
