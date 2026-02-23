"""Document file parsers for Rain RAG system.

Extracts plain text from supported file formats (.txt, .md, .pdf).
PDF support requires pypdf (optional dependency).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def parse_file(file_path: str) -> str:
    """Parse a file and return its text content.

    Supported formats:
    - .txt: read as UTF-8
    - .md: read as UTF-8 (markdown is already text)
    - .pdf: extract text via pypdf

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the file format is not supported or file exceeds size limit.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check file size before reading
    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        raise ValueError(
            f"File too large: {size_mb:.1f} MB. "
            f"Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
        )

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format: '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext in (".txt", ".md"):
        return _parse_text(path)
    elif ext == ".pdf":
        return _parse_pdf(path)

    return ""


def _parse_text(path: Path) -> str:
    """Read a plain text or markdown file."""
    return path.read_text(encoding="utf-8", errors="replace")


MAX_PDF_PAGES = 500
MAX_EXTRACTED_TEXT_BYTES = 10 * 1024 * 1024  # 10MB of extracted text


def _parse_pdf(path: Path) -> str:
    """Parse PDF file with safety limits."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf is required for PDF support. "
            "Install with: pip install rain-assistant[memory]"
        )

    try:
        reader = PdfReader(str(path))
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {type(e).__name__}")

    pages = []
    total_size = 0
    for i, page in enumerate(reader.pages):
        if i >= MAX_PDF_PAGES:
            logger.warning(
                "PDF '%s' has more than %d pages; truncating.", path.name, MAX_PDF_PAGES
            )
            pages.append(
                f"\n[WARNING: PDF truncated at {MAX_PDF_PAGES} pages out of {len(reader.pages)} total]"
            )
            break
        try:
            text = page.extract_text()
        except Exception:
            continue  # Skip malformed pages
        if text:
            total_size += len(text.encode("utf-8", errors="replace"))
            if total_size > MAX_EXTRACTED_TEXT_BYTES:
                pages.append("[... truncated: extracted text exceeds 10MB limit]")
                break
            pages.append(text)
    return "\n\n".join(pages)
