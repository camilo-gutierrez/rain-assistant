"""Vector embedding and semantic search for Rain Memories.

Uses sentence-transformers with the all-MiniLM-L6-v2 model (small, fast, CPU-friendly).
Embeddings are stored in a per-user SQLite database alongside memory metadata.
The model is lazy-loaded on first use to avoid slowing down import/startup.

Per-user isolation: each user_id gets its own memories.db file
under ~/.rain-assistant/users/{user_id}/memories.db.
"""

import hashlib
import math
import sqlite3
import struct
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from database import encrypt_field, decrypt_field
from utils.sanitize import sanitize_user_id, secure_chmod

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding cache (Phase 6)
# ---------------------------------------------------------------------------

_EMBEDDING_CACHE: dict[str, tuple[list[float], float]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour
_CACHE_MAX_ENTRIES = 1000

CONFIG_DIR = Path.home() / ".rain-assistant"
MEMORIES_DB = CONFIG_DIR / "memories.db"  # Legacy path (kept for backward compat)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 produces 384-dim embeddings

# Lazy-loaded model reference
_model = None
_model_load_attempted = False


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _user_db_path(user_id: str = "default") -> Path:
    """Get the embeddings database path for a specific user."""
    user_id = sanitize_user_id(user_id)
    user_dir = CONFIG_DIR / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    secure_chmod(user_dir, 0o700)
    return user_dir / "memories.db"


def _get_model():
    """Lazy-load the sentence-transformers model on first use."""
    global _model, _model_load_attempted

    if _model is not None:
        return _model

    if _model_load_attempted:
        # Already tried and failed, don't retry
        return None

    _model_load_attempted = True

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model '%s'...", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Model loaded successfully.")
        return _model
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. "
            "Install with: pip install rain-assistant[memory]"
        )
        return None
    except Exception as e:
        logger.error("Failed to load sentence-transformers model: %s", e)
        return None


def is_available() -> bool:
    """Check if the embedding system is available (model can be loaded)."""
    return _get_model() is not None


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def get_embedding(text: str) -> Optional[list[float]]:
    """Generate an embedding vector for the given text.

    Returns None if sentence-transformers is not available.
    Uses an in-memory cache (1hr TTL, max 1000 entries) to avoid recomputing.
    """
    # Check cache first
    cached = _get_cached_embedding(text)
    if cached is not None:
        return cached

    model = _get_model()
    if model is None:
        return None

    try:
        embedding = model.encode(text, convert_to_numpy=True)
        result = embedding.tolist()
        _cache_embedding(text, result)
        return result
    except Exception as e:
        logger.error("Failed to generate embedding: %s", e)
        return None


def _cache_key(text: str) -> str:
    """Generate a cache key from text hash."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _get_cached_embedding(text: str) -> Optional[list[float]]:
    """Look up an embedding in the in-memory cache."""
    key = _cache_key(text)
    entry = _EMBEDDING_CACHE.get(key)
    if entry is None:
        return None
    embedding, timestamp = entry
    if time.time() - timestamp > _CACHE_TTL_SECONDS:
        del _EMBEDDING_CACHE[key]
        return None
    return embedding


def _cache_embedding(text: str, embedding: list[float]) -> None:
    """Store an embedding in the in-memory cache."""
    if len(_EMBEDDING_CACHE) >= _CACHE_MAX_ENTRIES:
        # Evict oldest quarter
        sorted_keys = sorted(
            _EMBEDDING_CACHE.keys(),
            key=lambda k: _EMBEDDING_CACHE[k][1],
        )
        for k in sorted_keys[:len(sorted_keys) // 4]:
            del _EMBEDDING_CACHE[k]
    _EMBEDDING_CACHE[_cache_key(text)] = (embedding, time.time())


def _serialize_embedding(embedding: list[float]) -> bytes:
    """Pack a list of floats into a compact binary blob (little-endian floats)."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


