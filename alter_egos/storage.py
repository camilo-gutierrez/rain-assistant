"""Storage layer for Rain Alter Egos — JSON-based personality profiles.

Supports per-user isolation: each user_id gets their own alter egos directory
and active ego file under ~/.rain-assistant/users/{user_id}/.
"""

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".rain-assistant"

# Legacy paths (pre-isolation) — kept for migration
EGOS_DIR = CONFIG_DIR / "alter_egos"
ACTIVE_EGO_FILE = CONFIG_DIR / "active_ego.txt"

# Valid ID pattern
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,29}$")

# ---------------------------------------------------------------------------
# Built-in Ego Definitions
# ---------------------------------------------------------------------------

BUILTIN_EGOS: list[dict] = [
    {
        "id": "rain",
        "name": "Rain",
        "emoji": "\U0001f327\ufe0f",  # 🌧️
        "description": "Default personality — friendly, tech-savvy coding assistant",
        "system_prompt": (
            "Your name is Rain. You are a friendly, tech-savvy coding assistant. "
            "When greeting the user for the first time in a conversation, introduce yourself as Rain. "
            "Use a warm and casual tone -- like a knowledgeable friend who's an expert developer. "
            "You can be a little playful, but always stay helpful and focused. "
            "Use the name 'Rain' naturally when referring to yourself. "
            "Respond in the same language the user writes in."
        ),
        "color": "#3b82f6",
        "is_builtin": True,
    },
    {
        "id": "professor",
        "name": "Professor Rain",
        "emoji": "\U0001f393",  # 🎓
        "description": "Pedagogical mode — explains step by step with analogies",
        "system_prompt": (
            "Your name is Professor Rain. You are a patient, pedagogical coding teacher. "
            "Always explain concepts step by step, using clear analogies and real-world examples. "
            "Break down complex topics into digestible pieces. When showing code, explain WHY "
            "each line matters, not just what it does. Use diagrams (ASCII art) when helpful. "
            "Encourage the user and celebrate their progress. Ask if they understood before moving on. "
            "Respond in the same language the user writes in."
        ),
        "color": "#8b5cf6",
        "is_builtin": True,
    },
    {
        "id": "speed",
        "name": "Speed Rain",
        "emoji": "\u26a1",  # ⚡
        "description": "Ultra-concise mode — code only, minimal explanations",
        "system_prompt": (
            "Your name is Speed Rain. You are an extremely concise coding assistant. "
            "Rules: (1) Give code first, explanation second — and only if necessary. "
            "(2) No greetings, no filler, no pleasantries. (3) Use the shortest possible "
            "answers. (4) If the user asks a yes/no question, answer yes or no first. "
            "(5) Prefer code blocks over prose. (6) Skip obvious explanations. "
            "Respond in the same language the user writes in."
        ),
        "color": "#f59e0b",
        "is_builtin": True,
    },
    {
        "id": "security",
        "name": "Security Rain",
        "emoji": "\U0001f6e1\ufe0f",  # 🛡️
        "description": "Security-focused mode — reviews for vulnerabilities and best practices",
        "system_prompt": (
            "Your name is Security Rain. You are a security-obsessed coding assistant. "
            "Always analyze code for potential vulnerabilities: injection attacks, XSS, CSRF, "
            "insecure dependencies, hardcoded secrets, improper auth, race conditions, etc. "
            "When writing code, always follow security best practices by default. "
            "Flag any risky patterns you see, even if the user didn't ask. "
            "Suggest security improvements proactively. Rate code security on a scale of 1-10. "
            "Respond in the same language the user writes in."
        ),
        "color": "#ef4444",
        "is_builtin": True,
    },
    {
        "id": "rubber_duck",
        "name": "Rubber Duck",
        "emoji": "\U0001f986",  # 🦆
        "description": "Socratic debugging mode — asks questions instead of giving answers",
        "system_prompt": (
            "Your name is Rubber Duck Rain. You are a Socratic debugging assistant. "
            "NEVER give direct answers or solutions. Instead, guide the user to find the "
            "answer themselves by asking probing questions: 'What do you expect this function "
            "to return?', 'What happens if that value is null?', 'Have you checked the network "
            "tab?', 'What changed since it last worked?'. "
            "If the user gets frustrated (detects frustration in tone), offer: "
            "'Would you like a hint, or should I just show you the solution?' "
            "Celebrate when they find the answer themselves. Use duck emojis occasionally. "
            "Respond in the same language the user writes in."
        ),
        "color": "#eab308",
        "is_builtin": True,
    },
]

# ---------------------------------------------------------------------------
# Per-user path helpers
# ---------------------------------------------------------------------------


def _user_egos_dir(user_id: str = "default") -> Path:
    """Get the alter egos directory for a specific user."""
    user_dir = CONFIG_DIR / "users" / user_id / "alter_egos"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _user_active_file(user_id: str = "default") -> Path:
    """Get the active ego file path for a user."""
    user_dir = CONFIG_DIR / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "active_ego.txt"


def _ensure_dir(user_id: str = "default") -> None:
    _user_egos_dir(user_id)


def _ego_path(ego_id: str, user_id: str = "default") -> Path:
    return _user_egos_dir(user_id) / f"{ego_id}.json"


# ---------------------------------------------------------------------------
# Built-in ego provisioning
# ---------------------------------------------------------------------------


