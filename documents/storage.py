"""Document storage and semantic search for Rain RAG system.

Uses the same SQLite database and embedding infrastructure as memories
(all-MiniLM-L6-v2, cosine similarity, temporal decay).

Supports multiple search strategies:
- "hybrid" (default): BM25 keyword + semantic similarity + temporal decay
- "semantic": cosine similarity + temporal decay only
- "bm25": BM25 keyword scoring only
- "keyword": substring matching fallback
"""

import json
import logging
import math
import re
import secrets
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from database import encrypt_field, decrypt_field
from utils.sanitize import sanitize_user_id, secure_chmod

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

# Cross-encoder for optional reranking (lazy-loaded)
_cross_encoder = None
_cross_encoder_load_attempted = False

# ANN index for fast approximate nearest-neighbor search (optional, Phase 7)
_ann_indices: dict[str, "ANNIndex"] = {}  # per-user ANN indices
_ann_available: Optional[bool] = None


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
            user_id      TEXT NOT NULL DEFAULT 'default',
            UNIQUE(doc_id, chunk_index)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id
            ON document_chunks(doc_id)
    """)

    # Migration: add user_id column if missing (for pre-existing databases)
    cursor = conn.execute("PRAGMA table_info(document_chunks)")
    columns = {row[1] for row in cursor.fetchall()}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE document_chunks ADD COLUMN user_id TEXT DEFAULT 'default'")
        conn.execute("UPDATE document_chunks SET user_id = 'default' WHERE user_id IS NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_user_doc ON document_chunks(user_id, doc_id)")
        conn.commit()

    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_user_doc ON document_chunks(user_id, doc_id)")

    # Phase 5: document_meta table for metadata, tags, collections
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_meta (
            doc_id      TEXT PRIMARY KEY,
            title       TEXT NOT NULL DEFAULT '',
            source_url  TEXT DEFAULT '',
            tags        TEXT DEFAULT '[]',
            category    TEXT DEFAULT '',
            file_type   TEXT DEFAULT '',
            file_size   INTEGER DEFAULT 0,
            page_count  INTEGER DEFAULT 0,
            user_id     TEXT NOT NULL DEFAULT 'default',
            created_at  TEXT NOT NULL DEFAULT '',
            updated_at  TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docmeta_user ON document_meta(user_id)")

    # Migration: populate document_meta from existing chunks if table was just created
    existing_meta = conn.execute(
        "SELECT COUNT(*) FROM document_meta"
    ).fetchone()[0]
    if existing_meta == 0:
        orphans = conn.execute("""
            SELECT doc_id, doc_name, MIN(created_at) as created_at, user_id
            FROM document_chunks
            GROUP BY doc_id
        """).fetchall()
        for doc_id, doc_name, created_at, uid in orphans:
            ext = Path(doc_name).suffix.lower() if doc_name else ""
            conn.execute("""
                INSERT OR IGNORE INTO document_meta
                (doc_id, title, file_type, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (doc_id, doc_name, ext, uid or "default", created_at or "", created_at or ""))

    conn.commit()
    secure_chmod(MEMORIES_DB, 0o600)
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_document(file_path: str, user_id: str = "default") -> dict:
    """Parse, chunk, embed, and store a document.

    Args:
        file_path: Path to the file to ingest.
        user_id: Owner of this document (for per-user isolation).

    Returns:
        {"doc_id": str, "doc_name": str, "chunks": int, "status": "ok",
         "file_type": str, "file_size": int}

    Raises:
        FileNotFoundError: file does not exist.
        ValueError: unsupported format.
    """
    user_id = sanitize_user_id(user_id)
    text = parse_file(file_path)
    if not text.strip():
        return {"doc_id": "", "doc_name": Path(file_path).name, "chunks": 0, "status": "empty"}

    chunks = chunk_text(text)
    if not chunks:
        return {"doc_id": "", "doc_name": Path(file_path).name, "chunks": 0, "status": "empty"}

    doc_id = secrets.token_hex(4)
    doc_name = Path(file_path).name
    now = datetime.now(timezone.utc).isoformat()
    file_ext = Path(file_path).suffix.lower()
    file_size = Path(file_path).stat().st_size

    conn = _get_db()
    try:
        for i, chunk_content in enumerate(chunks):
            chunk_id = f"{doc_id}_{i}"
            embedding = get_embedding(chunk_content)
            blob = _serialize_embedding(embedding) if embedding else None

            conn.execute(
                """INSERT OR REPLACE INTO document_chunks
                   (id, doc_id, doc_name, chunk_index, total_chunks, content, created_at, embedding, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (chunk_id, doc_id, doc_name, i, len(chunks), encrypt_field(chunk_content), now, blob, user_id),
            )

        # Also insert into document_meta (Phase 5)
        conn.execute("""
            INSERT OR REPLACE INTO document_meta
            (doc_id, title, file_type, file_size, user_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (doc_id, doc_name, file_ext, file_size, user_id, now, now))

        conn.commit()
        _invalidate_ann_index(user_id)
    finally:
        conn.close()

    logger.info("Ingested '%s' → %d chunks (doc_id=%s, user=%s)", doc_name, len(chunks), doc_id, user_id)
    return {
        "doc_id": doc_id, "doc_name": doc_name, "chunks": len(chunks),
        "status": "ok", "file_type": file_ext, "file_size": file_size,
    }


def list_documents(user_id: str = "default") -> list[dict]:
    """List all ingested documents (grouped by doc_id) for a given user.

    Args:
        user_id: Owner whose documents to list.

    Returns:
        [{"doc_id": str, "doc_name": str, "chunks": int, "created_at": str,
          "tags": list[str], "category": str, "file_type": str}]
    """
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT dc.doc_id, dc.doc_name, COUNT(*) as chunk_count,
                   MIN(dc.created_at) as created_at,
                   COALESCE(dm.tags, '[]') as tags,
                   COALESCE(dm.category, '') as category,
                   COALESCE(dm.file_type, '') as file_type
            FROM document_chunks dc
            LEFT JOIN document_meta dm ON dc.doc_id = dm.doc_id
            WHERE dc.user_id = ?
            GROUP BY dc.doc_id
            ORDER BY created_at DESC
        """, (user_id,)).fetchall()
        results = []
        for r in rows:
            try:
                tags = json.loads(r[4]) if r[4] else []
            except (json.JSONDecodeError, TypeError):
                tags = []
            results.append({
                "doc_id": r[0], "doc_name": r[1], "chunks": r[2], "created_at": r[3],
                "tags": tags, "category": r[5], "file_type": r[6],
            })
        return results
    finally:
        conn.close()


def remove_document(doc_id: str, user_id: str = "default") -> bool:
    """Remove all chunks and metadata for a document owned by user_id. Returns True if found."""
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM document_chunks WHERE doc_id = ? AND user_id = ?",
            (doc_id, user_id),
        )
        conn.execute(
            "DELETE FROM document_meta WHERE doc_id = ? AND user_id = ?",
            (doc_id, user_id),
        )
        conn.commit()
        _invalidate_ann_index(user_id)
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_document_chunks(doc_id: str, user_id: str = "default") -> list[dict]:
    """Get all chunks for a specific document owned by user_id, in order."""
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, doc_name, chunk_index, total_chunks, content, created_at
               FROM document_chunks
               WHERE doc_id = ? AND user_id = ?
               ORDER BY chunk_index""",
            (doc_id, user_id),
        ).fetchall()
        return [
            {
                "id": r[0], "doc_name": r[1], "chunk_index": r[2],
                "total_chunks": r[3], "content": decrypt_field(r[4]), "created_at": r[5],
            }
            for r in rows
        ]
    finally:
        conn.close()


