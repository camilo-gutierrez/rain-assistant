"""Route modules for Rain Assistant.

Each module exports an APIRouter instance that gets included in the main
FastAPI app via app.include_router().
"""

from routes.auth import auth_router
from routes.agents import agents_router
from routes.files import files_router
from routes.settings import settings_router
from routes.directors import directors_router
from routes.images import images_router

__all__ = [
    "auth_router",
    "agents_router",
    "files_router",
    "settings_router",
    "directors_router",
    "images_router",
]
