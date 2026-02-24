import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/a2ui.dart';
import '../providers/agent_provider.dart';
import '../providers/connection_provider.dart';

/// Renders an A2UI surface inline in the chat as native Material 3 widgets.
class A2UISurfaceWidget extends ConsumerStatefulWidget {
  final A2UISurface surface;
  const A2UISurfaceWidget({super.key, required this.surface});

  @override
  ConsumerState<A2UISurfaceWidget> createState() => _A2UISurfaceWidgetState();
}

class _A2UISurfaceWidgetState extends ConsumerState<A2UISurfaceWidget> {
  /// Form field values: field_name → current value.
  final Map<String, dynamic> _fieldValues = {};

  /// Cached TextEditingControllers keyed by component id.
  final Map<String, TextEditingController> _controllers = {};

  @override
  void initState() {
    super.initState();
    _initFieldValues();
  }

  @override
  void didUpdateWidget(A2UISurfaceWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.surface.surfaceId != widget.surface.surfaceId) {
      _disposeControllers();
      _fieldValues.clear();
      _initFieldValues();
    }
  }

  @override
  void dispose() {
    _disposeControllers();
    super.dispose();
  }

  void _disposeControllers() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    _controllers.clear();
  }

  void _initFieldValues() {
    for (final comp in widget.surface.components.values) {
      switch (comp) {
        case A2UITextField(:final fieldName, :final value):
          if (fieldName.isNotEmpty) _fieldValues[fieldName] = value;
        case A2UICheckbox(:final fieldName, :final checked):
          if (fieldName.isNotEmpty) _fieldValues[fieldName] = checked;
        case A2UISlider(:final fieldName, :final value):
          if (fieldName.isNotEmpty) _fieldValues[fieldName] = value;
        default:
          break;
      }
    }
  }

  void _onAction(String actionName) {
    final agentId = ref.read(agentProvider).activeAgentId;
    final ws = ref.read(webSocketServiceProvider);
    ws.send({
      'type': 'a2ui_user_action',
      'agent_id': agentId,
      'surface_id': widget.surface.surfaceId,
      'action_name': actionName,
      'context': Map<String, dynamic>.from(_fieldValues),
    });
    ref.read(agentProvider.notifier).setProcessing(agentId, true);
  }

  // ─────────────────────────────────────────────────────
  //  Build
  // ─────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final rootComp = widget.surface.components[widget.surface.root];

    if (rootComp == null) {
      return _errorFallback(cs, 'Root component not found');
    }

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.9,
        ),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: cs.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Title bar
            if (widget.surface.title != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                child: Row(
                  children: [
                    Icon(Icons.widgets_outlined, size: 16, color: cs.primary),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        widget.surface.title!,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: cs.onSurface,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            // Component tree
            Padding(
              padding: const EdgeInsets.all(12),
              child: _buildComponent(rootComp),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────
  //  Component dispatch
  // ─────────────────────────────────────────────────────

  Widget _buildComponent(A2UIComponent comp) {
    return switch (comp) {
      A2UIColumn() => _buildColumn(comp),
      A2UIRow() => _buildRow(comp),
      A2UIText() => _buildText(comp),
      A2UIImage() => _buildImage(comp),
      A2UIDivider() => const Divider(height: 16),
      A2UIIcon() => _buildIcon(comp),
      A2UIButton() => _buildButton(comp),
      A2UITextField() => _buildTextField(comp),
      A2UICheckbox() => _buildCheckbox(comp),
      A2UISlider() => _buildSlider(comp),
      A2UICard() => _buildCard(comp),
      A2UIDataTable() => _buildDataTable(comp),
      A2UIProgressBar() => _buildProgressBar(comp),
      A2UISpacer() => SizedBox(height: comp.height),
    };
  }

  Widget _resolveChild(String childId) {
    final comp = widget.surface.components[childId];
    if (comp == null) {
      return Text(
        'Missing: $childId',
        style: TextStyle(
          color: Theme.of(context).colorScheme.error,
          fontSize: 12,
        ),
      );
    }
    return _buildComponent(comp);
  }

  // ─────────────────────────────────────────────────────
  //  Layout
  // ─────────────────────────────────────────────────────

  Widget _buildColumn(A2UIColumn comp) {
    return Column(
      crossAxisAlignment: _parseCrossAxis(comp.crossAxis),
      mainAxisSize: MainAxisSize.min,
      children: [
        for (int i = 0; i < comp.children.length; i++) ...[
          if (i > 0) SizedBox(height: comp.spacing),
          _resolveChild(comp.children[i]),
        ],
      ],
    );
  }

  Widget _buildRow(A2UIRow comp) {
    return Row(
      mainAxisAlignment: _parseMainAxis(comp.mainAxis),
      crossAxisAlignment: _parseCrossAxis(comp.crossAxis),
      children: [
        for (int i = 0; i < comp.children.length; i++) ...[
          if (i > 0) SizedBox(width: comp.spacing),
          Flexible(child: _resolveChild(comp.children[i])),
        ],
      ],
    );
  }

  // ─────────────────────────────────────────────────────
  //  Display
  // ─────────────────────────────────────────────────────

  Widget _buildText(A2UIText comp) {
    final cs = Theme.of(context).colorScheme;
    final style = switch (comp.variant) {
      'h1' => TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: cs.onSurface),
      'h2' => TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: cs.onSurface),
      'h3' => TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: cs.onSurface),
      'caption' => TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
      _ => TextStyle(fontSize: 14, height: 1.5, color: cs.onSurface),
    };
    return SelectableText(comp.text, style: style);
  }

  Widget _buildImage(A2UIImage comp) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Image.network(
        comp.url,
        width: comp.width,
        height: comp.height,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.errorContainer,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.broken_image, size: 16, color: Theme.of(context).colorScheme.onErrorContainer),
              const SizedBox(width: 8),
              Text(
                comp.alt.isNotEmpty ? comp.alt : 'Image failed to load',
                style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onErrorContainer),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildIcon(A2UIIcon comp) {
    return Icon(
      _resolveIconData(comp.name),
      size: comp.size,
      color: comp.color != null
          ? _parseColor(comp.color!)
          : Theme.of(context).colorScheme.onSurfaceVariant,
    );
  }

  // ─────────────────────────────────────────────────────
  //  Interactive
  // ─────────────────────────────────────────────────────

  Widget _buildButton(A2UIButton comp) {
    final onPressed = comp.action.isNotEmpty ? () => _onAction(comp.action) : null;
    return switch (comp.style) {
      'outlined' => OutlinedButton(onPressed: onPressed, child: Text(comp.label)),
      'text' => TextButton(onPressed: onPressed, child: Text(comp.label)),
      _ => FilledButton(onPressed: onPressed, child: Text(comp.label)),
    };
  }

  Widget _buildTextField(A2UITextField comp) {
    // Reuse or create controller
    final controller = _controllers.putIfAbsent(comp.id, () {
      final c = TextEditingController(text: _fieldValues[comp.fieldName] as String? ?? comp.value);
      c.addListener(() {
        if (comp.fieldName.isNotEmpty) {
          _fieldValues[comp.fieldName] = c.text;
        }
      });
      return c;
    });

    return TextField(
      controller: controller,
      decoration: InputDecoration(
        labelText: comp.label,
        hintText: comp.hint.isNotEmpty ? comp.hint : null,
        isDense: true,
      ),
    );
  }

  Widget _buildCheckbox(A2UICheckbox comp) {
    final cs = Theme.of(context).colorScheme;
    final checked = _fieldValues[comp.fieldName] as bool? ?? comp.checked;
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: () {
        setState(() {
          _fieldValues[comp.fieldName] = !checked;
        });
      },
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Checkbox(
            value: checked,
            onChanged: (v) {
              setState(() {
                _fieldValues[comp.fieldName] = v ?? false;
              });
            },
          ),
          Flexible(
            child: Text(
              comp.label,
              style: TextStyle(color: cs.onSurface, fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSlider(A2UISlider comp) {
    final cs = Theme.of(context).colorScheme;
    final value = (_fieldValues[comp.fieldName] as num?)?.toDouble() ?? comp.value;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (comp.label.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              '${comp.label}: ${value.round()}',
              style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
            ),
          ),
        Slider(
          value: value.clamp(comp.min, comp.max),
          min: comp.min,
          max: comp.max,
          onChanged: (v) {
            setState(() {
              _fieldValues[comp.fieldName] = v;
            });
          },
        ),
      ],
    );
  }

  // ─────────────────────────────────────────────────────
  //  Container
  // ─────────────────────────────────────────────────────

  Widget _buildCard(A2UICard comp) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      color: cs.surfaceContainerHighest,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: EdgeInsets.all(comp.padding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (comp.title != null) ...[
              Text(
                comp.title!,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: cs.onSurface,
                ),
              ),
              const SizedBox(height: 8),
            ],
            for (int i = 0; i < comp.children.length; i++) ...[
              if (i > 0) const SizedBox(height: 8),
              _resolveChild(comp.children[i]),
            ],
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────
  //  Data
  // ─────────────────────────────────────────────────────

  Widget _buildDataTable(A2UIDataTable comp) {
    final cs = Theme.of(context).colorScheme;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingTextStyle: TextStyle(
          fontWeight: FontWeight.w600,
          color: cs.onSurface,
          fontSize: 13,
        ),
        dataTextStyle: TextStyle(
          color: cs.onSurfaceVariant,
          fontSize: 13,
        ),
        columns: comp.columns
            .map((col) => DataColumn(label: Text(col)))
            .toList(),
        rows: comp.rows
            .map((row) => DataRow(
                  cells: row.map((cell) => DataCell(Text(cell))).toList(),
                ))
            .toList(),
      ),
    );
  }

  Widget _buildProgressBar(A2UIProgressBar comp) {
    final cs = Theme.of(context).colorScheme;
    final normalized = (comp.value / 100).clamp(0.0, 1.0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (comp.label.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(comp.label, style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                Text('${comp.value.round()}%', style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              ],
            ),
          ),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: normalized,
            minHeight: 6,
          ),
        ),
      ],
    );
  }

  // ─────────────────────────────────────────────────────
  //  Helpers
  // ─────────────────────────────────────────────────────

  Widget _errorFallback(ColorScheme cs, String msg) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cs.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, size: 16, color: cs.onErrorContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(msg, style: TextStyle(color: cs.onErrorContainer, fontSize: 13)),
          ),
        ],
      ),
    );
  }

  CrossAxisAlignment _parseCrossAxis(String value) => switch (value) {
        'center' => CrossAxisAlignment.center,
        'end' => CrossAxisAlignment.end,
        'stretch' => CrossAxisAlignment.stretch,
        _ => CrossAxisAlignment.start,
      };

  MainAxisAlignment _parseMainAxis(String value) => switch (value) {
        'center' => MainAxisAlignment.center,
        'end' => MainAxisAlignment.end,
        'space_between' => MainAxisAlignment.spaceBetween,
        'space_around' => MainAxisAlignment.spaceAround,
        _ => MainAxisAlignment.start,
      };

  /// Map common icon names to Material Icons.
  IconData _resolveIconData(String name) => switch (name) {
        'check' || 'check_circle' => Icons.check_circle_outline,
        'error' || 'warning' => Icons.warning_amber_rounded,
        'info' => Icons.info_outline,
        'star' => Icons.star_outline,
        'favorite' || 'heart' => Icons.favorite_outline,
        'settings' || 'gear' => Icons.settings_outlined,
        'search' => Icons.search,
        'home' => Icons.home_outlined,
        'person' || 'user' => Icons.person_outline,
        'email' || 'mail' => Icons.email_outlined,
        'phone' => Icons.phone_outlined,
        'calendar' || 'event' => Icons.calendar_today_outlined,
        'clock' || 'time' => Icons.access_time_outlined,
        'location' || 'place' => Icons.location_on_outlined,
        'download' => Icons.download_outlined,
        'upload' => Icons.upload_outlined,
        'edit' || 'pencil' => Icons.edit_outlined,
        'delete' || 'trash' => Icons.delete_outline,
        'add' || 'plus' => Icons.add,
        'remove' || 'minus' => Icons.remove,
        'close' || 'x' => Icons.close,
        'menu' => Icons.menu,
        'arrow_right' => Icons.arrow_forward,
        'arrow_left' => Icons.arrow_back,
        'expand' => Icons.expand_more,
        'collapse' => Icons.expand_less,
        'copy' => Icons.content_copy_outlined,
        'share' => Icons.share_outlined,
        'link' => Icons.link,
        'image' || 'photo' => Icons.image_outlined,
        'file' || 'document' => Icons.description_outlined,
        'folder' => Icons.folder_outlined,
        'code' => Icons.code,
        'terminal' => Icons.terminal,
        'chart' || 'analytics' => Icons.analytics_outlined,
        'dashboard' => Icons.dashboard_outlined,
        'refresh' || 'sync' => Icons.sync,
        'notification' || 'bell' => Icons.notifications_outlined,
        'lock' => Icons.lock_outline,
        'unlock' => Icons.lock_open_outlined,
        'visibility' || 'eye' => Icons.visibility_outlined,
        'cloud' => Icons.cloud_outlined,
        _ => Icons.help_outline,
      };

  /// Parse a color string (hex or named).
  Color? _parseColor(String color) {
    if (color.startsWith('#') && color.length == 7) {
      final hex = color.substring(1);
      final value = int.tryParse(hex, radix: 16);
      if (value != null) return Color(0xFF000000 | value);
    }
    return switch (color) {
      'red' => Colors.red,
      'green' => Colors.green,
      'blue' => Colors.blue,
      'yellow' => Colors.yellow,
      'orange' => Colors.orange,
      'purple' => Colors.purple,
      'primary' => Theme.of(context).colorScheme.primary,
      'error' => Theme.of(context).colorScheme.error,
      _ => null,
    };
  }
}
