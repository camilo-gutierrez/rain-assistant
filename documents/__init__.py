"""Rain Documents — RAG over user documents (PDF, TXT, MD)."""

from .storage import (
    ingest_document,
    list_documents,
    remove_document,
    search_documents,
    get_document_chunks,
    migrate_legacy_documents,
)
from .meta_tool import (
    MANAGE_DOCUMENTS_DEFINITION,
    handle_manage_documents,
)

__all__ = [
    "ingest_document",
    "list_documents",
    "remove_document",
    "search_documents",
    "get_document_chunks",
    "migrate_legacy_documents",
    "MANAGE_DOCUMENTS_DEFINITION",
    "handle_manage_documents",
]
