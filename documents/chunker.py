"""Text chunking for Rain RAG system.

Splits documents into overlapping chunks suitable for embedding with
all-MiniLM-L6-v2 (max 512 tokens ≈ 2000 chars).

Supports two strategies:
- **Semantic chunking** (default for structured docs): splits on markdown
  headers and preserves the header hierarchy as context in each chunk.
- **Paragraph chunking** (fallback): splits on double newlines with overlap.
"""

import re
from typing import Optional

# Target chunk size in characters (~500 tokens at ~4 chars/token)
CHUNK_SIZE = 2000
# Overlap between consecutive chunks for context continuity
CHUNK_OVERLAP = 256
# Hard limit per chunk to prevent runaway chunks
MAX_CHUNK_CHARS = 3000

# ── Markdown header regex ───────────────────────────────────────────────
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


# ── Public API ──────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks.

    Automatically selects the best strategy:
    - If the text contains markdown headers (# through ######),
      uses semantic chunking that respects section boundaries.
    - Otherwise, falls back to paragraph-based chunking.

    Returns a list of chunk strings. Empty input returns an empty list.
    """
    if not text or not text.strip():
        return []

    # Try semantic chunking if markdown headers are present
    if _has_markdown_headers(text):
        chunks = _semantic_chunk(text, chunk_size)
        if chunks:
            return chunks

    # Fallback to paragraph-based chunking
    return _paragraph_chunk(text, chunk_size, overlap)


def chunk_text_with_metadata(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """Split text into chunks and return with metadata.

    Each chunk is a dict with:
    - ``content``: the chunk text (includes header context prefix)
    - ``headers``: list of parent headers leading to this chunk
    - ``section``: the most specific (deepest) header for this chunk

    Falls back to paragraph-based chunking (no metadata) for plain text.
    """
    if not text or not text.strip():
        return []

    if _has_markdown_headers(text):
        result = _semantic_chunk_with_metadata(text, chunk_size)
        if result:
            return result

    # Fallback: plain chunks with empty metadata
    chunks = _paragraph_chunk(text, chunk_size, overlap)
    return [{"content": c, "headers": [], "section": ""} for c in chunks]


# ── Semantic chunking (header-aware) ───────────────────────────────────

def _has_markdown_headers(text: str) -> bool:
    """Check if text contains at least 2 markdown headers."""
    return len(_HEADER_RE.findall(text)) >= 2


def _semantic_chunk(text: str, chunk_size: int) -> list[str]:
    """Split text by markdown headers, preserving header context.

    Each chunk starts with its header hierarchy (e.g. "# Doc Title > ## Section")
    followed by the section content. Chunks that exceed chunk_size are sub-split
    using paragraph-based chunking.
    """
    meta_chunks = _semantic_chunk_with_metadata(text, chunk_size)
    return [mc["content"] for mc in meta_chunks]


def _semantic_chunk_with_metadata(text: str, chunk_size: int) -> list[dict]:
    """Core semantic chunking implementation with metadata."""
    sections = _split_by_headers(text)
    if not sections:
        return []

    result: list[dict] = []

    for section in sections:
        header_chain = section["headers"]
        section_name = section["section"]
        body = section["body"].strip()

        if not body:
            continue

        # Build context prefix from header chain
        prefix = ""
        if header_chain:
            prefix = " > ".join(header_chain) + "\n\n"

        full_text = prefix + body

        if len(full_text) <= chunk_size:
            result.append({
                "content": full_text,
                "headers": header_chain,
                "section": section_name,
            })
        else:
            # Sub-split large sections using paragraph chunking
            sub_chunks = _paragraph_chunk(body, chunk_size - len(prefix), CHUNK_OVERLAP)
            for sub in sub_chunks:
                result.append({
                    "content": prefix + sub,
                    "headers": header_chain,
                    "section": section_name,
                })

    return result


def _split_by_headers(text: str) -> list[dict]:
    """Split text into sections based on markdown headers.

    Returns a list of dicts:
      {"headers": ["# Title", "## Section"], "section": "Section", "body": "..."}
    """
    lines = text.split("\n")
    sections: list[dict] = []
    header_stack: list[tuple[int, str]] = []
    current_body_lines: list[str] = []
    preamble_lines: list[str] = []
    found_first_header = False

    for line in lines:
        match = _HEADER_RE.match(line)
        if not match:
            (current_body_lines if found_first_header else preamble_lines).append(line)
            continue

        level = len(match.group(1))
        header_text = match.group(2).strip()

        if not found_first_header:
            found_first_header = True
            _flush_section(sections, preamble_lines, [])
        else:
            _flush_section(sections, current_body_lines, header_stack)

        current_body_lines = []
        _update_header_stack(header_stack, level, header_text)

    # Flush final section
    if header_stack:
        _flush_section(sections, current_body_lines, header_stack)

    return sections


def _flush_section(
    sections: list[dict],
    body_lines: list[str],
    header_stack: list[tuple[int, str]],
) -> None:
    """Append a section to the list if body is non-empty."""
    body = "\n".join(body_lines)
    if not body.strip():
        return
    chain = [f"{'#' * lvl} {txt}" for lvl, txt in header_stack]
    section_name = header_stack[-1][1] if header_stack else ""
    sections.append({"headers": chain, "section": section_name, "body": body})


def _update_header_stack(
    stack: list[tuple[int, str]], level: int, text: str,
) -> None:
    """Pop headers at same or deeper level, then push the new one."""
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, text))


# ── Paragraph-based chunking (original algorithm) ─────────────────────

def _paragraph_chunk(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks by paragraphs.

    Strategy:
    1. Split by double newlines (paragraphs)
    2. Accumulate paragraphs until chunk_size is reached
    3. If a single paragraph exceeds MAX_CHUNK_CHARS, sub-split it
    4. Add overlap from previous chunk's tail
    """
    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        buffer = _process_paragraph(para, buffer, chunks, chunk_size, overlap)

    if buffer.strip():
        chunks.append(buffer.strip())

    return chunks


def _process_paragraph(
    para: str, buffer: str, chunks: list[str], chunk_size: int, overlap: int,
) -> str:
    """Process one paragraph, flushing the buffer if needed. Returns new buffer."""
    if len(para) > MAX_CHUNK_CHARS:
        if buffer.strip():
            chunks.append(buffer.strip())
        chunks.extend(sub.strip() for sub in _split_long_text(para))
        return ""

    candidate = (buffer + "\n\n" + para) if buffer else para
    if len(candidate) <= chunk_size or not buffer.strip():
        return candidate

    chunks.append(buffer.strip())
    prev_tail = buffer[-overlap:] if len(buffer) > overlap else buffer
    return prev_tail + "\n\n" + para


# ── Utility helpers ────────────────────────────────────────────────────

def _split_paragraphs(text: str) -> list[str]:
    """Split text by double newlines, filtering empty segments."""
    parts = text.split("\n\n")
    return [p for p in parts if p.strip()]


def _split_long_text(text: str) -> list[str]:
    """Split an oversized paragraph into smaller pieces.

    First tries splitting by single newlines, then by sentence boundaries.
    """
    lines = text.split("\n")
    if len(lines) > 1:
        return _accumulate(lines, "\n")

    sentences = text.split(". ")
    if len(sentences) > 1:
        restored = [s + "." for s in sentences[:-1]] + [sentences[-1]]
        return _accumulate(restored, " ")

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
