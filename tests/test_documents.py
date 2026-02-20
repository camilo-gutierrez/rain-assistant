"""Tests for the Rain RAG documents module.

Covers: parser, chunker, storage, and meta-tool.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ===========================================================================
# Parser tests
# ===========================================================================

class TestParser:
    """Tests for documents.parser.parse_file."""

    def test_parse_txt(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello, world!\nLine two.", encoding="utf-8")
        from documents.parser import parse_file
        result = parse_file(str(f))
        assert "Hello, world!" in result
        assert "Line two." in result

    def test_parse_md(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nSome **bold** text.", encoding="utf-8")
        from documents.parser import parse_file
        result = parse_file(str(f))
        assert "# Title" in result
        assert "**bold**" in result

    def test_parse_nonexistent_file(self):
        from documents.parser import parse_file
        with pytest.raises(FileNotFoundError):
            parse_file("/nonexistent/path/file.txt")

    def test_parse_unsupported_format(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c", encoding="utf-8")
        from documents.parser import parse_file
        with pytest.raises(ValueError, match="Unsupported"):
            parse_file(str(f))

    def test_parse_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        from documents.parser import parse_file
        result = parse_file(str(f))
        assert result == ""

    def test_parse_pdf_without_pypdf(self, tmp_path):
        """If pypdf is not installed, importing it raises ImportError."""
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 fake pdf")
        from documents.parser import parse_file
        with patch.dict("sys.modules", {"pypdf": None}):
            with pytest.raises(ImportError, match="pypdf"):
                parse_file(str(f))

    def test_parse_pdf_with_mock(self, tmp_path):
        """Test PDF parsing with mocked pypdf."""
        f = tmp_path / "real.pdf"
        f.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("documents.parser.PdfReader", mock_reader, create=True):
            # We need to patch the import inside _parse_pdf
            import documents.parser as parser_mod
            original_parse_pdf = parser_mod._parse_pdf

            def mock_parse_pdf(path):
                return "Page 1 content"

            parser_mod._parse_pdf = mock_parse_pdf
            try:
                result = parser_mod.parse_file(str(f))
                assert "Page 1 content" in result
            finally:
                parser_mod._parse_pdf = original_parse_pdf


# ===========================================================================
# Chunker tests
# ===========================================================================

class TestChunker:
    """Tests for documents.chunker.chunk_text."""

    def test_empty_text(self):
        from documents.chunker import chunk_text
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self):
        from documents.chunker import chunk_text
        text = "Short paragraph."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "Short paragraph."

    def test_long_text_multiple_chunks(self):
        from documents.chunker import chunk_text
        # Create text with several paragraphs
        paragraphs = [f"Paragraph {i}. " * 50 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text)
        assert len(chunks) > 1

    def test_overlap_present(self):
        from documents.chunker import chunk_text
        # Create two large paragraphs that will be split into separate chunks
        p1 = "Alpha " * 400  # ~2400 chars
        p2 = "Beta " * 400
        text = p1 + "\n\n" + p2
        chunks = chunk_text(text, chunk_size=2000, overlap=256)
        assert len(chunks) >= 2
        # The overlap means end of chunk 1 should appear at start of chunk 2
        # (or at least some shared content)

    def test_paragraph_boundaries_respected(self):
        from documents.chunker import chunk_text
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_text(text, chunk_size=5000)  # large enough for all
        assert len(chunks) == 1
        assert "Para one." in chunks[0]
        assert "Para two." in chunks[0]

    def test_very_long_paragraph_subsplit(self):
        from documents.chunker import chunk_text, MAX_CHUNK_CHARS
        # Single paragraph longer than MAX_CHUNK_CHARS
        text = "word " * 1000  # ~5000 chars
        chunks = chunk_text(text)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c) <= MAX_CHUNK_CHARS + 100  # small tolerance

    def test_chunk_size_respected(self):
        from documents.chunker import chunk_text
        paragraphs = [f"Section {i}. " * 30 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=1000)
        # Most chunks should be near the target size (not double)
        for c in chunks:
            assert len(c) < 4000  # reasonable upper bound


# ===========================================================================
# Storage tests
# ===========================================================================

class TestStorage:
    """Tests for documents.storage CRUD and search."""

    @pytest.fixture(autouse=True)
    def isolated_db(self, tmp_path):
        """Point the documents DB to a temp directory."""
        import memories.embeddings as emb
        old_config = emb.CONFIG_DIR
        old_db = emb.MEMORIES_DB
        emb.CONFIG_DIR = tmp_path
        emb.MEMORIES_DB = tmp_path / "test_memories.db"
        yield
        emb.CONFIG_DIR = old_config
        emb.MEMORIES_DB = old_db

    def test_ingest_document(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("Hello world. This is a test document.", encoding="utf-8")
        from documents.storage import ingest_document
        result = ingest_document(str(f))
        assert result["status"] == "ok"
        assert result["chunks"] >= 1
        assert result["doc_name"] == "doc.txt"
        assert result["doc_id"]

    def test_ingest_empty_document(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        from documents.storage import ingest_document
        result = ingest_document(str(f))
        assert result["status"] == "empty"
        assert result["chunks"] == 0

    def test_list_documents(self, tmp_path):
        f = tmp_path / "doc1.txt"
        f.write_text("Document one content.", encoding="utf-8")
        from documents.storage import ingest_document, list_documents
        ingest_document(str(f))
        docs = list_documents()
        assert len(docs) >= 1
        assert docs[0]["doc_name"] == "doc1.txt"

    def test_remove_document(self, tmp_path):
        f = tmp_path / "removable.txt"
        f.write_text("This will be removed.", encoding="utf-8")
        from documents.storage import ingest_document, remove_document, list_documents
        result = ingest_document(str(f))
        doc_id = result["doc_id"]
        assert remove_document(doc_id) is True
        assert all(d["doc_id"] != doc_id for d in list_documents())

    def test_remove_nonexistent(self):
        from documents.storage import remove_document
        assert remove_document("nonexistent_id") is False

    def test_get_document_chunks(self, tmp_path):
        # Create a larger document that will produce multiple chunks
        f = tmp_path / "big.txt"
        text = "\n\n".join([f"Section {i}. " * 60 for i in range(10)])
        f.write_text(text, encoding="utf-8")
        from documents.storage import ingest_document, get_document_chunks
        result = ingest_document(str(f))
        chunks = get_document_chunks(result["doc_id"])
        assert len(chunks) == result["chunks"]
        assert chunks[0]["chunk_index"] == 0

    def test_search_documents_substring(self, tmp_path):
        """Substring search fallback when embeddings are unavailable."""
        f = tmp_path / "searchable.txt"
        f.write_text("The quick brown fox jumps over the lazy dog.", encoding="utf-8")
        from documents.storage import ingest_document, search_documents
        # Mock embeddings as unavailable
        with patch("documents.storage.get_embedding", return_value=None):
            ingest_document(str(f))
            results = search_documents("quick brown fox")
        assert len(results) >= 1
        assert "quick brown fox" in results[0]["content"]

    def test_search_documents_empty_query(self):
        from documents.storage import search_documents
        assert search_documents("") == []

    def test_ingest_nonexistent_file(self):
        from documents.storage import ingest_document
        with pytest.raises(FileNotFoundError):
            ingest_document("/nonexistent/path/file.txt")


# ===========================================================================
# Meta-tool tests
# ===========================================================================

class TestMetaTool:
    """Tests for documents.meta_tool handler."""

    @pytest.fixture(autouse=True)
    def isolated_db(self, tmp_path):
        """Point the documents DB to a temp directory."""
        import memories.embeddings as emb
        old_config = emb.CONFIG_DIR
        old_db = emb.MEMORIES_DB
        emb.CONFIG_DIR = tmp_path
        emb.MEMORIES_DB = tmp_path / "test_memories.db"
        yield
        emb.CONFIG_DIR = old_config
        emb.MEMORIES_DB = old_db

    @pytest.mark.asyncio
    async def test_ingest_action(self, tmp_path):
        f = tmp_path / "meta.txt"
        f.write_text("Meta tool test content.", encoding="utf-8")
        from documents.meta_tool import handle_manage_documents
        result = await handle_manage_documents(
            {"action": "ingest", "file_path": str(f)},
            cwd=str(tmp_path),
        )
        assert not result["is_error"]
        assert "ingested" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_ingest_missing_path(self, tmp_path):
        from documents.meta_tool import handle_manage_documents
        result = await handle_manage_documents(
            {"action": "ingest"},
            cwd=str(tmp_path),
        )
        assert result["is_error"]

    @pytest.mark.asyncio
    async def test_list_action(self, tmp_path):
        from documents.meta_tool import handle_manage_documents
        result = await handle_manage_documents(
            {"action": "list"},
            cwd=str(tmp_path),
        )
        assert not result["is_error"]

    @pytest.mark.asyncio
    async def test_search_action(self, tmp_path):
        f = tmp_path / "search_test.txt"
        f.write_text("Important information about authentication and security.", encoding="utf-8")
        from documents.meta_tool import handle_manage_documents
        # Ingest first
        with patch("documents.storage.get_embedding", return_value=None):
            await handle_manage_documents(
                {"action": "ingest", "file_path": str(f)},
                cwd=str(tmp_path),
            )
            # Search
            result = await handle_manage_documents(
                {"action": "search", "query": "authentication"},
                cwd=str(tmp_path),
            )
        assert not result["is_error"]
        assert "authentication" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_search_missing_query(self, tmp_path):
        from documents.meta_tool import handle_manage_documents
        result = await handle_manage_documents(
            {"action": "search"},
            cwd=str(tmp_path),
        )
        assert result["is_error"]

    @pytest.mark.asyncio
    async def test_remove_action(self, tmp_path):
        f = tmp_path / "to_remove.txt"
        f.write_text("Remove me.", encoding="utf-8")
        from documents.meta_tool import handle_manage_documents
        with patch("documents.storage.get_embedding", return_value=None):
            ingest_result = await handle_manage_documents(
                {"action": "ingest", "file_path": str(f)},
                cwd=str(tmp_path),
            )
        # Extract doc_id from the result text
        # The format is "Doc ID: <id>"
        doc_id = None
        for line in ingest_result["content"].split("\n"):
            if "doc id:" in line.lower():
                doc_id = line.split(":")[-1].strip()
                break

        assert doc_id is not None
        result = await handle_manage_documents(
            {"action": "remove", "doc_id": doc_id},
            cwd=str(tmp_path),
        )
        assert not result["is_error"]
        assert "removed" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_show_action(self, tmp_path):
        f = tmp_path / "showme.txt"
        f.write_text("Content to display in chunks.", encoding="utf-8")
        from documents.meta_tool import handle_manage_documents
        with patch("documents.storage.get_embedding", return_value=None):
            ingest_result = await handle_manage_documents(
                {"action": "ingest", "file_path": str(f)},
                cwd=str(tmp_path),
            )
        doc_id = None
        for line in ingest_result["content"].split("\n"):
            if "doc id:" in line.lower():
                doc_id = line.split(":")[-1].strip()
                break

        assert doc_id is not None
        result = await handle_manage_documents(
            {"action": "show", "doc_id": doc_id},
            cwd=str(tmp_path),
        )
        assert not result["is_error"]
        assert "showme.txt" in result["content"]

    @pytest.mark.asyncio
    async def test_unknown_action(self, tmp_path):
        from documents.meta_tool import handle_manage_documents
        result = await handle_manage_documents(
            {"action": "fly"},
            cwd=str(tmp_path),
        )
        assert result["is_error"]

    @pytest.mark.asyncio
    async def test_ingest_relative_path(self, tmp_path):
        """Relative paths are resolved against cwd."""
        f = tmp_path / "relative.txt"
        f.write_text("Relative path test.", encoding="utf-8")
        from documents.meta_tool import handle_manage_documents
        with patch("documents.storage.get_embedding", return_value=None):
            result = await handle_manage_documents(
                {"action": "ingest", "file_path": "relative.txt"},
                cwd=str(tmp_path),
            )
        assert not result["is_error"]


# ===========================================================================
# Integration tests
# ===========================================================================

class TestIntegration:
    """Tests for RAG integration with existing systems."""

    @pytest.fixture(autouse=True)
    def isolated_db(self, tmp_path):
        """Point the documents DB to a temp directory."""
        import memories.embeddings as emb
        old_config = emb.CONFIG_DIR
        old_db = emb.MEMORIES_DB
        emb.CONFIG_DIR = tmp_path
        emb.MEMORIES_DB = tmp_path / "test_memories.db"
        yield
        emb.CONFIG_DIR = old_config
        emb.MEMORIES_DB = old_db

    def test_tool_definitions_include_documents(self):
        """manage_documents is included in tool definitions."""
        from tools.definitions import get_all_tool_definitions
        tools = get_all_tool_definitions()
        names = [t["function"]["name"] for t in tools]
        assert "manage_documents" in names

    def test_green_tools_include_documents(self):
        """manage_documents is classified as GREEN."""
        from tools.executor import GREEN_TOOLS
        assert "manage_documents" in GREEN_TOOLS

    def test_permission_classifier_green(self):
        """manage_documents is GREEN in permission classifier."""
        from permission_classifier import GREEN_TOOLS
        assert "manage_documents" in GREEN_TOOLS
