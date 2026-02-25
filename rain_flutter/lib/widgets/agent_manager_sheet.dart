import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../models/agent.dart';
import '../providers/agent_provider.dart';
import '../providers/settings_provider.dart';

/// Full-screen modal bottom sheet that acts as a professional agent manager.
/// Shows all agents with status, directory, message count, and quick actions.
// TODO(audit#9): Split into smaller widgets (_AgentCard, _StatusDot, _StatChip are candidates)
class AgentManagerSheet extends ConsumerStatefulWidget {
  final void Function(String agentId) onSwitchAgent;
  final void Function(String agentId) onDestroyAgent;
  final VoidCallback onCreateAgent;

  const AgentManagerSheet({
    super.key,
    required this.onSwitchAgent,
    required this.onDestroyAgent,
    required this.onCreateAgent,
  });

  @override
  ConsumerState<AgentManagerSheet> createState() => _AgentManagerSheetState();
}

class _AgentManagerSheetState extends ConsumerState<AgentManagerSheet> {
  String? _renamingAgentId;
  late TextEditingController _renameController;

  @override
  void initState() {
    super.initState();
    _renameController = TextEditingController();
  }

  @override
  void dispose() {
    _renameController.dispose();
    super.dispose();
  }

  void _startRename(Agent agent) {
    setState(() {
      _renamingAgentId = agent.id;
      _renameController.text = agent.label;
    });
  }

  void _commitRename(String agentId) {
    final newName = _renameController.text.trim();
    if (newName.isNotEmpty) {
      ref.read(agentProvider.notifier).renameAgent(agentId, newName);
    }
    setState(() => _renamingAgentId = null);
  }

  void _cancelRename() {
    setState(() => _renamingAgentId = null);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;
    final agentState = ref.watch(agentProvider);
    final agents = agentState.agents.values.toList();
    final activeId = agentState.activeAgentId;

    return DraggableScrollableSheet(
      initialChildSize: 0.65,
      minChildSize: 0.4,
      maxChildSize: 0.92,
      expand: false,
      builder: (context, scrollController) {
        return Column(
          children: [
            // Drag handle
            Center(
              child: Container(
                margin: const EdgeInsets.only(top: 12, bottom: 4),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: cs.onSurfaceVariant.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 12, 4),
              child: Row(
                children: [
                  Icon(Icons.hub_outlined, color: cs.primary, size: 22),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          L10n.t('agentMgr.title', lang),
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          L10n.t('agentMgr.count', lang, {
                            'n': '${agents.length}',
                            'max': '5',
                          }),
                          style: TextStyle(
                            fontSize: 12,
                            color: cs.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Create new agent button
                  if (agents.length < 5)
                    FilledButton.tonalIcon(
                      onPressed: () {
                        Navigator.of(context).pop();
                        widget.onCreateAgent();
                      },
                      icon: const Icon(Icons.add, size: 18),
                      label: Text(L10n.t('agent.create', lang)),
                    ),
                ],
              ),
            ),

            const SizedBox(height: 8),
            Divider(height: 1, color: cs.outlineVariant.withValues(alpha: 0.3)),

            // Agent list
            Expanded(
              child: agents.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.smart_toy_outlined,
                              size: 48,
                              color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
                          const SizedBox(height: 12),
                          Text(
                            L10n.t('agentMgr.empty', lang),
                            style: TextStyle(color: cs.onSurfaceVariant),
                          ),
                        ],
                      ),
                    )
                  : ListView.separated(
                      controller: scrollController,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      itemCount: agents.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (context, index) {
                        final agent = agents[index];
                        final isActive = agent.id == activeId;
                        final isRenaming = _renamingAgentId == agent.id;

                        return _AgentCard(
                          agent: agent,
                          isActive: isActive,
                          isRenaming: isRenaming,
                          renameController: _renameController,
                          lang: lang,
                          onTap: () {
                            widget.onSwitchAgent(agent.id);
                            Navigator.of(context).pop();
                          },
                          onRename: () => _startRename(agent),
                          onCommitRename: () => _commitRename(agent.id),
                          onCancelRename: _cancelRename,
                          onDelete: agents.length > 1
                              ? () {
                                  Navigator.of(context).pop();
                                  widget.onDestroyAgent(agent.id);
                                }
                              : null,
                        );
                      },
                    ),
            ),
          ],
        );
      },
    );
  }
}

// ── Individual agent card ──

class _AgentCard extends StatelessWidget {
  final Agent agent;
  final bool isActive;
  final bool isRenaming;
  final TextEditingController renameController;
  final String lang;
  final VoidCallback onTap;
  final VoidCallback onRename;
  final VoidCallback onCommitRename;
  final VoidCallback onCancelRename;
  final VoidCallback? onDelete;

  const _AgentCard({
    required this.agent,
    required this.isActive,
    required this.isRenaming,
    required this.renameController,
    required this.lang,
    required this.onTap,
    required this.onRename,
    required this.onCommitRename,
    required this.onCancelRename,
    this.onDelete,
  });

  Color _statusColor() {
    return switch (agent.status) {
      AgentStatus.working => Colors.orange,
      AgentStatus.done => Colors.green,
      AgentStatus.error => Colors.red,
      AgentStatus.idle => Colors.grey,
    };
  }

  String _statusLabel() {
    return switch (agent.status) {
      AgentStatus.working => L10n.t('agentMgr.statusWorking', lang),
      AgentStatus.done => L10n.t('agentMgr.statusDone', lang),
      AgentStatus.error => L10n.t('agentMgr.statusError', lang),
      AgentStatus.idle => L10n.t('agentMgr.statusIdle', lang),
    };
  }

  IconData _modeIcon() {
    return switch (agent.mode) {
      AgentMode.coding => Icons.code,
      AgentMode.computerUse => Icons.desktop_windows_outlined,
    };
  }

