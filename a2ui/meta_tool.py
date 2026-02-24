"""render_surface meta-tool — A2UI declarative surface rendering for Rain."""

from __future__ import annotations

from typing import Any

from .schema import validate_surface

RENDER_SURFACE_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "render_surface",
        "description": (
            "Render a declarative UI surface inline in the user's chat. "
            "Use this when the user's request is best served by a visual, "
            "interactive interface rather than plain text — for example: "
            "data tables, forms, progress dashboards, configuration panels, "
            "or multi-step wizards.\n\n"
            "ACTIONS:\n"
            "  'render' — Create or fully replace a surface.\n"
            "  'update' — Partially update specific components in an "
            "existing surface.\n\n"
            "COMPONENT CATALOG:\n"
            "  Layout: column (children, spacing?, cross_axis?), "
            "row (children, spacing?, main_axis?, cross_axis?)\n"
            "  Display: text (text, variant?: h1/h2/h3/body/caption), "
            "image (url, alt?), divider, icon (name, size?)\n"
            "  Interactive: button (label, action, style?: "
            "filled/outlined/text), text_field (label, field_name, "
            "hint?, value?), checkbox (label, field_name, checked?), "
            "slider (field_name, label?, min?, max?, value?)\n"
            "  Container: card (children, title?, padding?)\n"
            "  Data: data_table (columns, rows), "
            "progress_bar (value 0-100, label?)\n"
            "  Meta: spacer (height?)\n\n"
            "SURFACE FORMAT:\n"
            "  surface_id: unique string (reuse same ID to update)\n"
            "  title: optional display title\n"
            "  root: ID of the root component\n"
            "  components: flat list of {id, type, ...props}\n"
            "  Layout components reference children by ID array.\n\n"
            "INTERACTIVE COMPONENTS:\n"
            "  Buttons must have 'action' (name sent back on click).\n"
            "  TextFields/Checkboxes/Sliders must have 'field_name' "
            "(included in action context on button click).\n\n"
            "EXAMPLE:\n"
            '  {"action": "render", "surface": {"surface_id": "form1", '
            '"title": "User Info", "root": "col", "components": ['
            '{"id": "col", "type": "column", "children": '
            '["name_field", "submit"]}, '
            '{"id": "name_field", "type": "text_field", "label": "Name"'
            ', "field_name": "name"}, '
            '{"id": "submit", "type": "button", "label": "Submit", '
            '"action": "submit_form", "style": "filled"}'
            "]}}"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["render", "update"],
                    "description": (
                        "'render' to create/replace a surface, "
                        "'update' to partially modify components "
                        "in an existing surface"
                    ),
                },
                "surface": {
                    "type": "object",
                    "description": (
                        "The surface definition with surface_id, root, "
                        "components[], and optional title. "
                        "Required for 'render' action."
                    ),
                },
                "updates": {
                    "type": "array",
                    "description": (
                        "For 'update' action only: list of partial "
                        "component updates. Each must have 'id' and "
                        "only the fields to change. "
                        "E.g. [{'id': 'status', 'text': 'Done!'}]"
                    ),
                },
                "surface_id": {
                    "type": "string",
                    "description": (
                        "For 'update' action: which surface to update."
                    ),
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_render_surface(
    args: dict[str, Any], cwd: str
) -> dict[str, Any]:
    """Handle render_surface tool calls.

    Returns a dict with ``content`` and optional ``_a2ui_surface`` /
    ``_a2ui_update`` markers that ``server.py`` intercepts to emit
    dedicated WebSocket messages.
    """
    action = args.get("action", "")

    if action == "render":
        return _action_render(args)
    elif action == "update":
        return _action_update(args)
    else:
        return {"content": f"Unknown action: {action}", "is_error": True}


def _action_render(args: dict[str, Any]) -> dict[str, Any]:
    surface = args.get("surface")
    if not surface or not isinstance(surface, dict):
        return {
            "content": "Missing 'surface' object for render action",
            "is_error": True,
        }

    is_valid, error = validate_surface(surface)
    if not is_valid:
        return {"content": f"Invalid surface: {error}", "is_error": True}

    return {
        "content": f"Surface '{surface['surface_id']}' rendered successfully.",
        "is_error": False,
        "_a2ui_surface": surface,
    }


def _action_update(args: dict[str, Any]) -> dict[str, Any]:
    surface_id = args.get("surface_id", "")
    updates = args.get("updates", [])

    if not surface_id:
        return {
            "content": "Missing 'surface_id' for update action",
            "is_error": True,
        }
    if not isinstance(updates, list) or len(updates) == 0:
        return {
            "content": "Missing or empty 'updates' list",
            "is_error": True,
        }

    for upd in updates:
        if not isinstance(upd, dict) or "id" not in upd:
            return {
                "content": "Each update must have an 'id' field",
                "is_error": True,
            }

    return {
        "content": (
            f"Surface '{surface_id}' updated "
            f"({len(updates)} component(s))."
        ),
        "is_error": False,
        "_a2ui_update": {
            "surface_id": surface_id,
            "updates": updates,
        },
    }
