"""Tests for alter_egos/storage.py — ego CRUD, built-in egos, active ego switching."""

import json

import pytest

import alter_egos.storage as storage


@pytest.fixture()
def ego_store(tmp_path):
    """Provide an isolated alter_egos storage using a temp directory."""
    old_config_dir = storage.CONFIG_DIR
    old_egos_dir = storage.EGOS_DIR
    old_active_file = storage.ACTIVE_EGO_FILE

    storage.CONFIG_DIR = tmp_path
    # Legacy paths (kept for backward compat in module)
    storage.EGOS_DIR = tmp_path / "alter_egos"
    storage.EGOS_DIR.mkdir()
    storage.ACTIVE_EGO_FILE = tmp_path / "active_ego.txt"
    # Per-user paths (new isolation structure)
    default_user_dir = tmp_path / "users" / "default"
    default_user_dir.mkdir(parents=True)
    (default_user_dir / "alter_egos").mkdir()

    yield tmp_path

    storage.CONFIG_DIR = old_config_dir
    storage.EGOS_DIR = old_egos_dir
    storage.ACTIVE_EGO_FILE = old_active_file


def _egos_dir():
    """Helper: get the per-user egos directory used in tests."""
    return storage._user_egos_dir("default")


def _active_file():
    """Helper: get the per-user active ego file used in tests."""
    return storage._user_active_file("default")


# =====================================================================
# Built-in egos
# =====================================================================

class TestBuiltinEgos:
    """Test that built-in egos are created on first access."""

    def test_ensure_builtin_egos(self, ego_store):
        storage.ensure_builtin_egos()
        egos_dir = _egos_dir()
        # All builtin egos should be created
        for ego in storage.BUILTIN_EGOS:
            path = egos_dir / f"{ego['id']}.json"
            assert path.exists(), f"Built-in ego '{ego['id']}' was not created"

    def test_builtin_ego_count(self, ego_store):
        storage.ensure_builtin_egos()
        egos = storage.load_all_egos()
        assert len(egos) >= len(storage.BUILTIN_EGOS)

    def test_builtin_egos_have_required_fields(self, ego_store):
        storage.ensure_builtin_egos()
        for ego in storage.load_all_egos():
            assert "id" in ego
            assert "system_prompt" in ego
            assert "name" in ego

    def test_rain_ego_is_default(self, ego_store):
        """The 'rain' ego should always exist and be the default."""
        storage.ensure_builtin_egos()
        ego = storage.load_ego("rain")
        assert ego is not None
        assert ego["name"] == "Rain"
        assert ego["is_builtin"] is True

    def test_builtin_not_overwritten(self, ego_store):
        """Calling ensure_builtin_egos twice should not overwrite existing files."""
        storage.ensure_builtin_egos()
        rain_path = _egos_dir() / "rain.json"
        original_content = rain_path.read_text(encoding="utf-8")

        storage.ensure_builtin_egos()
        assert rain_path.read_text(encoding="utf-8") == original_content


# =====================================================================
# Load egos
# =====================================================================

class TestLoadEgos:
    """Test loading egos from disk."""

    def test_load_all_egos(self, ego_store):
        storage.ensure_builtin_egos()
        egos = storage.load_all_egos()
        assert len(egos) > 0
        names = [e["name"] for e in egos]
        assert "Rain" in names
        assert "Professor Rain" in names
        assert "Speed Rain" in names

    def test_load_ego_by_id(self, ego_store):
        storage.ensure_builtin_egos()
        ego = storage.load_ego("professor")
        assert ego is not None
        assert ego["id"] == "professor"
        assert "pedagogical" in ego["system_prompt"].lower()

    def test_load_nonexistent_ego(self, ego_store):
        storage.ensure_builtin_egos()
        ego = storage.load_ego("nonexistent_ego")
        assert ego is None

    def test_load_corrupt_ego_file(self, ego_store):
        (_egos_dir() / "corrupt.json").write_text("not json!!", encoding="utf-8")
        ego = storage.load_ego("corrupt")
        assert ego is None

    def test_load_all_skips_invalid_files(self, ego_store):
        storage.ensure_builtin_egos()
        # Add a corrupt file
        (_egos_dir() / "bad.json").write_text("not json!!", encoding="utf-8")
        # Add a file missing required fields
        (_egos_dir() / "incomplete.json").write_text('{"name": "No ID"}', encoding="utf-8")

        egos = storage.load_all_egos()
        ids = [e["id"] for e in egos]
        assert "bad" not in ids
        assert "incomplete" not in ids


# =====================================================================
# Save egos
# =====================================================================

