"""manage_documents meta-tool — RAG document ingestion and search for Rain."""

from .storage import (
    ingest_document,
    list_documents,
    remove_document,
    search_documents,
    get_document_chunks,
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
            "Ingested documents are chunked and stored with semantic embeddings for fast retrieval. "
            "Supported formats: .txt, .md, .pdf"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["ingest", "search", "list", "remove", "show"],
                    "description": (
                        "Action: 'ingest' a file, 'search' across documents, "
                        "'list' all documents, 'remove' a document, 'show' chunks of a document"
                    ),
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to ingest (required for 'ingest'). Supports .txt, .md, .pdf",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for 'search')",
                },
                "doc_id": {
                    "type": "string",
                    "description": "Document ID (required for 'remove' and 'show')",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results for search (default: 5, max: 20)",
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
    user_id = args.get("_user_id", "default")

    try:
        if action == "ingest":
            return _action_ingest(args, cwd, user_id)
        elif action == "search":
            return _action_search(args, user_id)
        elif action == "list":
            return _action_list(user_id)
        elif action == "remove":
            return _action_remove(args, user_id)
        elif action == "show":
            return _action_show(args, user_id)
        else:
            return {"content": f"Unknown action: {action}", "is_error": True}
    except FileNotFoundError as e:
        return {"content": f"File not found: {e}", "is_error": True}
    except ValueError as e:
        return {"content": str(e), "is_error": True}
    except ImportError as e:
        return {"content": str(e), "is_error": True}
    except Exception as e:
        return {"content": f"Error: {e}", "is_error": True}


def _action_ingest(args: dict, cwd: str, user_id: str) -> dict:
    file_path = args.get("file_path", "").strip()
    if not file_path:
        return {"content": "Error: 'file_path' is required for ingest action", "is_error": True}

    from pathlib import Path
    path = Path(file_path)
    if not path.is_absolute():
        path = Path(cwd) / path

    # Resolve to canonical path to prevent path traversal (e.g. ../../etc/passwd)
    path = path.resolve()

    # Validate the resolved path is under the user's home directory or cwd
    home_dir = Path.home().resolve()
    cwd_dir = Path(cwd).resolve()
    if not (str(path).startswith(str(home_dir)) or str(path).startswith(str(cwd_dir))):
        return {"content": "Access denied: path is outside allowed directory", "is_error": True}

    # Validate file extension before proceeding
    allowed_extensions = {".txt", ".md", ".pdf"}
    if path.suffix.lower() not in allowed_extensions:
        return {
            "content": f"Unsupported file type: '{path.suffix}'. Allowed: {', '.join(sorted(allowed_extensions))}",
            "is_error": True,
        }

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


def _action_search(args: dict, user_id: str) -> dict:
    query = args.get("query", "").strip()
    if not query:
        return {"content": "Error: 'query' is required for search action", "is_error": True}

    top_k = min(args.get("top_k", 5), 20)
    results = search_documents(query, user_id=user_id, top_k=top_k)

    if not results:
        return {"content": f"No document chunks matching '{query}'.", "is_error": False}

    lines = [f"Found {len(results)} relevant chunks for '{query}':"]
    for r in results:
        score = r.get("_score", 0)
        lines.append(
            f"\n--- [{r['doc_name']}, chunk {r['chunk_index'] + 1}/{r['total_chunks']}] "
            f"(score: {score:.3f}) ---"
        )
        # Truncate very long chunks for display
        content = r["content"]
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(content)

    return {"content": "\n".join(lines), "is_error": False}


def _action_list(user_id: str) -> dict:
    docs = list_documents(user_id=user_id)
    if not docs:
        return {"content": "No documents ingested yet.", "is_error": False}

    lines = [f"Ingested documents ({len(docs)} total):"]
    for d in docs:
        lines.append(
            f"  - {d['doc_name']} (id: {d['doc_id']}, "
            f"{d['chunks']} chunks, ingested: {d['created_at'][:10]})"
        )

    return {"content": "\n".join(lines), "is_error": False}


def _action_remove(args: dict, user_id: str) -> dict:
    doc_id = args.get("doc_id", "").strip()
    if not doc_id:
        return {"content": "Error: 'doc_id' is required for remove action", "is_error": True}

    if remove_document(doc_id, user_id=user_id):
        return {"content": f"Document '{doc_id}' removed.", "is_error": False}
    return {"content": f"Document '{doc_id}' not found.", "is_error": True}


def _action_show(args: dict, user_id: str) -> dict:
    doc_id = args.get("doc_id", "").strip()
    if not doc_id:
        return {"content": "Error: 'doc_id' is required for show action", "is_error": True}

    chunks = get_document_chunks(doc_id, user_id=user_id)
    if not chunks:
        return {"content": f"Document '{doc_id}' not found.", "is_error": True}

    doc_name = chunks[0]["doc_name"]
    lines = [f"Document: {doc_name} (id: {doc_id}, {len(chunks)} chunks)"]
    for c in chunks:
        lines.append(f"\n--- Chunk {c['chunk_index'] + 1}/{c['total_chunks']} ---")
        content = c["content"]
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(content)

    return {"content": "\n".join(lines), "is_error": False}