def ensure_builtin_egos(user_id: str = "default") -> None:
    """Create built-in ego files in the user's directory if they don't exist yet."""
    egos_dir = _user_egos_dir(user_id)
    for ego in BUILTIN_EGOS:
        path = egos_dir / f"{ego['id']}.json"
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ego, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CRUD operations (all per-user)
# ---------------------------------------------------------------------------


def load_all_egos(user_id: str = "default") -> list[dict]:
    """Load all ego definitions from the user's directory."""
    ensure_builtin_egos(user_id)

    egos = []
    for path in sorted(_user_egos_dir(user_id).glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                ego = json.load(f)
            if isinstance(ego, dict) and "id" in ego and "system_prompt" in ego:
                egos.append(ego)
        except (json.JSONDecodeError, OSError):
            continue

    return egos


def load_ego(ego_id: str, user_id: str = "default") -> Optional[dict]:
    """Load a single ego by ID from the user's directory."""
    ensure_builtin_egos(user_id)
    path = _ego_path(ego_id, user_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_ego(ego_dict: dict, user_id: str = "default") -> Path:
    """Save an ego definition to the user's directory. Returns the file path."""
    ego_id = ego_dict.get("id", "")
    if not ego_id or not _ID_PATTERN.match(ego_id):
        raise ValueError(
            f"Invalid ego ID '{ego_id}'. Must match [a-z][a-z0-9_]{{0,29}}"
        )

    required = ["name", "system_prompt"]
    for field in required:
        if not ego_dict.get(field):
            raise ValueError(f"Missing required field: '{field}'")

    # Set defaults
    ego_dict.setdefault("emoji", "\U0001f916")  # 🤖
    ego_dict.setdefault("description", "")
    ego_dict.setdefault("color", "#6b7280")
    ego_dict.setdefault("is_builtin", False)

    _ensure_dir(user_id)
    path = _ego_path(ego_id, user_id)

    # Don't overwrite builtin flag if file already exists
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            ego_dict["is_builtin"] = existing.get("is_builtin", False)
        except (json.JSONDecodeError, OSError):
            pass

    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ego_dict, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

    return path


def delete_ego(ego_id: str, user_id: str = "default") -> bool:
    """Delete an ego by ID from the user's directory. Returns True if deleted."""
    path = _ego_path(ego_id, user_id)
    if not path.exists():
        return False

    # Prevent deleting the default "rain" ego
    if ego_id == "rain":
        raise ValueError("Cannot delete the default 'rain' ego")

    path.unlink()

    # If this was the active ego, reset to rain
    if get_active_ego_id(user_id) == ego_id:
        set_active_ego_id("rain", user_id)

    return True


def get_active_ego_id(user_id: str = "default") -> str:
    """Get the currently active ego ID for a user."""
    active_file = _user_active_file(user_id)
    if active_file.exists():
        try:
            ego_id = active_file.read_text(encoding="utf-8").strip()
            if ego_id and _ego_path(ego_id, user_id).exists():
                return ego_id
        except OSError:
            pass
    return "rain"


def set_active_ego_id(ego_id: str, user_id: str = "default") -> None:
    """Set the active ego ID for a user."""
    _ensure_dir(user_id)
    _user_active_file(user_id).write_text(ego_id, encoding="utf-8")


# ---------------------------------------------------------------------------
# Migration from legacy global layout
# ---------------------------------------------------------------------------


def migrate_shared_ego_to_user_isolated() -> dict:
    """Move legacy global active_ego.txt and ego files to per-user structure.

    Migrates:
      1. ~/.rain-assistant/active_ego.txt  ->  users/default/active_ego.txt
      2. ~/.rain-assistant/alter_egos/*.json  ->  users/default/alter_egos/*.json

    Safe to call multiple times; skips if nothing to migrate.
    """
    results: dict = {"active_ego": "skipped", "ego_files": "skipped"}

    # --- Migrate active_ego.txt ---
    legacy_active = CONFIG_DIR / "active_ego.txt"
    if legacy_active.exists():
        try:
            ego_id = legacy_active.read_text(encoding="utf-8").strip()
            set_active_ego_id(ego_id or "rain", "default")
            legacy_active.unlink()
            results["active_ego"] = "migrated"
            results["active_ego_id"] = ego_id or "rain"
            logger.info("Migrated legacy active_ego.txt (ego_id=%s)", ego_id)
        except Exception as e:
            results["active_ego"] = "error"
            results["active_ego_error"] = str(e)
            logger.warning("Failed to migrate active_ego.txt: %s", e)

    # --- Migrate ego JSON files ---
    legacy_dir = CONFIG_DIR / "alter_egos"
    if legacy_dir.is_dir():
        user_dir = _user_egos_dir("default")
        migrated_files = []
        for legacy_file in legacy_dir.glob("*.json"):
            dest = user_dir / legacy_file.name
            try:
                if not dest.exists():
                    # Copy to user dir (don't move yet, in case of error)
                    shutil.copy2(str(legacy_file), str(dest))
                migrated_files.append(legacy_file.name)
            except Exception as e:
                logger.warning("Failed to migrate ego file %s: %s", legacy_file.name, e)

        # Remove legacy files only after all copies succeeded
        if migrated_files:
            for legacy_file in legacy_dir.glob("*.json"):
                try:
                    legacy_file.unlink()
                except OSError:
                    pass
            # Remove legacy dir if empty
            try:
                legacy_dir.rmdir()
            except OSError:
                pass  # Not empty (maybe .tmp files remain)
            results["ego_files"] = "migrated"
            results["migrated_files"] = migrated_files
            logger.info("Migrated %d ego files to per-user dir", len(migrated_files))

    return results
