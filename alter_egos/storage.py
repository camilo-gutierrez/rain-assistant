"""Storage layer for Rain Alter Egos — JSON-based personality profiles."""

import json
import re
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".rain-assistant"
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


def _ensure_dir() -> None:
    EGOS_DIR.mkdir(parents=True, exist_ok=True)


def _ego_path(ego_id: str) -> Path:
    return EGOS_DIR / f"{ego_id}.json"


def ensure_builtin_egos() -> None:
    """Create built-in ego files if they don't exist yet."""
    _ensure_dir()
    for ego in BUILTIN_EGOS:
        path = _ego_path(ego["id"])
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ego, f, indent=2, ensure_ascii=False)


def load_all_egos() -> list[dict]:
    """Load all ego definitions from disk."""
    ensure_builtin_egos()

    egos = []
    for path in sorted(EGOS_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                ego = json.load(f)
            if isinstance(ego, dict) and "id" in ego and "system_prompt" in ego:
                egos.append(ego)
        except (json.JSONDecodeError, OSError):
            continue

    return egos


def load_ego(ego_id: str) -> Optional[dict]:
    """Load a single ego by ID."""
    ensure_builtin_egos()
    path = _ego_path(ego_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_ego(ego_dict: dict) -> Path:
    """Save an ego definition to disk. Returns the file path."""
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

    _ensure_dir()
    path = _ego_path(ego_id)

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


def delete_ego(ego_id: str) -> bool:
    """Delete an ego by ID. Returns True if deleted."""
    path = _ego_path(ego_id)
    if not path.exists():
        return False

    # Prevent deleting the default "rain" ego
    if ego_id == "rain":
        raise ValueError("Cannot delete the default 'rain' ego")

    path.unlink()

    # If this was the active ego, reset to rain
    if get_active_ego_id() == ego_id:
        set_active_ego_id("rain")

    return True


def get_active_ego_id() -> str:
    """Get the currently active ego ID."""
    if ACTIVE_EGO_FILE.exists():
        try:
            ego_id = ACTIVE_EGO_FILE.read_text(encoding="utf-8").strip()
            if ego_id and _ego_path(ego_id).exists():
                return ego_id
        except OSError:
            pass
    return "rain"


def set_active_ego_id(ego_id: str) -> None:
    """Set the active ego ID."""
    _ensure_dir()
    ACTIVE_EGO_FILE.write_text(ego_id, encoding="utf-8")
