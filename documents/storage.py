"""Document storage and semantic search for Rain RAG system.

Uses the same SQLite database and embedding infrastructure as memories
(all-MiniLM-L6-v2, cosine similarity, temporal decay).
"""

import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from memories.embeddings import (
    CONFIG_DIR,
    MEMORIES_DB,
    get_embedding,
    cosine_similarity,
    _serialize_embedding,
    _deserialize_embedding,
    _compute_decay,
    _ensure_dir,
    is_available as embeddings_available,
)

from .parser import parse_file
from .chunker import chunk_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    """Open the shared memories/documents database and ensure tables exist."""
    _ensure_dir()
    conn = sqlite3.connect(str(MEMORIES_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id           TEXT PRIMARY KEY,
            doc_id       TEXT NOT NULL,
            doc_name     TEXT NOT NULL,
            chunk_index  INTEGER NOT NULL,
            total_chunks INTEGER NOT NULL,
            content      TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            embedding    BLOB,
            UNIQUE(doc_id, chunk_index)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id
            ON document_chunks(doc_id)
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_document(file_path: str) -> dict:
    """Parse, chunk, embed, and store a document.

    Returns:
        {"doc_id": str, "doc_name": str, "chunks": int, "status": "ok"}

    Raises:
        FileNotFoundError: file does not exist.
        ValueError: unsupported format.
    """
    text = parse_file(file_path)
    if not text.strip():
        return {"doc_id": "", "doc_name": Path(file_path).name, "chunks": 0, "status": "empty"}

    chunks = chunk_text(text)
    if not chunks:
        return {"doc_id": "", "doc_name": Path(file_path).name, "chunks": 0, "status": "empty"}

    doc_id = secrets.token_hex(4)
    doc_name = Path(file_path).name
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_db()
    try:
        for i, chunk_content in enumerate(chunks):
            chunk_id = f"{doc_id}_{i}"
            embedding = get_embedding(chunk_content)
            blob = _serialize_embedding(embedding) if embedding else None

            conn.execute(
                """INSERT OR REPLACE INTO document_chunks
                   (id, doc_id, doc_name, chunk_index, total_chunks, content, created_at, embedding)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (chunk_id, doc_id, doc_name, i, len(chunks), chunk_content, now, blob),
            )
        conn.commit()
    finally:
        conn.close()

    logger.info("Ingested '%s' → %d chunks (doc_id=%s)", doc_name, len(chunks), doc_id)
    return {"doc_id": doc_id, "doc_name": doc_name, "chunks": len(chunks), "status": "ok"}


def list_documents() -> list[dict]:
    """List all ingested documents (grouped by doc_id).

    Returns:
        [{"doc_id": str, "doc_name": str, "chunks": int, "created_at": str}]
    """
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT doc_id, doc_name, COUNT(*) as chunk_count, MIN(created_at) as created_at
            FROM document_chunks
            GROUP BY doc_id
            ORDER BY created_at DESC
        """).fetchall()
        return [
            {"doc_id": r[0], "doc_name": r[1], "chunks": r[2], "created_at": r[3]}
            for r in rows
        ]
    finally:
        conn.close()


def remove_document(doc_id: str) -> bool:
    """Remove all chunks for a document. Returns True if found."""
    conn = _get_db()
    try:
        cursor = conn.execute("DELETE FROM document_chunks WHERE doc_id = ?", (doc_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_document_chunks(doc_id: str) -> list[dict]:
    """Get all chunks for a specific document, in order."""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, doc_name, chunk_index, total_chunks, content, created_at
               FROM document_chunks
               WHERE doc_id = ?
               ORDER BY chunk_index""",
            (doc_id,),
        ).fetchall()
        return [
            {
                "id": r[0], "doc_name": r[1], "chunk_index": r[2],
                "total_chunks": r[3], "content": r[4], "created_at": r[5],
            }
            for r in rows
        ]
    finally:
        conn.close()


def search_documents(query: str, top_k: int = 5) -> list[dict]:
    """Semantic search across all document chunks.

    Uses the same cosine_similarity + temporal_decay from memories/embeddings.
    Returns chunks sorted by relevance with _score and _doc_name fields.

    Falls back to substring search if embeddings are unavailable.
    """
    if not query:
        return []

    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, doc_id, doc_name, chunk_index, total_chunks,
                      content, created_at, embedding
               FROM document_chunks"""
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    # Try semantic search
    query_embedding = get_embedding(query)
    if query_embedding is not None:
        return _semantic_search(query_embedding, rows, top_k)

    # Fallback: substring matching
    return _substring_search(query, rows, top_k)


def _semantic_search(
    query_embedding: list[float],
    rows: list[tuple],
    top_k: int,
) -> list[dict]:
    """Rank chunks by cosine_similarity + temporal_decay."""
    DECAY_WEIGHT = 0.15
    scored = []

    for row_id, doc_id, doc_name, chunk_idx, total, content, created_at, emb_blob in rows:
        if emb_blob:
            chunk_emb = _deserialize_embedding(emb_blob)
            semantic = cosine_similarity(query_embedding, chunk_emb)
        else:
            # Generate embedding on the fly
            chunk_emb = get_embedding(content)
            if chunk_emb is None:
                continue
            semantic = cosine_similarity(query_embedding, chunk_emb)

        decay = _compute_decay(created_at)
        final = (1.0 - DECAY_WEIGHT) * semantic + DECAY_WEIGHT * decay

        scored.append((final, semantic, {
            "id": row_id,
            "doc_id": doc_id,
            "doc_name": doc_name,
            "chunk_index": chunk_idx,
            "total_chunks": total,
            "content": content,
            "created_at": created_at,
            "_score": round(final, 4),
            "_semantic_score": round(semantic, 4),
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[2] for item in scored[:top_k]]


def _substring_search(query: str, rows: list[tuple], top_k: int) -> list[dict]:
    """Fallback: case-insensitive substring matching."""
    query_lower = query.lower()
    results = []

    for row_id, doc_id, doc_name, chunk_idx, total, content, created_at, _ in rows:
        if query_lower in content.lower():
            results.append({
                "id": row_id,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "chunk_index": chunk_idx,
                "total_chunks": total,
                "content": content,
                "created_at": created_at,
                "_score": 1.0,
                "_semantic_score": 0.0,
            })

    return results[:top_k]