  String _modeLabel() {
    return switch (agent.mode) {
      AgentMode.coding => L10n.t('cu.modeCoding', lang),
      AgentMode.computerUse => L10n.t('cu.modeComputer', lang),
    };
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final statusColor = _statusColor();
    final isWorking = agent.status == AgentStatus.working;

    return Material(
      color: isActive ? cs.primaryContainer.withValues(alpha: 0.5) : cs.surfaceContainerLow,
      borderRadius: BorderRadius.circular(16),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isActive
                  ? cs.primary.withValues(alpha: 0.5)
                  : cs.outlineVariant.withValues(alpha: 0.2),
              width: isActive ? 1.5 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Row 1: Status + Name + Active badge + Mode badge
              Row(
                children: [
                  // Animated status dot
                  _StatusDot(color: statusColor, animate: isWorking),
                  const SizedBox(width: 10),

                  // Agent name (editable)
                  Expanded(
                    child: isRenaming
                        ? SizedBox(
                            height: 32,
                            child: TextField(
                              controller: renameController,
                              autofocus: true,
                              style: const TextStyle(
                                  fontSize: 15, fontWeight: FontWeight.w600),
                              decoration: InputDecoration(
                                isDense: true,
                                contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 6),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                suffixIcon: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    IconButton(
                                      onPressed: onCommitRename,
                                      icon: Icon(Icons.check,
                                          size: 18, color: Colors.green),
                                      padding: EdgeInsets.zero,
                                      constraints: const BoxConstraints(
                                          minWidth: 28, minHeight: 28),
                                    ),
                                    IconButton(
                                      onPressed: onCancelRename,
                                      icon: Icon(Icons.close,
                                          size: 18, color: cs.error),
                                      padding: EdgeInsets.zero,
                                      constraints: const BoxConstraints(
                                          minWidth: 28, minHeight: 28),
                                    ),
                                  ],
                                ),
                              ),
                              onSubmitted: (_) => onCommitRename(),
                            ),
                          )
                        : GestureDetector(
                            onDoubleTap: onRename,
                            child: Text(
                              agent.label,
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: isActive
                                    ? cs.onPrimaryContainer
                                    : cs.onSurface,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                  ),

                  // Active indicator
                  if (isActive)
                    Container(
                      margin: const EdgeInsets.only(left: 6),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: cs.primary,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        L10n.t('agentMgr.active', lang),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: cs.onPrimary,
                        ),
                      ),
                    ),

                  // Mode badge
                  Container(
                    margin: const EdgeInsets.only(left: 6),
                    padding:
                        const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                    decoration: BoxDecoration(
                      color: cs.secondaryContainer,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(_modeIcon(), size: 12, color: cs.onSecondaryContainer),
                        const SizedBox(width: 4),
                        Text(
                          _modeLabel(),
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: cs.onSecondaryContainer,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 10),

              // Row 2: Directory + Status text
              Row(
                children: [
                  Icon(Icons.folder_outlined,
                      size: 14, color: cs.onSurfaceVariant),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      agent.cwd ?? L10n.t('agentMgr.noDir', lang),
                      style: TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                        color: cs.onSurfaceVariant,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Status chip
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _statusLabel(),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: statusColor,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 10),

              // Row 3: Stats + Actions
              Row(
                children: [
                  // Message count
                  _StatChip(
                    icon: Icons.chat_bubble_outline,
                    label: '${agent.messages.length}',
                    cs: cs,
                  ),
                  const SizedBox(width: 8),
                  // Unread count
                  if (agent.unread > 0) ...[
                    _StatChip(
                      icon: Icons.mark_email_unread_outlined,
                      label: '${agent.unread}',
                      cs: cs,
                      highlight: true,
                    ),
                    const SizedBox(width: 8),
                  ],
                  // Computer iteration
                  if (agent.mode == AgentMode.computerUse &&
                      agent.computerIteration > 0) ...[
                    _StatChip(
                      icon: Icons.replay,
                      label: '${agent.computerIteration}',
                      cs: cs,
                    ),
                    const SizedBox(width: 8),
                  ],
                  // Sub-agents count
                  if (agent.subAgents.isNotEmpty) ...[
                    _StatChip(
                      icon: Icons.hub_outlined,
                      label: '${agent.subAgents.length} sub',
                      cs: cs,
                    ),
                    const SizedBox(width: 8),
                  ],

                  const Spacer(),

                  // Rename button
                  SizedBox(
                    height: 30,
                    child: TextButton.icon(
                      onPressed: onRename,
                      icon: const Icon(Icons.edit_outlined, size: 14),
                      label: Text(L10n.t('agentMgr.rename', lang),
                          style: const TextStyle(fontSize: 12)),
                      style: TextButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        minimumSize: Size.zero,
                      ),
                    ),
                  ),

                  // Delete button
                  if (onDelete != null)
                    SizedBox(
                      height: 30,
                      child: TextButton.icon(
                        onPressed: onDelete,
                        icon: Icon(Icons.delete_outline,
                            size: 14, color: cs.error),
                        label: Text(
                          L10n.t('history.delete', lang),
                          style: TextStyle(fontSize: 12, color: cs.error),
                        ),
                        style: TextButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 8),
                          minimumSize: Size.zero,
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Animated status dot ──

class _StatusDot extends StatefulWidget {
  final Color color;
  final bool animate;

  const _StatusDot({required this.color, this.animate = false});

  @override
  State<_StatusDot> createState() => _StatusDotState();
}

class _StatusDotState extends State<_StatusDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    if (widget.animate) _controller.repeat(reverse: true);
  }

  @override
  void didUpdateWidget(_StatusDot oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.animate && !_controller.isAnimating) {
      _controller.repeat(reverse: true);
    } else if (!widget.animate && _controller.isAnimating) {
      _controller.stop();
      _controller.value = 0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final scale = widget.animate ? 0.8 + 0.4 * _controller.value : 1.0;
        return Transform.scale(
          scale: scale,
          child: Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              color: widget.color,
              shape: BoxShape.circle,
              boxShadow: widget.animate
                  ? [
                      BoxShadow(
                        color: widget.color.withValues(alpha: 0.4),
                        blurRadius: 6,
                        spreadRadius: 1,
                      )
                    ]
                  : null,
            ),
          ),
        );
      },
    );
  }
}

// ── Small stat chip ──

class _StatChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final ColorScheme cs;
  final bool highlight;

  const _StatChip({
    required this.icon,
    required this.label,
    required this.cs,
    this.highlight = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: highlight
            ? cs.error.withValues(alpha: 0.12)
            : cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon,
              size: 13,
              color: highlight ? cs.error : cs.onSurfaceVariant),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: highlight ? cs.error : cs.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}
