"""Document file parsers for Rain RAG system.

Extracts plain text from supported file formats (.txt, .md, .pdf).
PDF support requires pypdf (optional dependency).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def parse_file(file_path: str) -> str:
    """Parse a file and return its text content.

    Supported formats:
    - .txt: read as UTF-8
    - .md: read as UTF-8 (markdown is already text)
    - .pdf: extract text via pypdf

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the file format is not supported.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

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


def _parse_pdf(path: Path) -> str:
    """Extract text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf is required for PDF support. "
            "Install with: pip install rain-assistant[memory]"
        )

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)
