"""Rain Documents — RAG over user documents.

Supports: .txt, .md, .pdf, .docx, .csv, .tsv, .html, .json, .epub, and source code.
Uses semantic chunking (header-aware for markdown/docx) with overlapping fallback.
Search strategies: hybrid (BM25 + semantic), semantic-only, BM25-only, keyword fallback.
"""

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
from .meta_tool import (
    MANAGE_DOCUMENTS_DEFINITION,
    handle_manage_documents,
)
from .query import (
    expand_query_simple,
    extract_key_terms,
    deduplicate_results,
)

__all__ = [
    "ingest_document",
    "ingest_documents_batch",
    "list_documents",
    "remove_document",
    "search_documents",
    "search_documents_multihop",
    "get_document_chunks",
    "get_document_meta",
    "get_collection_stats",
    "tag_document",
    "reembed_documents",
    "migrate_legacy_documents",
    "MANAGE_DOCUMENTS_DEFINITION",
    "handle_manage_documents",
    "expand_query_simple",
    "extract_key_terms",
    "deduplicate_results",
]