def _deserialize_embedding(blob: bytes) -> list[float]:
    """Unpack a binary blob back into a list of floats."""
    count = len(blob) // 4  # 4 bytes per float32
    return list(struct.unpack(f"<{count}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Returns a value between -1 and 1, where 1 means identical direction.
    """
    if len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# SQLite storage for embeddings — per-user isolated
# ---------------------------------------------------------------------------

def _get_db(user_id: str = "default") -> sqlite3.Connection:
    """Open (and initialize) the embeddings database for a specific user."""
    db_path = _user_db_path(user_id)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'fact',
            created_at TEXT NOT NULL,
            embedding BLOB
        )
    """)
    conn.commit()
    secure_chmod(db_path, 0o600)
    return conn


def store_embedding(memory_id: str, content: str, category: str,
                    created_at: str, embedding: Optional[list[float]] = None,
                    user_id: str = "default") -> None:
    """Store or update a memory's embedding in the SQLite database."""
    conn = _get_db(user_id)
    try:
        blob = _serialize_embedding(embedding) if embedding else None
        conn.execute(
            """INSERT OR REPLACE INTO memories (id, content, category, created_at, embedding)
               VALUES (?, ?, ?, ?, ?)""",
            (memory_id, encrypt_field(content), category, created_at, blob),
        )
        conn.commit()
    finally:
        conn.close()


def remove_embedding(memory_id: str, user_id: str = "default") -> None:
    """Remove a memory's embedding from the database."""
    conn = _get_db(user_id)
    try:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
    finally:
        conn.close()


def clear_embeddings(user_id: str = "default") -> None:
    """Remove all embeddings from the database."""
    conn = _get_db(user_id)
    try:
        conn.execute("DELETE FROM memories")
        conn.commit()
    finally:
        conn.close()


def get_all_embeddings(user_id: str = "default") -> dict[str, list[float]]:
    """Load all stored embeddings as {memory_id: embedding_vector}.

    Only returns entries that have a non-null embedding.
    """
    conn = _get_db(user_id)
    try:
        rows = conn.execute(
            "SELECT id, embedding FROM memories WHERE embedding IS NOT NULL"
        ).fetchall()
        result = {}
        for row_id, blob in rows:
            if blob:
                result[row_id] = _deserialize_embedding(blob)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Temporal decay
# ---------------------------------------------------------------------------

# Half-life in days: after this many days, the decay weight drops to 0.5.
# After 2x half-life -> 0.25, 3x -> 0.125, etc.
DECAY_HALF_LIFE_DAYS = 30.0

# How much weight temporal decay has vs semantic similarity.
# final_score = (1 - DECAY_WEIGHT) * semantic_score + DECAY_WEIGHT * decay_factor
DECAY_WEIGHT = 0.15


def _compute_decay(created_at: str) -> float:
    """Compute temporal decay factor (0..1) for a memory based on its age.

    Uses exponential decay: factor = 2^(-age_days / half_life).
    Returns 1.0 for brand-new memories, ~0.5 after DECAY_HALF_LIFE_DAYS days,
    and approaches 0 for very old memories.
    """
    if not created_at:
        return 0.5  # Unknown age -> neutral

    try:
        created = datetime.fromisoformat(created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = max((now - created).total_seconds() / 86400.0, 0.0)
        return math.pow(2.0, -age_days / DECAY_HALF_LIFE_DAYS)
    except (ValueError, TypeError):
        return 0.5


# ---------------------------------------------------------------------------
# Semantic search (with temporal decay)
# ---------------------------------------------------------------------------

def semantic_search(query: str, memories: list[dict],
                    top_k: int = 5, user_id: str = "default") -> list[dict]:
    """Find the most relevant memories using cosine similarity + temporal decay.

    The final score combines semantic similarity (how relevant the content is)
    with temporal decay (how recent the memory is). Recent memories get a boost
    over older ones with the same semantic relevance.

    Formula: final = (1 - DECAY_WEIGHT) * semantic + DECAY_WEIGHT * decay

    Args:
        query: The search query text.
        memories: List of memory dicts (must have 'id' and 'content' keys).
        top_k: Number of top results to return.
        user_id: User whose embeddings to search.

    Returns:
        List of memory dicts sorted by relevance (most relevant first),
        each augmented with '_score' (final) and '_semantic_score' keys.
        Returns an empty list if embeddings are not available.
    """
    if not memories or not query:
        return []

    query_embedding = get_embedding(query)
    if query_embedding is None:
        return []

    # Load stored embeddings for this user
    stored = get_all_embeddings(user_id)

    scored: list[tuple[float, float, float, dict]] = []  # (final, semantic, decay, mem)
    for mem in memories:
        mem_id = mem.get("id", "")
        if mem_id in stored:
            semantic = cosine_similarity(query_embedding, stored[mem_id])
        else:
            # Memory exists in JSON but has no embedding yet -- generate on the fly
            mem_embedding = get_embedding(mem.get("content", ""))
            if mem_embedding is not None:
                semantic = cosine_similarity(query_embedding, mem_embedding)
                # Opportunistically store the embedding for future use
                try:
                    store_embedding(
                        mem_id,
                        mem.get("content", ""),
                        mem.get("category", "fact"),
                        mem.get("created_at", ""),
                        mem_embedding,
                        user_id=user_id,
                    )
                except Exception:
                    pass
            else:
                continue

        decay = _compute_decay(mem.get("created_at", ""))
        final = (1.0 - DECAY_WEIGHT) * semantic + DECAY_WEIGHT * decay
        scored.append((final, semantic, decay, mem))

    # Sort by final score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for final, semantic, decay, mem in scored[:top_k]:
        augmented = dict(mem)
        augmented["_score"] = round(final, 4)
        augmented["_semantic_score"] = round(semantic, 4)
        results.append(augmented)

    return results
