/// A2UI (Agent-to-User Interface) component model.
///
/// Declarative UI surfaces sent by the AI agent. Each surface contains
/// a flat list of components referenced by ID, with a root component
/// that forms the tree.
library;

// ─────────────────────────────────────────────────────────
//  Surface
// ─────────────────────────────────────────────────────────

/// A complete A2UI surface to be rendered inline in the chat.
class A2UISurface {
  final String surfaceId;
  final String? title;
  final String root;
  final Map<String, A2UIComponent> components;

  const A2UISurface({
    required this.surfaceId,
    this.title,
    required this.root,
    required this.components,
  });

  factory A2UISurface.fromJson(Map<String, dynamic> json) {
    final comps = <String, A2UIComponent>{};
    for (final raw in (json['components'] as List? ?? [])) {
      final comp = A2UIComponent.fromJson(Map<String, dynamic>.from(raw as Map));
      comps[comp.id] = comp;
    }
    return A2UISurface(
      surfaceId: json['surface_id'] as String? ?? '',
      title: json['title'] as String?,
      root: json['root'] as String? ?? '',
      components: comps,
    );
  }

  Map<String, dynamic> toJson() => {
        'surface_id': surfaceId,
        if (title != null) 'title': title,
        'root': root,
        'components': components.values.map((c) => c.toJson()).toList(),
      };

  /// Return a new surface with partial component updates applied.
  A2UISurface applyUpdates(List<Map<String, dynamic>> updates) {
    final newComps = Map<String, A2UIComponent>.from(components);
    for (final upd in updates) {
      final id = upd['id'] as String?;
      if (id == null) continue;
      final existing = newComps[id];
      if (existing != null) {
        final merged = {...existing.toJson(), ...upd};
        newComps[id] = A2UIComponent.fromJson(merged);
      }
    }
    return A2UISurface(
      surfaceId: surfaceId,
      title: title,
      root: root,
      components: newComps,
    );
  }
}

// ─────────────────────────────────────────────────────────
//  Component (sealed)
// ─────────────────────────────────────────────────────────

/// Base sealed class for all A2UI component types.
sealed class A2UIComponent {
  final String id;
  final String type;
  const A2UIComponent({required this.id, required this.type});

  Map<String, dynamic> toJson();

  static A2UIComponent fromJson(Map<String, dynamic> json) {
    final type = json['type'] as String? ?? '';
    return switch (type) {
      'column' => A2UIColumn.fromJson(json),
      'row' => A2UIRow.fromJson(json),
      'text' => A2UIText.fromJson(json),
      'image' => A2UIImage.fromJson(json),
      'divider' => A2UIDivider.fromJson(json),
      'icon' => A2UIIcon.fromJson(json),
      'button' => A2UIButton.fromJson(json),
      'text_field' => A2UITextField.fromJson(json),
      'checkbox' => A2UICheckbox.fromJson(json),
      'slider' => A2UISlider.fromJson(json),
      'card' => A2UICard.fromJson(json),
      'data_table' => A2UIDataTable.fromJson(json),
      'progress_bar' => A2UIProgressBar.fromJson(json),
      'spacer' => A2UISpacer.fromJson(json),
      _ => A2UIText(id: json['id'] as String? ?? '', text: 'Unknown: $type', variant: 'caption'),
    };
  }
}

// ─────────────────────────────────────────────────────────
//  Layout
// ─────────────────────────────────────────────────────────

class A2UIColumn extends A2UIComponent {
  final List<String> children;
  final double spacing;
  final String crossAxis;

  const A2UIColumn({
    required super.id,
    required this.children,
    this.spacing = 8,
    this.crossAxis = 'start',
  }) : super(type: 'column');

  factory A2UIColumn.fromJson(Map<String, dynamic> json) => A2UIColumn(
        id: json['id'] as String? ?? '',
        children: List<String>.from(json['children'] as List? ?? []),
        spacing: (json['spacing'] as num?)?.toDouble() ?? 8,
        crossAxis: json['cross_axis'] as String? ?? 'start',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'children': children,
        'spacing': spacing,
        'cross_axis': crossAxis,
      };
}

class A2UIRow extends A2UIComponent {
  final List<String> children;
  final double spacing;
  final String mainAxis;
  final String crossAxis;

