"""A2UI surface payload validation."""

from __future__ import annotations

from typing import Any

# Supported component types → required fields (name → expected type)
COMPONENT_TYPES: dict[str, dict[str, type | tuple]] = {
    # Layout
    "column": {"children": list},
    "row": {"children": list},
    # Display
    "text": {"text": str},
    "image": {"url": str},
    "divider": {},
    "icon": {"name": str},
    # Interactive
    "button": {"label": str},
    "text_field": {"label": str},
    "checkbox": {"label": str},
    "slider": {},
    # Container
    "card": {"children": list},
    # Data
    "data_table": {"columns": list, "rows": list},
    "progress_bar": {"value": (int, float)},
    # Meta
    "spacer": {},
}

MAX_COMPONENTS = 100
MAX_SURFACE_ID_LEN = 64
MAX_TITLE_LEN = 200


def validate_surface(payload: dict[str, Any]) -> tuple[bool, str]:
    """Validate an A2UI surface payload.

    Returns ``(is_valid, error_message)``.
    """
    surface_id = payload.get("surface_id")
    if not surface_id or not isinstance(surface_id, str):
        return False, "Missing or invalid 'surface_id'"
    if len(surface_id) > MAX_SURFACE_ID_LEN:
        return False, f"'surface_id' exceeds {MAX_SURFACE_ID_LEN} chars"

    root = payload.get("root")
    if not root or not isinstance(root, str):
        return False, "Missing or invalid 'root' component ID"

    components = payload.get("components")
    if not isinstance(components, list) or len(components) == 0:
        return False, "Missing or empty 'components' list"
    if len(components) > MAX_COMPONENTS:
        return False, f"Too many components ({len(components)} > {MAX_COMPONENTS})"

    # Build ID set and validate each component
    ids: set[str] = set()
    for comp in components:
        if not isinstance(comp, dict):
            return False, "Component must be a dict"

        comp_id = comp.get("id")
        if not comp_id or not isinstance(comp_id, str):
            return False, "Component missing 'id'"
        if comp_id in ids:
            return False, f"Duplicate component ID: '{comp_id}'"
        ids.add(comp_id)

        comp_type = comp.get("type")
        if comp_type not in COMPONENT_TYPES:
            return False, f"Unknown component type: '{comp_type}' (id: {comp_id})"

        # Validate required fields for this type
        for field, expected in COMPONENT_TYPES[comp_type].items():
            if field not in comp:
                return False, (
                    f"Component '{comp_id}' ({comp_type}) missing "
                    f"required field '{field}'"
                )
            if isinstance(expected, tuple):
                if not isinstance(comp[field], expected):
                    return False, (
                        f"Component '{comp_id}' field '{field}' has wrong type"
                    )
            elif not isinstance(comp[field], expected):
                return False, (
                    f"Component '{comp_id}' field '{field}' has wrong type"
                )

    # Verify root exists
    if root not in ids:
        return False, f"Root component '{root}' not found in components"

    # Verify all children references exist
    for comp in components:
        children = comp.get("children", [])
        if isinstance(children, list):
            for child_id in children:
                if isinstance(child_id, str) and child_id not in ids:
                    return False, (
                        f"Component '{comp['id']}' references "
                        f"unknown child '{child_id}'"
                    )

    return True, ""
