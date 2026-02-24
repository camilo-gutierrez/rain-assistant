"""Rain A2UI — Agent-to-User declarative UI surfaces."""

from .meta_tool import RENDER_SURFACE_DEFINITION, handle_render_surface
from .schema import validate_surface

__all__ = [
    "RENDER_SURFACE_DEFINITION",
    "handle_render_surface",
    "validate_surface",
]