def search_documents(
    query: str,
    user_id: str = "default",
    top_k: int = 5,
    strategy: str = "hybrid",
    search_options: Optional[dict] = None,
    filters: Optional[dict] = None,
) -> list[dict]:
    """Search across document chunks belonging to a user.

    Supports multiple strategies:
    - "hybrid" (default): BM25 keyword + semantic + temporal decay
    - "semantic": cosine similarity + temporal decay only
    - "bm25": BM25 keyword scoring only
    - "keyword": substring matching fallback

    Falls back through hybrid → bm25 → keyword if embeddings unavailable.

    Args:
        query: Search query text.
        user_id: Owner whose documents to search.
        top_k: Maximum number of results to return.
        strategy: Search strategy ("hybrid", "semantic", "bm25", "keyword").
        search_options: Optional dict with weights and flags:
            - alpha (float): Semantic weight (default 0.6)
            - beta (float): BM25 weight (default 0.25)
            - gamma (float): Decay weight (default 0.15)
            - rerank (bool): Use cross-encoder reranking (default False)
        filters: Optional filtering dict:
            - tags (list[str]): Only documents with ALL these tags
            - file_type (str): Only documents of this type (e.g. ".pdf")
            - doc_ids (list[str]): Only search within these documents
            - category (str): Only documents in this category
    """
    user_id = sanitize_user_id(user_id)
    if not query:
        return []

    opts = search_options or {}

    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, doc_id, doc_name, chunk_index, total_chunks,
                      content, created_at, embedding
               FROM document_chunks
               WHERE user_id = ?""",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    # Decrypt content in fetched rows
    rows = [
        (r[0], r[1], r[2], r[3], r[4], decrypt_field(r[5]), r[6], r[7])
        for r in rows
    ]

    # Apply metadata filters (Phase 5)
    if filters:
        rows = _apply_filters(rows, user_id, filters)
        if not rows:
            return []

    # Determine strategy with fallback
    query_embedding = get_embedding(query) if strategy in ("hybrid", "semantic") else None

    if strategy == "hybrid":
        if query_embedding is not None:
            return _hybrid_search(query, query_embedding, rows, top_k, opts)
        # Fallback: try BM25, then keyword
        logger.info("Embeddings unavailable for hybrid search, falling back to BM25")
        strategy = "bm25"

    if strategy == "semantic":
        if query_embedding is not None:
            return _semantic_search(query_embedding, rows, top_k)
        logger.info("Embeddings unavailable for semantic search, falling back to keyword")
        return _substring_search(query, rows, top_k)

    if strategy == "bm25":
        scored = _bm25_search(query, rows, top_k)
        return [item[1] for item in scored]

    # "keyword" or fallback
    return _substring_search(query, rows, top_k)


def migrate_legacy_documents() -> dict:
    """Ensure user_id column exists with default values.

    This is handled automatically by the PRAGMA check in _get_db(),
    but this function is exposed explicitly for server.py to call
    during startup if needed.
    """
    conn = _get_db()  # triggers migration in _get_db()
    conn.close()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Phase 5: Metadata, tags, collections, stats
# ---------------------------------------------------------------------------

def tag_document(
    doc_id: str,
    tags: list[str],
    user_id: str = "default",
    mode: str = "add",
) -> dict:
    """Add, remove, or set tags on a document.

    Args:
        doc_id: Document identifier.
        tags: List of tag strings.
        user_id: Owner of the document.
        mode: "add" to append, "remove" to remove, "set" to replace.

    Returns:
        {"doc_id": str, "tags": list[str], "status": "ok"}
    """
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT tags FROM document_meta WHERE doc_id = ? AND user_id = ?",
            (doc_id, user_id),
        ).fetchone()
        if not row:
            return {"doc_id": doc_id, "tags": [], "status": "not_found"}

        try:
            current = json.loads(row[0]) if row[0] else []
        except (json.JSONDecodeError, TypeError):
            current = []

        if mode == "set":
            current = list(tags)
        elif mode == "remove":
            current = [t for t in current if t not in tags]
        else:  # "add"
            for t in tags:
                if t not in current:
                    current.append(t)

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE document_meta SET tags = ?, updated_at = ? WHERE doc_id = ? AND user_id = ?",
            (json.dumps(current), now, doc_id, user_id),
        )
        conn.commit()
        return {"doc_id": doc_id, "tags": current, "status": "ok"}
    finally:
        conn.close()


def get_document_meta(doc_id: str, user_id: str = "default") -> Optional[dict]:
    """Get metadata for a specific document. Returns None if not found."""
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        row = conn.execute(
            """SELECT doc_id, title, source_url, tags, category, file_type,
                      file_size, page_count, created_at, updated_at
               FROM document_meta WHERE doc_id = ? AND user_id = ?""",
            (doc_id, user_id),
        ).fetchone()
        if not row:
            return None
        try:
            tags = json.loads(row[3]) if row[3] else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        return {
            "doc_id": row[0], "title": row[1], "source_url": row[2],
            "tags": tags, "category": row[4], "file_type": row[5],
            "file_size": row[6], "page_count": row[7],
            "created_at": row[8], "updated_at": row[9],
        }
    finally:
        conn.close()


def get_collection_stats(user_id: str = "default") -> dict:
    """Get aggregate statistics for a user's document collection."""
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        doc_count = conn.execute(
            "SELECT COUNT(DISTINCT doc_id) FROM document_chunks WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        chunk_count = conn.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

        # File type breakdown
        type_rows = conn.execute(
            "SELECT file_type, COUNT(*) FROM document_meta WHERE user_id = ? GROUP BY file_type",
            (user_id,),
        ).fetchall()
        by_file_type = {r[0]: r[1] for r in type_rows if r[0]}

        # Total size
        total_size = conn.execute(
            "SELECT COALESCE(SUM(file_size), 0) FROM document_meta WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

        # All tags
        tag_rows = conn.execute(
            "SELECT tags FROM document_meta WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        all_tags = set()
        for (raw,) in tag_rows:
            try:
                for t in json.loads(raw or "[]"):
                    all_tags.add(t)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "total_documents": doc_count,
            "total_chunks": chunk_count,
            "total_size_bytes": total_size,
            "by_file_type": by_file_type,
            "all_tags": sorted(all_tags),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 7: Batch ingestion & re-embedding
# ---------------------------------------------------------------------------

def ingest_documents_batch(
    file_paths: list[str],
    user_id: str = "default",
    max_workers: int = 4,
) -> list[dict]:
    """Ingest multiple documents in parallel.

    Parses and chunks files in parallel, then stores in a single transaction.

    Args:
        file_paths: List of file paths to ingest.
        user_id: Owner of these documents.
        max_workers: Maximum parallel workers for parsing.

    Returns:
        List of ingestion result dicts.
    """
    if not file_paths:
        return []

    def _parse_one(fp: str) -> tuple[str, Optional[str], Optional[list[str]]]:
        try:
            text = parse_file(fp)
            if not text.strip():
                return fp, None, None
            chunks = chunk_text(text)
            return fp, text, chunks
        except Exception as e:
            logger.warning("Batch ingest: failed to parse %s: %s", fp, e)
            return fp, None, None

    # Parse in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        parsed = list(pool.map(_parse_one, file_paths))

    results = []
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        for fp, text, chunks in parsed:
            if not chunks:
                results.append({
                    "doc_id": "", "doc_name": Path(fp).name,
                    "chunks": 0, "status": "empty" if text is None else "error",
                })
                continue

            doc_id = secrets.token_hex(4)
            doc_name = Path(fp).name
            now = datetime.now(timezone.utc).isoformat()
            file_ext = Path(fp).suffix.lower()
            try:
                file_size = Path(fp).stat().st_size
            except OSError:
                file_size = 0

            for i, chunk_content in enumerate(chunks):
                chunk_id = f"{doc_id}_{i}"
                embedding = get_embedding(chunk_content)
                blob = _serialize_embedding(embedding) if embedding else None
                conn.execute(
                    """INSERT OR REPLACE INTO document_chunks
                       (id, doc_id, doc_name, chunk_index, total_chunks, content, created_at, embedding, user_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (chunk_id, doc_id, doc_name, i, len(chunks), encrypt_field(chunk_content), now, blob, user_id),
                )

            conn.execute("""
                INSERT OR REPLACE INTO document_meta
                (doc_id, title, file_type, file_size, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (doc_id, doc_name, file_ext, file_size, user_id, now, now))

            results.append({
                "doc_id": doc_id, "doc_name": doc_name,
                "chunks": len(chunks), "status": "ok",
                "file_type": file_ext, "file_size": file_size,
            })

        conn.commit()
        _invalidate_ann_index(user_id)
    finally:
        conn.close()

    return results


def reembed_documents(
    user_id: str = "default",
    batch_size: int = 100,
    progress_callback=None,
) -> dict:
    """Re-embed all chunks for a user with the current model.

    Args:
        user_id: Owner whose chunks to re-embed.
        batch_size: Chunks to process per batch.
        progress_callback: Optional callable(done, total) for progress.

    Returns:
        {"chunks_processed": int, "status": "ok"}
    """
    user_id = sanitize_user_id(user_id)
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT id, content FROM document_chunks WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        total = len(rows)
        done = 0

        for batch_start in range(0, total, batch_size):
            batch = rows[batch_start:batch_start + batch_size]
            for chunk_id, encrypted_content in batch:
                content = decrypt_field(encrypted_content)
                embedding = get_embedding(content)
                blob = _serialize_embedding(embedding) if embedding else None
                conn.execute(
                    "UPDATE document_chunks SET embedding = ? WHERE id = ?",
                    (blob, chunk_id),
                )
                done += 1
            conn.commit()
            if progress_callback:
                progress_callback(done, total)

        _invalidate_ann_index(user_id)
        return {"chunks_processed": done, "status": "ok"}
    finally:
        conn.close()


def search_documents_multihop(
    query: str,
    user_id: str = "default",
    top_k: int = 5,
    expand: bool = True,
    hops: int = 2,
    search_options: Optional[dict] = None,
    filters: Optional[dict] = None,
) -> list[dict]:
    """Multi-hop search with optional query expansion (Phase 4).

    Hop 1: Search with original query (and expanded variants if expand=True).
    Hop 2: Extract key entities from hop 1 results, search again.
    Deduplicate across all hops.

    Args:
        query: Original search query.
        user_id: Owner whose documents to search.
        top_k: Maximum results to return.
        expand: Whether to expand the query into variants.
        hops: Number of search hops (1 = single, 2 = multi-hop).
        search_options: Passed through to search_documents().
        filters: Metadata filters to apply.

    Returns:
        Deduplicated, scored list of result dicts.
    """
    from .query import expand_query_simple, extract_key_terms, deduplicate_results

    # Hop 1: search with expanded variants
    all_results = []
    if expand:
        variants = expand_query_simple(query)
    else:
        variants = [query]

    for variant in variants:
        results = search_documents(
            variant, user_id=user_id, top_k=top_k,
            strategy="hybrid", search_options=search_options, filters=filters,
        )
        all_results.extend(results)

    if hops >= 2 and all_results:
        # Extract key terms from hop 1 content
        combined_text = " ".join(r.get("content", "")[:500] for r in all_results[:5])
        key_terms = extract_key_terms(combined_text, max_terms=5)
        if key_terms:
            hop2_query = " ".join(key_terms)
            hop2_results = search_documents(
                hop2_query, user_id=user_id, top_k=top_k,
                strategy="hybrid", search_options=search_options, filters=filters,
            )
            all_results.extend(hop2_results)

    return deduplicate_results(all_results)[:top_k]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
            "_bm25_score": 0.0,
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[2] for item in scored[:top_k]]


def _bm25_search(
    query: str,
    rows: list[tuple],
    top_k: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[float, dict]]:
    """BM25 keyword scoring across document chunks (pure Python).

    Args:
        query: Search query string.
        rows: Decrypted row tuples (row_id, doc_id, doc_name, chunk_idx, total,
              content, created_at, emb_blob).
        top_k: Maximum results to return.
        k1: Term frequency saturation parameter.
        b: Length normalization parameter.

    Returns:
        List of (bm25_score, result_dict) sorted by score descending.
    """
    query_terms = re.findall(r"\b\w+\b", query.lower())
    if not query_terms or not rows:
        return []

    # Tokenize all documents
    doc_tokens = []
    for r in rows:
        doc_tokens.append(re.findall(r"\b\w+\b", r[5].lower()))

    doc_lengths = [len(t) for t in doc_tokens]
    avg_dl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1

    N = len(rows)
    # IDF for each query term
    idf = {}
    for term in query_terms:
        df = sum(1 for tokens in doc_tokens if term in tokens)
        idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    scored = []
    for i, row in enumerate(rows):
        tf = Counter(doc_tokens[i])
        dl = doc_lengths[i]
        score = 0.0
        for term in query_terms:
            term_tf = tf.get(term, 0)
            if term_tf == 0:
                continue
            numerator = term_tf * (k1 + 1)
            denominator = term_tf + k1 * (1 - b + b * dl / avg_dl)
            score += idf.get(term, 0) * numerator / denominator

        if score > 0:
            row_id, doc_id, doc_name, chunk_idx, total, content, created_at, _ = row
            scored.append((score, {
                "id": row_id,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "chunk_index": chunk_idx,
                "total_chunks": total,
                "content": content,
                "created_at": created_at,
                "_score": round(score, 4),
                "_semantic_score": 0.0,
                "_bm25_score": round(score, 4),
            }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def _hybrid_search(
    query: str,
    query_embedding: list[float],
    rows: list[tuple],
    top_k: int,
    opts: dict,
) -> list[dict]:
    """Combine semantic similarity, BM25, and temporal decay.

    Final score = alpha * semantic_norm + beta * bm25_norm + gamma * decay.
    Optionally reranks with a cross-encoder.
    """
    alpha = opts.get("alpha", 0.6)
    beta = opts.get("beta", 0.25)
    gamma = opts.get("gamma", 0.15)
    do_rerank = opts.get("rerank", False)

    # Wider retrieval for merge
    candidate_k = min(top_k * 4, len(rows))

    # Get semantic scores
    semantic_map: dict[str, tuple[float, dict]] = {}
    for row_id, doc_id, doc_name, chunk_idx, total, content, created_at, emb_blob in rows:
        if emb_blob:
            chunk_emb = _deserialize_embedding(emb_blob)
            sem_score = cosine_similarity(query_embedding, chunk_emb)
        else:
            chunk_emb = get_embedding(content)
            if chunk_emb is None:
                sem_score = 0.0
            else:
                sem_score = cosine_similarity(query_embedding, chunk_emb)

        result = {
            "id": row_id, "doc_id": doc_id, "doc_name": doc_name,
            "chunk_index": chunk_idx, "total_chunks": total,
            "content": content, "created_at": created_at,
        }
        semantic_map[row_id] = (sem_score, result)

    # Get BM25 scores
    bm25_results = _bm25_search(query, rows, candidate_k)
    bm25_map: dict[str, float] = {r[1]["id"]: r[0] for r in bm25_results}

    # Collect all candidate IDs
    all_ids = set(semantic_map.keys()) | set(bm25_map.keys())

    # Min-max normalization helpers
    sem_scores = [semantic_map[cid][0] for cid in all_ids if cid in semantic_map]
    bm25_scores = [bm25_map[cid] for cid in all_ids if cid in bm25_map]

    sem_min = min(sem_scores) if sem_scores else 0
    sem_max = max(sem_scores) if sem_scores else 1
    sem_range = sem_max - sem_min if sem_max != sem_min else 1.0

    bm25_min = min(bm25_scores) if bm25_scores else 0
    bm25_max = max(bm25_scores) if bm25_scores else 1
    bm25_range = bm25_max - bm25_min if bm25_max != bm25_min else 1.0

    # Compute final scores
    scored = []
    for cid in all_ids:
        sem_score, result = semantic_map.get(cid, (0.0, None))
        if result is None:
            continue
        bm25_score = bm25_map.get(cid, 0.0)

        sem_norm = (sem_score - sem_min) / sem_range
        bm25_norm = (bm25_score - bm25_min) / bm25_range
        decay = _compute_decay(result["created_at"])

        final = alpha * sem_norm + beta * bm25_norm + gamma * decay

        result["_score"] = round(final, 4)
        result["_semantic_score"] = round(sem_score, 4)
        result["_bm25_score"] = round(bm25_score, 4)
        scored.append((final, result))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [item[1] for item in scored[:top_k * 2]]  # Over-fetch for reranking

    # Optional cross-encoder reranking
    if do_rerank and results:
        results = _rerank_with_cross_encoder(query, results, top_k)
    else:
        results = results[:top_k]

    return results


def _rerank_with_cross_encoder(
    query: str, results: list[dict], top_k: int = 5,
) -> list[dict]:
    """Rerank results using a cross-encoder model.

    Falls back to original ordering if the model is unavailable.
    """
    global _cross_encoder, _cross_encoder_load_attempted

    if _cross_encoder is None and not _cross_encoder_load_attempted:
        _cross_encoder_load_attempted = True
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info("Cross-encoder loaded for reranking")
        except (ImportError, Exception) as e:
            logger.info("Cross-encoder unavailable: %s", e)
            _cross_encoder = None

    if _cross_encoder is None:
        return results[:top_k]

    try:
        pairs = [(query, r["content"][:1000]) for r in results]
        scores = _cross_encoder.predict(pairs)
        for result, score in zip(results, scores):
            result["_pre_rerank_score"] = result["_score"]
            result["_score"] = round(float(score), 4)
        results.sort(key=lambda x: x["_score"], reverse=True)
    except Exception as e:
        logger.warning("Cross-encoder reranking failed: %s", e)

    return results[:top_k]


def _apply_filters(
    rows: list[tuple], user_id: str, filters: dict,
) -> list[tuple]:
    """Filter rows by metadata (tags, file_type, doc_ids, category)."""
    filter_tags = filters.get("tags")
    filter_type = filters.get("file_type")
    filter_doc_ids = filters.get("doc_ids")
    filter_category = filters.get("category")

    if not any([filter_tags, filter_type, filter_doc_ids, filter_category]):
        return rows

    # Fast path: doc_ids filter only
    if filter_doc_ids and not any([filter_tags, filter_type, filter_category]):
        doc_set = set(filter_doc_ids)
        return [r for r in rows if r[1] in doc_set]

    # Need metadata lookup
    conn = _get_db()
    try:
        meta_rows = conn.execute(
            "SELECT doc_id, tags, category, file_type FROM document_meta WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    allowed_docs = set()
    for doc_id, raw_tags, cat, ftype in meta_rows:
        if filter_doc_ids and doc_id not in filter_doc_ids:
            continue
        if filter_type and ftype != filter_type:
            continue
        if filter_category and cat != filter_category:
            continue
        if filter_tags:
            try:
                doc_tags = json.loads(raw_tags or "[]")
            except (json.JSONDecodeError, TypeError):
                doc_tags = []
            if not all(t in doc_tags for t in filter_tags):
                continue
        allowed_docs.add(doc_id)

    return [r for r in rows if r[1] in allowed_docs]


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
                "_bm25_score": 0.0,
            })

    return results[:top_k]


# ---------------------------------------------------------------------------
# Phase 7: ANN Index (optional FAISS integration)
# ---------------------------------------------------------------------------

def _check_ann_available() -> bool:
    """Check if FAISS is available for ANN search."""
    global _ann_available
    if _ann_available is not None:
        return _ann_available
    try:
        import faiss  # noqa: F401
        _ann_available = True
    except ImportError:
        _ann_available = False
        logger.debug("faiss not installed; using linear scan for search")
    return _ann_available


class ANNIndex:
    """Manages a FAISS index for approximate nearest-neighbor search."""

    def __init__(self, dim: int = 384):
        self.dim = dim
        self._index = None
        self._id_map: list[str] = []
        self._dirty = True

    def build(self, rows: list[tuple]) -> None:
        """Build the ANN index from chunk rows with embeddings."""
        import faiss
        import numpy as np

        embeddings = []
        ids = []
        for row_id, _, _, _, _, _, _, emb_blob in rows:
            if emb_blob:
                emb = _deserialize_embedding(emb_blob)
                embeddings.append(emb)
                ids.append(row_id)

        if not embeddings:
            self._index = None
            self._dirty = False
            return

        matrix = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(matrix)

        n = len(embeddings)
        if n < 10000:
            self._index = faiss.IndexFlatIP(self.dim)
        else:
            nlist = min(int(n ** 0.5), 256)
            quantizer = faiss.IndexFlatIP(self.dim)
            self._index = faiss.IndexIVFFlat(quantizer, self.dim, nlist)
            self._index.train(matrix)

        self._index.add(matrix)
        self._id_map = ids
        self._dirty = False

    def search(self, query_embedding: list[float], top_k: int = 20) -> list[tuple[str, float]]:
        """Search the ANN index. Returns (chunk_id, score) tuples."""
        import faiss
        import numpy as np

        if self._index is None or self._index.ntotal == 0:
            return []

        q = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(q)
        scores, indices = self._index.search(q, min(top_k, self._index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self._id_map):
                results.append((self._id_map[idx], float(score)))
        return results

    def invalidate(self) -> None:
        """Mark the index as needing rebuild."""
        self._dirty = True

    @property
    def needs_rebuild(self) -> bool:
        return self._dirty


def _invalidate_ann_index(user_id: str) -> None:
    """Mark the ANN index for a user as dirty."""
    if user_id in _ann_indices:
        _ann_indices[user_id].invalidate()
