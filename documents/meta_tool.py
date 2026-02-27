"""manage_documents meta-tool — RAG document ingestion and search for Rain."""

from .storage import (
    ingest_document,
    ingest_documents_batch,
    list_documents,
    remove_document,
    search_documents,
    search_documents_multihop,
    get_document_chunks,
    get_document_meta,
    get_collection_stats,
    tag_document,
    reembed_documents,
    migrate_legacy_documents,
)

MANAGE_DOCUMENTS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_documents",
        "description": (
            "Ingest, search, and manage documents for RAG (Retrieval-Augmented Generation). "
            "Use this when the user says 'read this document', 'ingest this file', "
            "'search in my docs', 'what does the spec say about...', or wants to work "
            "with their files as a knowledge base. "
            "Ingested documents use semantic chunking (respects markdown headers/sections) "
            "and are stored with semantic embeddings for fast retrieval. "
            "Supports hybrid search (BM25 + semantic + temporal decay), query expansion, "
            "document tagging, and collection statistics. "
            "Supported formats: .txt, .md, .pdf, .docx, .csv, .tsv, .html, .json, .epub, "
            "and source code (.py, .js, .ts, .java, .go, .rs, .c, .cpp, etc.)"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "ingest", "search", "list", "remove", "show",
                        "tag", "stats", "batch_ingest", "reembed",
                    ],
                    "description": (
                        "Action: 'ingest' a file, 'search' across documents, "
                        "'list' all documents, 'remove' a document, 'show' chunks, "
                        "'tag' add/remove tags, 'stats' show collection statistics, "
                        "'batch_ingest' multiple files, 'reembed' re-generate embeddings"
                    ),
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to ingest (required for 'ingest')",
                },
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths for 'batch_ingest'",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for 'search')",
                },
                "doc_id": {
                    "type": "string",
                    "description": "Document ID (required for 'remove', 'show', 'tag')",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results for search (default: 5, max: 20)",
                },
                "strategy": {
                    "type": "string",
                    "enum": ["hybrid", "semantic", "bm25", "keyword"],
                    "description": "Search strategy (default: hybrid)",
                },
                "rerank": {
                    "type": "boolean",
                    "description": "Use cross-encoder reranking for higher accuracy (slower)",
                },
                "expand": {
                    "type": "boolean",
                    "description": "Expand query into multiple search variants for better recall",
                },
                "multihop": {
                    "type": "boolean",
                    "description": "Use multi-hop search: first search, extract entities, search again",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to add/remove/set (for 'tag' action)",
                },
                "tag_mode": {
                    "type": "string",
                    "enum": ["add", "remove", "set"],
                    "description": "Tag operation mode (default: add)",
                },
                "filters": {
                    "type": "object",
                    "description": "Search filters: {tags: [...], file_type: '.pdf', category: '...', doc_ids: [...]}",
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_manage_documents(args: dict, cwd: str) -> dict:
    """Handle manage_documents tool calls from Rain.

    The caller may inject ``_user_id`` into *args* for per-user isolation.
    If absent, falls back to ``"default"`` for backward compatibility.
    """
    action = args.get("action", "")
    user_id = args.pop("_user_id", "default")

    try:
        handler = _ACTION_HANDLERS.get(action)
        if handler:
            return handler(args, cwd, user_id)
        return {"content": f"Unknown action: {action}", "is_error": True}
    except FileNotFoundError as e:
        return {"content": f"File not found: {e}", "is_error": True}
    except (ValueError, ImportError) as e:
        return {"content": str(e), "is_error": True}
    except Exception as e:
        return {"content": f"Error: {e}", "is_error": True}


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _action_ingest(args: dict, cwd: str, user_id: str) -> dict:
    file_path = args.get("file_path", "").strip()
    if not file_path:
        return {"content": "Error: 'file_path' is required for ingest action", "is_error": True}

    path = _validate_path(file_path, cwd)
    if isinstance(path, dict):
        return path  # Error response

    result = ingest_document(str(path), user_id=user_id)

    if result["status"] == "empty":
        return {"content": f"Document '{result['doc_name']}' is empty or has no extractable text.", "is_error": True}

    return {
        "content": (
            f"Document ingested: '{result['doc_name']}'\n"
            f"  Doc ID: {result['doc_id']}\n"
            f"  Chunks: {result['chunks']}\n"
            f"  Status: {result['status']}"
        ),
        "is_error": False,
    }


def _action_batch_ingest(args: dict, cwd: str, user_id: str) -> dict:
    file_paths = args.get("file_paths", [])
    if not file_paths:
        return {"content": "Error: 'file_paths' is required for batch_ingest", "is_error": True}

    validated = []
    for fp in file_paths:
        path = _validate_path(fp, cwd)
        if isinstance(path, dict):
            continue  # Skip invalid paths
        validated.append(str(path))

    if not validated:
        return {"content": "No valid file paths to ingest.", "is_error": True}

    results = ingest_documents_batch(validated, user_id=user_id)

    lines = [f"Batch ingestion results ({len(results)} files):"]
    for r in results:
        status = r["status"]
        if status == "ok":
            lines.append(f"  ✓ {r['doc_name']} → {r['chunks']} chunks (id: {r['doc_id']})")
        else:
            lines.append(f"  ✗ {r['doc_name']} → {status}")

    return {"content": "\n".join(lines), "is_error": False}


def _action_search(args: dict, _cwd: str, user_id: str) -> dict:
    query = args.get("query", "").strip()
    if not query:
        return {"content": "Error: 'query' is required for search action", "is_error": True}

    top_k = min(args.get("top_k", 5), 20)
    strategy = args.get("strategy", "hybrid")
    rerank = args.get("rerank", False)
    expand = args.get("expand", False)
    multihop = args.get("multihop", False)
    filters = args.get("filters")

    search_opts = {"rerank": rerank} if rerank else None

    if expand or multihop:
        results = search_documents_multihop(
            query, user_id=user_id, top_k=top_k,
            expand=expand, hops=2 if multihop else 1,
            search_options=search_opts, filters=filters,
        )
    else:
        results = search_documents(
            query, user_id=user_id, top_k=top_k,
            strategy=strategy, search_options=search_opts, filters=filters,
        )

    if not results:
        return {"content": f"No document chunks matching '{query}'.", "is_error": False}

    lines = [f"Found {len(results)} relevant chunks for '{query}':"]
    for r in results:
        score_parts = [f"score: {r.get('_score', 0):.3f}"]
        if r.get("_semantic_score"):
            score_parts.append(f"sem: {r['_semantic_score']:.3f}")
        if r.get("_bm25_score"):
            score_parts.append(f"bm25: {r['_bm25_score']:.3f}")
        score_str = ", ".join(score_parts)

        lines.append(
            f"\n--- [{r['doc_name']}, chunk {r['chunk_index'] + 1}/{r['total_chunks']}] "
            f"({score_str}) ---"
        )
        content = r["content"]
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(content)

    return {"content": "\n".join(lines), "is_error": False}


def _action_list(_args: dict, _cwd: str, user_id: str) -> dict:
    docs = list_documents(user_id=user_id)
    if not docs:
        return {"content": "No documents ingested yet.", "is_error": False}

    lines = [f"Ingested documents ({len(docs)} total):"]
    for d in docs:
        tags_str = f" [{', '.join(d['tags'])}]" if d.get("tags") else ""
        lines.append(
            f"  - {d['doc_name']} (id: {d['doc_id']}, "
            f"{d['chunks']} chunks, ingested: {d['created_at'][:10]}){tags_str}"
        )

    return {"content": "\n".join(lines), "is_error": False}


def _action_remove(args: dict, _cwd: str, user_id: str) -> dict:
    doc_id = args.get("doc_id", "").strip()
    if not doc_id:
        return {"content": "Error: 'doc_id' is required for remove action", "is_error": True}

    if remove_document(doc_id, user_id=user_id):
        return {"content": f"Document '{doc_id}' removed.", "is_error": False}
    return {"content": f"Document '{doc_id}' not found.", "is_error": True}


def _action_show(args: dict, _cwd: str, user_id: str) -> dict:
    doc_id = args.get("doc_id", "").strip()
    if not doc_id:
        return {"content": "Error: 'doc_id' is required for show action", "is_error": True}

    chunks = get_document_chunks(doc_id, user_id=user_id)
    if not chunks:
        return {"content": f"Document '{doc_id}' not found.", "is_error": True}

    doc_name = chunks[0]["doc_name"]
    meta = get_document_meta(doc_id, user_id=user_id)

    lines = [f"Document: {doc_name} (id: {doc_id}, {len(chunks)} chunks)"]
    if meta:
        if meta.get("tags"):
            lines.append(f"  Tags: {', '.join(meta['tags'])}")
        if meta.get("category"):
            lines.append(f"  Category: {meta['category']}")
        if meta.get("file_type"):
            lines.append(f"  Type: {meta['file_type']}")

    for c in chunks:
        lines.append(f"\n--- Chunk {c['chunk_index'] + 1}/{c['total_chunks']} ---")
        content = c["content"]
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(content)

    return {"content": "\n".join(lines), "is_error": False}


def _action_tag(args: dict, _cwd: str, user_id: str) -> dict:
    doc_id = args.get("doc_id", "").strip()
    if not doc_id:
        return {"content": "Error: 'doc_id' is required for tag action", "is_error": True}

    tags = args.get("tags", [])
    if not tags:
        return {"content": "Error: 'tags' is required for tag action", "is_error": True}

    mode = args.get("tag_mode", "add")
    result = tag_document(doc_id, tags, user_id=user_id, mode=mode)

    if result["status"] == "not_found":
        return {"content": f"Document '{doc_id}' not found.", "is_error": True}

    return {
        "content": f"Tags updated for '{doc_id}': {', '.join(result['tags'])}",
        "is_error": False,
    }


def _action_stats(_args: dict, _cwd: str, user_id: str) -> dict:
    stats = get_collection_stats(user_id=user_id)

    lines = [
        "Document collection statistics:",
        f"  Documents: {stats['total_documents']}",
        f"  Chunks: {stats['total_chunks']}",
        f"  Total size: {_format_size(stats['total_size_bytes'])}",
    ]
    if stats["by_file_type"]:
        type_str = ", ".join(f"{k}: {v}" for k, v in stats["by_file_type"].items())
        lines.append(f"  By type: {type_str}")
    if stats["all_tags"]:
        lines.append(f"  Tags: {', '.join(stats['all_tags'])}")

    return {"content": "\n".join(lines), "is_error": False}


def _action_reembed(_args: dict, _cwd: str, user_id: str) -> dict:
    result = reembed_documents(user_id=user_id)
    return {
        "content": f"Re-embedded {result['chunks_processed']} chunks. Status: {result['status']}",
        "is_error": False,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_path(file_path: str, cwd: str):
    """Validate a file path for ingestion. Returns Path or error dict."""
    from pathlib import Path

    path = Path(file_path)
    if not path.is_absolute():
        path = Path(cwd) / path

    if path.is_symlink():
        return {"content": "Access denied: symbolic links are not allowed", "is_error": True}

    path = path.resolve()

    home_dir = Path.home().resolve()
    cwd_dir = Path(cwd).resolve()
    try:
        path.relative_to(home_dir)
        _path_allowed = True
    except ValueError:
        try:
            path.relative_to(cwd_dir)
            _path_allowed = True
        except ValueError:
            _path_allowed = False
    if not _path_allowed:
        return {"content": "Access denied: path is outside allowed directory", "is_error": True}

    _sensitive_dirs = [
        home_dir / ".rain-assistant",
        home_dir / ".ssh",
        home_dir / ".aws",
        home_dir / ".gnupg",
        home_dir / ".config",
        home_dir / ".kube",
        home_dir / ".docker",
    ]
    for sensitive in _sensitive_dirs:
        try:
            path.relative_to(sensitive)
            return {"content": "Access denied: path is inside a sensitive directory", "is_error": True}
        except ValueError:
            continue

    from .parser import SUPPORTED_EXTENSIONS as allowed_extensions
    if path.suffix.lower() not in allowed_extensions:
        return {
            "content": f"Unsupported file type: '{path.suffix}'. Allowed: {', '.join(sorted(allowed_extensions))}",
            "is_error": True,
        }

    return path


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# Action dispatch table
_ACTION_HANDLERS = {
    "ingest": _action_ingest,
    "search": _action_search,
    "list": _action_list,
    "remove": _action_remove,
    "show": _action_show,
    "tag": _action_tag,
    "stats": _action_stats,
    "batch_ingest": _action_batch_ingest,
    "reembed": _action_reembed,
}
