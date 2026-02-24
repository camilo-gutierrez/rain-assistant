"""Shared fixtures for Rain Assistant test suite."""

import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import bcrypt
import pytest


# ---------------------------------------------------------------------------
# Temporary config directory — prevents touching the real ~/.rain-assistant
# ---------------------------------------------------------------------------

@pytest.fixture()
def rain_home(tmp_path):
    """Create a temporary Rain Assistant home directory.

    Patches the CONFIG_DIR / MEMORIES_FILE / EGOS_DIR / PLUGINS_DIR / DB_PATH
    constants in every module that references them so no test touches the
    user's real config.
    """
    config_dir = tmp_path / ".rain-assistant"
    config_dir.mkdir()

    # Sub-directories
    plugins_dir = config_dir / "plugins"
    plugins_dir.mkdir()
    egos_dir = config_dir / "alter_egos"
    egos_dir.mkdir()
    history_dir = config_dir / "history"
    history_dir.mkdir()

    # Config file with a test encryption key and PIN hash
    test_pin = "123456"
    pin_hash = bcrypt.hashpw(test_pin.encode(), bcrypt.gensalt()).decode()
    from cryptography.fernet import Fernet
    enc_key = Fernet.generate_key().decode()
    config = {
        "pin_hash": pin_hash,
        "encryption_key": enc_key,
    }
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")

    return {
        "root": tmp_path,
        "config_dir": config_dir,
        "config_file": config_file,
        "plugins_dir": plugins_dir,
        "egos_dir": egos_dir,
        "history_dir": history_dir,
        "pin": test_pin,
        "pin_hash": pin_hash,
        "encryption_key": enc_key,
    }


# ---------------------------------------------------------------------------
# Isolated database
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_db(tmp_path):
    """Provide an isolated SQLite database for tests.

    Patches database.DB_PATH and database.CONFIG_FILE / CONFIG_DIR so that
    _ensure_db() and encryption helpers use temporary paths.
    Disables the OS keyring so key_manager falls back to config.json.
    """
    import database
    import key_manager

    db_path = tmp_path / "test.db"
    config_dir = tmp_path / ".rain-assistant"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.json"

    from cryptography.fernet import Fernet
    enc_key = Fernet.generate_key().decode()
    config_file.write_text(json.dumps({"encryption_key": enc_key}), encoding="utf-8")

    old_db = database.DB_PATH
    old_config_dir = database.CONFIG_DIR
    old_config_file = database.CONFIG_FILE
    old_fernet = database._fernet
    old_keyring_available = key_manager._keyring_available

    database.DB_PATH = db_path
    database.CONFIG_DIR = config_dir
    database.CONFIG_FILE = config_file
    database._fernet = None  # force reload with test key
    key_manager._keyring_available = False  # disable keyring in tests

    database._ensure_db()

    yield db_path

    # Restore
    database.DB_PATH = old_db
    database.CONFIG_DIR = old_config_dir
    database.CONFIG_FILE = old_config_file
    database._fernet = old_fernet
    key_manager._keyring_available = old_keyring_available