class TestSaveEgo:
    """Test saving new ego definitions."""

    def test_save_custom_ego(self, ego_store):
        ego_dict = {
            "id": "custom",
            "name": "Custom Ego",
            "system_prompt": "You are a custom assistant.",
        }
        path = storage.save_ego(ego_dict)
        assert path.exists()

        loaded = storage.load_ego("custom")
        assert loaded["name"] == "Custom Ego"
        assert loaded["is_builtin"] is False

    def test_save_ego_sets_defaults(self, ego_store):
        ego_dict = {
            "id": "minimal",
            "name": "Minimal",
            "system_prompt": "Minimal ego",
        }
        storage.save_ego(ego_dict)
        loaded = storage.load_ego("minimal")
        assert "emoji" in loaded
        assert "color" in loaded
        assert loaded["is_builtin"] is False

    def test_save_ego_invalid_id(self, ego_store):
        with pytest.raises(ValueError, match="Invalid ego ID"):
            storage.save_ego({"id": "Bad-ID!", "name": "Test", "system_prompt": "x"})

    def test_save_ego_empty_id(self, ego_store):
        with pytest.raises(ValueError, match="Invalid ego ID"):
            storage.save_ego({"id": "", "name": "Test", "system_prompt": "x"})

    def test_save_ego_missing_name(self, ego_store):
        with pytest.raises(ValueError, match="Missing required field"):
            storage.save_ego({"id": "test", "system_prompt": "x"})

    def test_save_ego_missing_system_prompt(self, ego_store):
        with pytest.raises(ValueError, match="Missing required field"):
            storage.save_ego({"id": "test", "name": "Test"})

    def test_save_preserves_builtin_flag(self, ego_store):
        """When updating a builtin ego, is_builtin should be preserved."""
        storage.ensure_builtin_egos()
        # Save over the rain ego
        storage.save_ego({
            "id": "rain",
            "name": "Rain Updated",
            "system_prompt": "Updated prompt",
            "is_builtin": False,  # Attempt to change it
        })
        loaded = storage.load_ego("rain")
        assert loaded["is_builtin"] is True  # Should still be True

    def test_save_ego_id_pattern(self, ego_store):
        """ID must match [a-z][a-z0-9_]{0,29}."""
        # Valid
        storage.save_ego({"id": "a", "name": "A", "system_prompt": "x"})
        storage.save_ego({"id": "test_123", "name": "T", "system_prompt": "x"})

        # Invalid
        with pytest.raises(ValueError):
            storage.save_ego({"id": "123start", "name": "T", "system_prompt": "x"})
        with pytest.raises(ValueError):
            storage.save_ego({"id": "HAS_CAPS", "name": "T", "system_prompt": "x"})


# =====================================================================
# Delete egos
# =====================================================================

class TestDeleteEgo:
    """Test deleting ego definitions."""

    def test_delete_custom_ego(self, ego_store):
        storage.save_ego({"id": "temp", "name": "Temp", "system_prompt": "x"})
        assert storage.delete_ego("temp") is True
        assert storage.load_ego("temp") is None

    def test_delete_nonexistent_ego(self, ego_store):
        assert storage.delete_ego("ghost") is False

    def test_cannot_delete_rain(self, ego_store):
        storage.ensure_builtin_egos()
        with pytest.raises(ValueError, match="Cannot delete.*rain"):
            storage.delete_ego("rain")

    def test_delete_active_ego_resets_to_rain(self, ego_store):
        """Deleting the active ego should reset active to 'rain'."""
        storage.ensure_builtin_egos()
        storage.save_ego({"id": "temp", "name": "Temp", "system_prompt": "x"})
        storage.set_active_ego_id("temp")
        assert storage.get_active_ego_id() == "temp"

        storage.delete_ego("temp")
        assert storage.get_active_ego_id() == "rain"


# =====================================================================
# Active ego switching
# =====================================================================

class TestActiveEgo:
    """Test active ego ID management."""

    def test_default_active_is_rain(self, ego_store):
        storage.ensure_builtin_egos()
        assert storage.get_active_ego_id() == "rain"

    def test_set_and_get_active(self, ego_store):
        storage.ensure_builtin_egos()
        storage.set_active_ego_id("professor")
        assert storage.get_active_ego_id() == "professor"

    def test_set_nonexistent_ego_falls_back(self, ego_store):
        """If the active ego file points to a deleted ego, fall back to rain."""
        storage.ensure_builtin_egos()
        storage.set_active_ego_id("nonexistent")
        # get_active_ego_id checks if the ego file exists
        assert storage.get_active_ego_id() == "rain"

    def test_corrupt_active_file_falls_back(self, ego_store):
        storage.ensure_builtin_egos()
        _active_file().write_text("", encoding="utf-8")
        assert storage.get_active_ego_id() == "rain"

    def test_missing_active_file(self, ego_store):
        storage.ensure_builtin_egos()
        af = _active_file()
        if af.exists():
            af.unlink()
        assert storage.get_active_ego_id() == "rain"