  const A2UIRow({
    required super.id,
    required this.children,
    this.spacing = 8,
    this.mainAxis = 'start',
    this.crossAxis = 'center',
  }) : super(type: 'row');

  factory A2UIRow.fromJson(Map<String, dynamic> json) => A2UIRow(
        id: json['id'] as String? ?? '',
        children: List<String>.from(json['children'] as List? ?? []),
        spacing: (json['spacing'] as num?)?.toDouble() ?? 8,
        mainAxis: json['main_axis'] as String? ?? 'start',
        crossAxis: json['cross_axis'] as String? ?? 'center',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'children': children,
        'spacing': spacing,
        'main_axis': mainAxis,
        'cross_axis': crossAxis,
      };
}

// ─────────────────────────────────────────────────────────
//  Display
// ─────────────────────────────────────────────────────────

class A2UIText extends A2UIComponent {
  final String text;
  final String variant; // h1, h2, h3, body, caption

  const A2UIText({
    required super.id,
    required this.text,
    this.variant = 'body',
  }) : super(type: 'text');

  factory A2UIText.fromJson(Map<String, dynamic> json) => A2UIText(
        id: json['id'] as String? ?? '',
        text: json['text'] as String? ?? '',
        variant: json['variant'] as String? ?? 'body',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'text': text,
        'variant': variant,
      };
}

class A2UIImage extends A2UIComponent {
  final String url;
  final String alt;
  final double? width;
  final double? height;

  const A2UIImage({
    required super.id,
    required this.url,
    this.alt = '',
    this.width,
    this.height,
  }) : super(type: 'image');

  factory A2UIImage.fromJson(Map<String, dynamic> json) => A2UIImage(
        id: json['id'] as String? ?? '',
        url: json['url'] as String? ?? '',
        alt: json['alt'] as String? ?? '',
        width: (json['width'] as num?)?.toDouble(),
        height: (json['height'] as num?)?.toDouble(),
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'url': url,
        'alt': alt,
        if (width != null) 'width': width,
        if (height != null) 'height': height,
      };
}

class A2UIDivider extends A2UIComponent {
  const A2UIDivider({required super.id}) : super(type: 'divider');

  factory A2UIDivider.fromJson(Map<String, dynamic> json) =>
      A2UIDivider(id: json['id'] as String? ?? '');

  @override
  Map<String, dynamic> toJson() => {'id': id, 'type': type};
}

class A2UIIcon extends A2UIComponent {
  final String name;
  final double size;
  final String? color;

  const A2UIIcon({
    required super.id,
    required this.name,
    this.size = 24,
    this.color,
  }) : super(type: 'icon');

  factory A2UIIcon.fromJson(Map<String, dynamic> json) => A2UIIcon(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? 'help',
        size: (json['size'] as num?)?.toDouble() ?? 24,
        color: json['color'] as String?,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'name': name,
        'size': size,
        if (color != null) 'color': color,
      };
}

// ─────────────────────────────────────────────────────────
//  Interactive
// ─────────────────────────────────────────────────────────

class A2UIButton extends A2UIComponent {
  final String label;
  final String style; // filled, outlined, text
  final String action;

  const A2UIButton({
    required super.id,
    required this.label,
    this.style = 'filled',
    this.action = '',
  }) : super(type: 'button');

  factory A2UIButton.fromJson(Map<String, dynamic> json) => A2UIButton(
        id: json['id'] as String? ?? '',
        label: json['label'] as String? ?? '',
        style: json['style'] as String? ?? 'filled',
        action: json['action'] as String? ?? '',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'label': label,
        'style': style,
        'action': action,
      };
}

class A2UITextField extends A2UIComponent {
  final String label;
  final String hint;
  final String value;
  final String fieldName;

  const A2UITextField({
    required super.id,
    required this.label,
    this.hint = '',
    this.value = '',
    this.fieldName = '',
  }) : super(type: 'text_field');

  factory A2UITextField.fromJson(Map<String, dynamic> json) => A2UITextField(
        id: json['id'] as String? ?? '',
        label: json['label'] as String? ?? '',
        hint: json['hint'] as String? ?? '',
        value: json['value'] as String? ?? '',
        fieldName: json['field_name'] as String? ?? '',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'label': label,
        'hint': hint,
        'value': value,
        'field_name': fieldName,
      };
}