# ---------------------------------------------------------------------------
# FastAPI test client (with mocked dependencies)
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_app(tmp_path):
    """Create a FastAPI TestClient that talks to an isolated server instance.

    Heavy dependencies (Transcriber, Synthesizer, claude_agent_sdk, etc.) are
    mocked so the test client only exercises the HTTP layer.
    """
    import database
    import key_manager

    # Prepare isolated paths
    db_path = tmp_path / "server_test.db"
    config_dir = tmp_path / ".rain-assistant"
    config_dir.mkdir(exist_ok=True)
    egos_dir = config_dir / "alter_egos"
    egos_dir.mkdir()
    history_dir = config_dir / "history"
    history_dir.mkdir()
    plugins_dir = config_dir / "plugins"
    plugins_dir.mkdir()

    from cryptography.fernet import Fernet
    enc_key = Fernet.generate_key().decode()

    test_pin = "999888"
    pin_hash = bcrypt.hashpw(test_pin.encode(), bcrypt.gensalt()).decode()

    config_data = {
        "pin_hash": pin_hash,
        "encryption_key": enc_key,
    }
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    # Patch database paths
    old_db = database.DB_PATH
    old_cfg_dir = database.CONFIG_DIR
    old_cfg_file = database.CONFIG_FILE
    old_fernet = database._fernet
    old_keyring_available = key_manager._keyring_available

    database.DB_PATH = db_path
    database.CONFIG_DIR = config_dir
    database.CONFIG_FILE = config_file
    database._fernet = None
    key_manager._keyring_available = False  # disable keyring in tests
    database._ensure_db()

    # Patch server module-level globals
    import server
    import shared_state
    old_config_data = dict(server.config)  # snapshot current config
    old_active_tokens = server.active_tokens.copy()
    old_auth_attempts = server._auth_attempts.copy()
    old_history_dir = shared_state.HISTORY_DIR
    old_static_dir = server.STATIC_DIR

    # Update config in-place (shared_state.config is the same object as server.config)
    server.config.clear()
    server.config.update(config_data)
    server.active_tokens.clear()
    server._auth_attempts.clear()
    shared_state.HISTORY_DIR = history_dir
    # Ensure STATIC_DIR exists for root endpoint
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>test</html>")
    (static_dir / "sw.js").write_text("// sw")
    server.STATIC_DIR = static_dir

    # Patch alter_egos paths
    import alter_egos.storage as ae_storage
    old_ae_egos_dir = ae_storage.EGOS_DIR
    old_ae_config_dir = ae_storage.CONFIG_DIR
    old_ae_active_file = ae_storage.ACTIVE_EGO_FILE
    ae_storage.EGOS_DIR = egos_dir
    ae_storage.CONFIG_DIR = config_dir
    ae_storage.ACTIVE_EGO_FILE = config_dir / "active_ego.txt"

    # Patch memories paths
    import memories.storage as mem_storage
    old_mem_config_dir = mem_storage.CONFIG_DIR
    old_mem_file = mem_storage.MEMORIES_FILE
    mem_storage.CONFIG_DIR = config_dir
    mem_storage.MEMORIES_FILE = config_dir / "memories.json"
    # Ensure per-user directory exists for default user
    (config_dir / "users" / "default").mkdir(parents=True, exist_ok=True)

    from httpx import AsyncClient, ASGITransport
    import asyncio

    # We need to pass the test_pin through
    result = {
        "app": server.app,
        "pin": test_pin,
        "config_dir": config_dir,
        "history_dir": history_dir,
        "egos_dir": egos_dir,
        "tmp_path": tmp_path,
    }

    yield result

    # Restore everything
    server.config.clear()
    server.config.update(old_config_data)
    server.active_tokens.clear()
    server.active_tokens.update(old_active_tokens)
    server._auth_attempts.clear()
    server._auth_attempts.update(old_auth_attempts)
    shared_state.HISTORY_DIR = old_history_dir
    server.STATIC_DIR = old_static_dir

    ae_storage.EGOS_DIR = old_ae_egos_dir
    ae_storage.CONFIG_DIR = old_ae_config_dir
    ae_storage.ACTIVE_EGO_FILE = old_ae_active_file

    mem_storage.CONFIG_DIR = old_mem_config_dir
    mem_storage.MEMORIES_FILE = old_mem_file

    database.DB_PATH = old_db
    database.CONFIG_DIR = old_cfg_dir
    database.CONFIG_FILE = old_cfg_file
    database._fernet = old_fernet
    key_manager._keyring_available = old_keyring_available


@pytest.fixture()
async def authenticated_client(test_app):
    """Return an httpx.AsyncClient that is already authenticated with a valid token."""
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=test_app["app"])
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Authenticate (Origin header required by CSRF middleware)
        resp = await client.post(
            "/api/auth",
            json={"pin": test_app["pin"]},
            headers={"Origin": "http://testserver"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.fixture()
async def unauthenticated_client(test_app):
    """Return an httpx.AsyncClient with no auth token."""
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=test_app["app"])
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# Helper: sample plugin YAML
# ---------------------------------------------------------------------------

SAMPLE_PLUGIN_YAML = """\
name: test_plugin
description: A test plugin for unit tests
version: "1.0"
author: tester
enabled: true
permission_level: yellow
parameters:
  - name: query
    type: string
    description: Search query
    required: true
execution:
  type: http
  method: GET
  url: "https://example.com/api?q={{query}}"
  headers:
    Authorization: "Bearer {{env.TEST_API_KEY}}"
"""

SAMPLE_BASH_PLUGIN_YAML = """\
name: bash_test
description: A bash plugin for testing
version: "1.0"
enabled: true
permission_level: green
parameters:
  - name: filename
    type: string
    description: File to check
    required: true
execution:
  type: bash
  command: "echo {{filename}}"
"""

SAMPLE_DISABLED_PLUGIN_YAML = """\
name: disabled_plugin
description: A disabled plugin
version: "1.0"
enabled: false
permission_level: yellow
parameters: []
execution:
  type: http
  method: GET
  url: "https://disabled.example.com"
"""
