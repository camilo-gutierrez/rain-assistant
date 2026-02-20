"""Secure encryption key management using the OS keyring.

This module migrates the Fernet encryption key from plaintext storage in
config.json to the operating system's credential store (Windows Credential
Locker, macOS Keychain, or Linux SecretService).

The migration is automatic and transparent:
1. Try the OS keyring first.
2. If not there, check config.json and migrate the key to the keyring.
3. If no key exists anywhere, generate a fresh Fernet key.
4. If the keyring backend is unavailable, fall back to config.json gracefully.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cryptography.fernet import Fernet

log = logging.getLogger("rain.key_manager")

SERVICE_NAME = "rain-assistant"
KEY_NAME = "encryption_key"

# ---------------------------------------------------------------------------
# Internal: keyring helpers (with graceful fallback)
# ---------------------------------------------------------------------------

_keyring_available: bool | None = None  # lazy probe


def _is_keyring_available() -> bool:
    """Check whether a usable keyring backend exists on this system."""
    global _keyring_available
    if _keyring_available is not None:
        return _keyring_available

    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        backend = keyring.get_keyring()
        # Some Linux systems return the FailKeyring when no D-Bus
        # SecretService is running.  Treat that as "unavailable".
        if isinstance(backend, FailKeyring):
            log.warning(
                "keyring backend is FailKeyring (no SecretService?) "
                "-- falling back to config.json for encryption key."
            )
            _keyring_available = False
        else:
            _keyring_available = True
    except Exception as exc:
        log.warning("keyring library not available (%s) -- falling back to config.json.", exc)
        _keyring_available = False

    return _keyring_available


def _keyring_get() -> str | None:
    """Retrieve the encryption key from the OS keyring, or None."""
    if not _is_keyring_available():
        return None
    try:
        import keyring
        return keyring.get_password(SERVICE_NAME, KEY_NAME)
    except Exception as exc:
        log.warning("Failed to read from OS keyring: %s", exc)
        return None


def _keyring_set(key: str) -> bool:
    """Store the encryption key in the OS keyring. Returns True on success."""
    if not _is_keyring_available():
        return False
    try:
        import keyring
        keyring.set_password(SERVICE_NAME, KEY_NAME, key)
        return True
    except Exception as exc:
        log.warning("Failed to write to OS keyring: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_encryption_key() -> str | None:
    """Get the encryption key from the OS keyring.

    Returns None if the key is not stored in the keyring or if the keyring
    is unavailable.
    """
    return _keyring_get()


def store_encryption_key(key: str) -> bool:
    """Store the encryption key in the OS keyring.

    Returns True if the key was successfully stored.
    """
    return _keyring_set(key)


def migrate_key_from_config(config_path: Path) -> bool:
    """Migrate the encryption key from config.json to the OS keyring.

    If the key is found in config.json and successfully stored in the
    keyring, it is removed from config.json.  A note field
    ``_encryption_key_migrated`` is left behind so the user knows what
    happened.

    Returns True if migration was performed.
    """
    if not config_path.exists():
        return False

    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read config for key migration: %s", exc)
        return False

    enc_key = cfg.get("encryption_key")
    if not enc_key:
        return False

    # Attempt to store in keyring
    if not _keyring_set(enc_key):
        log.info(
            "Keyring unavailable -- encryption key remains in config.json."
        )
        return False

    # Successfully migrated: remove plaintext key from config.json
    del cfg["encryption_key"]
    cfg["_encryption_key_migrated"] = (
        "Key moved to OS keyring (rain-assistant/encryption_key). "
        "Do not re-add encryption_key here."
    )
    try:
        config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("Could not update config.json after migration: %s", exc)
        # The key is already in the keyring, so this is non-fatal.

    log.info("Encryption key migrated from config.json to OS keyring.")
    return True


def ensure_encryption_key(config_path: Path) -> str:
    """Main entry point: return an encryption key, migrating if necessary.

    Resolution order:
    1. OS keyring
    2. config.json  (migrate to keyring if possible)
    3. Generate new  (store in keyring, or fall back to config.json)

    This function is idempotent and safe to call multiple times.
    """
    # 1. Try keyring
    key = _keyring_get()
    if key:
        return key

    # 2. Try config.json
    cfg: dict = {}
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    existing_key = cfg.get("encryption_key")
    if existing_key:
        # Migrate to keyring (best-effort)
        if _keyring_set(existing_key):
            # Remove from config.json
            del cfg["encryption_key"]
            cfg["_encryption_key_migrated"] = (
                "Key moved to OS keyring (rain-assistant/encryption_key). "
                "Do not re-add encryption_key here."
            )
            try:
                config_path.write_text(
                    json.dumps(cfg, indent=2), encoding="utf-8"
                )
            except OSError:
                pass
            log.info("Encryption key migrated from config.json to OS keyring.")
        else:
            log.info(
                "Keyring unavailable -- encryption key stays in config.json."
            )
        return existing_key

    # 3. Generate new key
    new_key = Fernet.generate_key().decode("utf-8")

    if _keyring_set(new_key):
        log.info("New encryption key generated and stored in OS keyring.")
    else:
        # Fall back: store in config.json
        config_path.parent.mkdir(parents=True, exist_ok=True)
        cfg["encryption_key"] = new_key
        try:
            config_path.write_text(
                json.dumps(cfg, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            log.error("Could not persist new encryption key: %s", exc)
        log.info(
            "New encryption key generated and stored in config.json "
            "(keyring unavailable)."
        )

    return new_key
