"""Text chunking for Rain RAG system.

Splits documents into overlapping chunks suitable for embedding with
all-MiniLM-L6-v2 (max 512 tokens ≈ 2000 chars).
"""

# Target chunk size in characters (~500 tokens at ~4 chars/token)
CHUNK_SIZE = 2000
# Overlap between consecutive chunks for context continuity
CHUNK_OVERLAP = 256
# Hard limit per chunk to prevent runaway chunks
MAX_CHUNK_CHARS = 3000


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks.

    Strategy:
    1. Split by double newlines (paragraphs)
    2. Accumulate paragraphs until chunk_size is reached
    3. If a single paragraph exceeds MAX_CHUNK_CHARS, sub-split it
    4. Add overlap from previous chunk's tail

    Returns a list of chunk strings. Empty input returns an empty list.
    """
    if not text or not text.strip():
        return []

    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        # Sub-split oversized paragraphs
        if len(para) > MAX_CHUNK_CHARS:
            # Flush current buffer first
            if buffer.strip():
                chunks.append(buffer.strip())
                buffer = ""
            for sub in _split_long_text(para):
                chunks.append(sub.strip())
            continue

        # Would adding this paragraph exceed chunk_size?
        candidate = (buffer + "\n\n" + para) if buffer else para
        if len(candidate) > chunk_size and buffer.strip():
            # Emit current buffer as a chunk
            chunks.append(buffer.strip())
            # Start new buffer with overlap from previous chunk
            prev_tail = buffer[-overlap:] if len(buffer) > overlap else buffer
            buffer = prev_tail + "\n\n" + para
        else:
            buffer = candidate

    # Don't forget the last buffer
    if buffer.strip():
        chunks.append(buffer.strip())

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text by double newlines, filtering empty segments."""
    parts = text.split("\n\n")
    return [p for p in parts if p.strip()]


def _split_long_text(text: str) -> list[str]:
    """Split an oversized paragraph into smaller pieces.

    First tries splitting by single newlines, then by sentence boundaries.
    """
    # Try splitting by single newlines
    lines = text.split("\n")
    if len(lines) > 1:
        return _accumulate(lines, "\n")

    # Try splitting by sentences (period + space)
    sentences = text.split(". ")
    if len(sentences) > 1:
        # Re-add the period to each sentence except the last
        restored = [s + "." for s in sentences[:-1]] + [sentences[-1]]
        return _accumulate(restored, " ")

    # Last resort: hard split by character limit
    result = []
    for i in range(0, len(text), MAX_CHUNK_CHARS):
        result.append(text[i : i + MAX_CHUNK_CHARS])
    return result


def _accumulate(parts: list[str], separator: str) -> list[str]:
    """Accumulate parts into chunks up to MAX_CHUNK_CHARS."""
    chunks: list[str] = []
    buffer = ""
    for part in parts:
        candidate = (buffer + separator + part) if buffer else part
        if len(candidate) > MAX_CHUNK_CHARS and buffer:
            chunks.append(buffer.strip())
            buffer = part
        else:
            buffer = candidate
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks
