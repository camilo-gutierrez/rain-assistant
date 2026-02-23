"""Tests for prompt_composer.py — system prompt composition with ego + memories."""

import json

import pytest

import alter_egos.storage as ae_storage
import memories.storage as mem_storage
from prompt_composer import compose_system_prompt, _FALLBACK_PROMPT


@pytest.fixture()
def prompt_env(tmp_path):
    """Set up isolated storage for both alter_egos and memories."""
    # Alter egos
    old_ae_config = ae_storage.CONFIG_DIR
    old_ae_egos = ae_storage.EGOS_DIR
    old_ae_active = ae_storage.ACTIVE_EGO_FILE

    ae_storage.CONFIG_DIR = tmp_path
    ae_storage.EGOS_DIR = tmp_path / "alter_egos"
    ae_storage.EGOS_DIR.mkdir()
    ae_storage.ACTIVE_EGO_FILE = tmp_path / "active_ego.txt"

    # Memories
    old_mem_config = mem_storage.CONFIG_DIR
    old_mem_file = mem_storage.MEMORIES_FILE

    mem_storage.CONFIG_DIR = tmp_path
    mem_storage.MEMORIES_FILE = tmp_path / "memories.json"
    # Ensure per-user directory exists for default user
    (tmp_path / "users" / "default").mkdir(parents=True, exist_ok=True)

    # Initialize builtins
    ae_storage.ensure_builtin_egos()

    yield tmp_path

    ae_storage.CONFIG_DIR = old_ae_config
    ae_storage.EGOS_DIR = old_ae_egos
    ae_storage.ACTIVE_EGO_FILE = old_ae_active
    mem_storage.CONFIG_DIR = old_mem_config
    mem_storage.MEMORIES_FILE = old_mem_file


class TestComposeSystemPrompt:
    """Test the compose_system_prompt function."""

    def test_default_prompt_is_rain(self, prompt_env):
        """Default (no args) should use the Rain ego."""
        prompt = compose_system_prompt()
        assert "Rain" in prompt

    def test_specific_ego(self, prompt_env):
        """Passing ego_id should use that ego's prompt."""
        prompt = compose_system_prompt(ego_id="professor")
        assert "Professor Rain" in prompt

    def test_speed_ego(self, prompt_env):
        prompt = compose_system_prompt(ego_id="speed")
        assert "Speed Rain" in prompt
        assert "concise" in prompt.lower()

    def test_security_ego(self, prompt_env):
        prompt = compose_system_prompt(ego_id="security")
        assert "Security Rain" in prompt
        assert "vulnerabilities" in prompt.lower()

    def test_nonexistent_ego_fallback(self, prompt_env):
        """Non-existent ego should fall back to _FALLBACK_PROMPT."""
        prompt = compose_system_prompt(ego_id="nonexistent")
        assert prompt.startswith(_FALLBACK_PROMPT) or "Rain" in prompt

    def test_active_ego_used_when_none(self, prompt_env):
        """When ego_id is None, the active ego should be used."""
        ae_storage.set_active_ego_id("professor")
        prompt = compose_system_prompt()
        assert "Professor Rain" in prompt

    def test_memories_appended(self, prompt_env):
        """Memories should be appended to the prompt."""
        memories = [
            {"category": "preference", "content": "User prefers dark mode"},
            {"category": "fact", "content": "User works on Rain Assistant project"},
        ]
        prompt = compose_system_prompt(memories=memories)
        assert "User Memories" in prompt
        assert "User prefers dark mode" in prompt
        assert "Rain Assistant project" in prompt
        assert "[preference]" in prompt
        assert "[fact]" in prompt

    def test_empty_memories_no_section(self, prompt_env):
        """If memories list is empty, no memories section should be added."""
        prompt = compose_system_prompt(memories=[])
        assert "User Memories" not in prompt

    def test_memories_loaded_from_disk(self, prompt_env):
        """When memories=None, they should be loaded from disk."""
        mem_storage.add_memory("Test memory from disk", category="fact")
        prompt = compose_system_prompt()
        assert "Test memory from disk" in prompt

    def test_memories_with_empty_content_skipped(self, prompt_env):
        """Memories with empty content should be silently skipped."""
        memories = [
            {"category": "fact", "content": ""},
            {"category": "fact", "content": "Real memory"},
        ]
        prompt = compose_system_prompt(memories=memories)
        assert "Real memory" in prompt

    def test_custom_ego_with_memories(self, prompt_env):
        """Custom ego + memories should both appear in the prompt."""
        ae_storage.save_ego({
            "id": "pirate",
            "name": "Pirate Rain",
            "system_prompt": "Arr, ye be a pirate coding assistant!",
        })
        memories = [
            {"category": "fact", "content": "User loves treasure"},
        ]
        prompt = compose_system_prompt(ego_id="pirate", memories=memories)
        assert "pirate" in prompt.lower()
        assert "treasure" in prompt

    def test_prompt_structure(self, prompt_env):
        """Prompt should have ego first, then memories section."""
        memories = [{"category": "fact", "content": "test_marker"}]
        prompt = compose_system_prompt(ego_id="rain", memories=memories)

        rain_pos = prompt.find("Rain")
        memories_pos = prompt.find("User Memories")
        marker_pos = prompt.find("test_marker")

        assert rain_pos < memories_pos < marker_pos
