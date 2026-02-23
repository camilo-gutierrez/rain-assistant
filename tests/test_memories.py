"""Tests for memories/storage.py — add, remove, search, clear memories."""

import json

import pytest

import database
import key_manager
import memories.storage as storage


@pytest.fixture()
def mem_store(tmp_path):
    """Provide an isolated memories storage using a temp directory."""
    old_config_dir = storage.CONFIG_DIR
    old_memories_file = storage.MEMORIES_FILE

    # Set up database encryption with a temporary key
    old_db_config_dir = database.CONFIG_DIR
    old_db_config_file = database.CONFIG_FILE
    old_fernet = database._fernet
    old_keyring_available = key_manager._keyring_available

    config_dir = tmp_path / ".rain-config"
    config_dir.mkdir(exist_ok=True)
    from cryptography.fernet import Fernet
    enc_key = Fernet.generate_key().decode()
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"encryption_key": enc_key}), encoding="utf-8")

    database.CONFIG_DIR = config_dir
    database.CONFIG_FILE = config_file
    database._fernet = None  # force reload with test key
    key_manager._keyring_available = False  # disable keyring in tests

    storage.CONFIG_DIR = tmp_path
    storage.MEMORIES_FILE = tmp_path / "memories.json"

    # The per-user path for "default" user
    user_dir = tmp_path / "users" / "default"
    user_dir.mkdir(parents=True, exist_ok=True)

    yield tmp_path

    storage.CONFIG_DIR = old_config_dir
    storage.MEMORIES_FILE = old_memories_file
    database.CONFIG_DIR = old_db_config_dir
    database.CONFIG_FILE = old_db_config_file
    database._fernet = old_fernet
    key_manager._keyring_available = old_keyring_available


class TestLoadMemories:
    """Test loading memories from disk."""

    def test_load_empty(self, mem_store):
        memories = storage.load_memories()
        assert memories == []

    def test_load_existing(self, mem_store):
        data = [{"id": "abc", "content": "test", "category": "fact"}]
        user_file = storage._user_memories_file("default")
        user_file.write_text(json.dumps(data), encoding="utf-8")
        memories = storage.load_memories()
        assert len(memories) == 1
        assert memories[0]["content"] == "test"

    def test_load_corrupt_json(self, mem_store):
        user_file = storage._user_memories_file("default")
        user_file.write_text("not json!!", encoding="utf-8")
        memories = storage.load_memories()
        assert memories == []

    def test_load_non_list_json(self, mem_store):
        user_file = storage._user_memories_file("default")
        user_file.write_text('{"key": "value"}', encoding="utf-8")
        memories = storage.load_memories()
        assert memories == []


class TestAddMemory:
    """Test adding new memories."""

    def test_add_basic_memory(self, mem_store):
        memory = storage.add_memory("User prefers dark mode")
        assert memory["content"] == "User prefers dark mode"
        assert memory["category"] == "fact"
        assert "id" in memory
        assert "created_at" in memory

    def test_add_memory_with_category(self, mem_store):
        memory = storage.add_memory("Likes Python", category="preference")
        assert memory["category"] == "preference"

    def test_add_memory_invalid_category_defaults(self, mem_store):
        memory = storage.add_memory("test", category="invalid_category")
        assert memory["category"] == "fact"

    @pytest.mark.parametrize("category", ["preference", "fact", "pattern", "project"])
    def test_valid_categories(self, mem_store, category):
        memory = storage.add_memory(f"Test {category}", category=category)
        assert memory["category"] == category

    def test_add_duplicate_returns_existing(self, mem_store):
        m1 = storage.add_memory("I use Vim")
        m2 = storage.add_memory("I use Vim")
        assert m1["id"] == m2["id"]

    def test_add_duplicate_case_insensitive(self, mem_store):
        m1 = storage.add_memory("I use Vim")
        m2 = storage.add_memory("i use vim")
        assert m1["id"] == m2["id"]

    def test_add_strips_whitespace(self, mem_store):
        memory = storage.add_memory("  spaced content  ")
        assert memory["content"] == "spaced content"

    def test_add_empty_raises(self, mem_store):
        with pytest.raises(ValueError, match="cannot be empty"):
            storage.add_memory("")

    def test_add_whitespace_only_raises(self, mem_store):
        with pytest.raises(ValueError, match="cannot be empty"):
            storage.add_memory("   ")

    def test_add_multiple_memories(self, mem_store):
        storage.add_memory("Memory 1")
        storage.add_memory("Memory 2")
        storage.add_memory("Memory 3")
        memories = storage.load_memories()
        assert len(memories) == 3

    def test_memories_persist_to_disk(self, mem_store):
        storage.add_memory("Persistent memory")
        # Read directly from per-user file — content is now encrypted
        user_file = storage._user_memories_file("default")
        raw = user_file.read_text(encoding="utf-8")
        from database import decrypt_field
        decrypted = decrypt_field(raw)
        data = json.loads(decrypted)
        assert len(data) == 1
        assert data[0]["content"] == "Persistent memory"


class TestRemoveMemory:
    """Test removing memories by ID."""

    def test_remove_existing(self, mem_store):
        memory = storage.add_memory("To be removed")
        assert storage.remove_memory(memory["id"]) is True
        assert storage.load_memories() == []

    def test_remove_nonexistent(self, mem_store):
        assert storage.remove_memory("nonexistent_id") is False

    def test_remove_preserves_others(self, mem_store):
        m1 = storage.add_memory("Keep this")
        m2 = storage.add_memory("Remove this")
        storage.remove_memory(m2["id"])
        memories = storage.load_memories()
        assert len(memories) == 1
        assert memories[0]["content"] == "Keep this"


class TestClearMemories:
    """Test clearing all memories."""

    def test_clear_with_data(self, mem_store):
        storage.add_memory("Memory 1")
        storage.add_memory("Memory 2")
        count = storage.clear_memories()
        assert count == 2
        assert storage.load_memories() == []

    def test_clear_empty(self, mem_store):
        count = storage.clear_memories()
        assert count == 0


class TestSearchMemories:
    """Test searching memories by content."""

    def test_search_by_content(self, mem_store):
        storage.add_memory("I prefer dark mode", category="preference")
        storage.add_memory("Python is my language", category="fact")
        storage.add_memory("Always use type hints", category="pattern")

        results = storage.search_memories("dark")
        assert len(results) == 1
        assert results[0]["content"] == "I prefer dark mode"

    def test_search_case_insensitive(self, mem_store):
        storage.add_memory("Uses TypeScript for frontend")
        results = storage.search_memories("typescript")
        assert len(results) == 1

    def test_search_by_category(self, mem_store):
        storage.add_memory("test1", category="preference")
        storage.add_memory("test2", category="fact")
        results = storage.search_memories("preference")
        assert len(results) == 1

    def test_search_empty_query_returns_all(self, mem_store):
        storage.add_memory("Memory 1")
        storage.add_memory("Memory 2")
        results = storage.search_memories("")
        assert len(results) == 2

    def test_search_no_match(self, mem_store):
        storage.add_memory("Python developer")
        results = storage.search_memories("JavaScript")
        assert len(results) == 0
