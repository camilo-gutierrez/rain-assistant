"""Telegram bot configuration for Rain Assistant."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".rain-assistant"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_telegram_config() -> dict:
    """Read Telegram configuration from config.json."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return config.get("telegram", {})
    except Exception:
        return {}


def save_telegram_config(telegram_config: dict) -> None:
    """Save Telegram configuration to config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception:
            pass

    config["telegram"] = telegram_config

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_bot_token() -> str | None:
    """Get the Telegram bot token."""
    return get_telegram_config().get("bot_token")


def get_allowed_users() -> list[int]:
    """Get list of allowed Telegram user IDs. Empty = all allowed."""
    return get_telegram_config().get("allowed_users", [])


def get_default_provider() -> str:
    """Get the default AI provider for Telegram sessions."""
    return get_telegram_config().get("default_provider", "claude")


def get_default_model() -> str:
    """Get the default AI model for Telegram sessions."""
    return get_telegram_config().get("default_model", "auto")


def get_default_cwd() -> str:
    """Get the default working directory for Telegram sessions."""
    return get_telegram_config().get("default_cwd", str(Path.home()))