class A2UICheckbox extends A2UIComponent {
  final String label;
  final bool checked;
  final String fieldName;

  const A2UICheckbox({
    required super.id,
    required this.label,
    this.checked = false,
    this.fieldName = '',
  }) : super(type: 'checkbox');

  factory A2UICheckbox.fromJson(Map<String, dynamic> json) => A2UICheckbox(
        id: json['id'] as String? ?? '',
        label: json['label'] as String? ?? '',
        checked: json['checked'] as bool? ?? false,
        fieldName: json['field_name'] as String? ?? '',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'label': label,
        'checked': checked,
        'field_name': fieldName,
      };
}

class A2UISlider extends A2UIComponent {
  final double min;
  final double max;
  final double value;
  final String fieldName;
  final String label;

  const A2UISlider({
    required super.id,
    this.min = 0,
    this.max = 100,
    this.value = 50,
    this.fieldName = '',
    this.label = '',
  }) : super(type: 'slider');

  factory A2UISlider.fromJson(Map<String, dynamic> json) => A2UISlider(
        id: json['id'] as String? ?? '',
        min: (json['min'] as num?)?.toDouble() ?? 0,
        max: (json['max'] as num?)?.toDouble() ?? 100,
        value: (json['value'] as num?)?.toDouble() ?? 50,
        fieldName: json['field_name'] as String? ?? '',
        label: json['label'] as String? ?? '',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'min': min, 'max': max, 'value': value,
        'field_name': fieldName,
        'label': label,
      };
}

// ─────────────────────────────────────────────────────────
//  Container
// ─────────────────────────────────────────────────────────

class A2UICard extends A2UIComponent {
  final List<String> children;
  final String? title;
  final double padding;

  const A2UICard({
    required super.id,
    required this.children,
    this.title,
    this.padding = 16,
  }) : super(type: 'card');

  factory A2UICard.fromJson(Map<String, dynamic> json) => A2UICard(
        id: json['id'] as String? ?? '',
        children: List<String>.from(json['children'] as List? ?? []),
        title: json['title'] as String?,
        padding: (json['padding'] as num?)?.toDouble() ?? 16,
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'children': children,
        if (title != null) 'title': title,
        'padding': padding,
      };
}

// ─────────────────────────────────────────────────────────
//  Data
// ─────────────────────────────────────────────────────────

class A2UIDataTable extends A2UIComponent {
  final List<String> columns;
  final List<List<String>> rows;

  const A2UIDataTable({
    required super.id,
    required this.columns,
    required this.rows,
  }) : super(type: 'data_table');

  factory A2UIDataTable.fromJson(Map<String, dynamic> json) {
    final rawRows = json['rows'] as List? ?? [];
    final rows = rawRows
        .map((r) => (r as List).map((c) => c.toString()).toList())
        .toList();
    return A2UIDataTable(
      id: json['id'] as String? ?? '',
      columns:
          (json['columns'] as List? ?? []).map((c) => c.toString()).toList(),
      rows: rows,
    );
  }

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'columns': columns,
        'rows': rows,
      };
}

class A2UIProgressBar extends A2UIComponent {
  final double value; // 0-100
  final String label;

  const A2UIProgressBar({
    required super.id,
    required this.value,
    this.label = '',
  }) : super(type: 'progress_bar');

  factory A2UIProgressBar.fromJson(Map<String, dynamic> json) =>
      A2UIProgressBar(
        id: json['id'] as String? ?? '',
        value: (json['value'] as num?)?.toDouble() ?? 0,
        label: json['label'] as String? ?? '',
      );

  @override
  Map<String, dynamic> toJson() => {
        'id': id, 'type': type,
        'value': value,
        'label': label,
      };
}

// ─────────────────────────────────────────────────────────
//  Meta
// ─────────────────────────────────────────────────────────

class A2UISpacer extends A2UIComponent {
  final double height;

  const A2UISpacer({required super.id, this.height = 16}) : super(type: 'spacer');

  factory A2UISpacer.fromJson(Map<String, dynamic> json) => A2UISpacer(
        id: json['id'] as String? ?? '',
        height: (json['height'] as num?)?.toDouble() ?? 16,
      );

  @override
  Map<String, dynamic> toJson() => {'id': id, 'type': type, 'height': height};
}
