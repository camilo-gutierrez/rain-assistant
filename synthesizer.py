from __future__ import annotations

import re
import tempfile
from typing import AsyncIterator

import edge_tts

# Default voice mapping by language
VOICES = {
    "es-female": "es-MX-DaliaNeural",
    "es-male": "es-MX-JorgeNeural",
    "en-female": "en-US-JennyNeural",
    "en-male": "en-US-GuyNeural",
}

VALID_VOICES = set(VOICES.values())
DEFAULT_VOICE = "es-MX-DaliaNeural"
MAX_TTS_LENGTH = 5000


def preprocess_text(text: str) -> str:
    """Strip markdown artifacts that degrade TTS quality."""
    # Remove code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code (`...`)
    text = re.sub(r"`[^`]+`", "", text)
    # Remove markdown headers (# ## ### etc.)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove image syntax ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Convert links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Remove emojis and pictographic symbols
    text = re.sub(
        r"[\U0001F600-\U0001F64F"   # emoticons
        r"\U0001F300-\U0001F5FF"    # misc symbols & pictographs
        r"\U0001F680-\U0001F6FF"    # transport & map symbols
        r"\U0001F1E0-\U0001F1FF"    # flags
        r"\U00002702-\U000027B0"    # dingbats
        r"\U000024C2-\U0001F251"    # enclosed chars
        r"\U0001F900-\U0001F9FF"    # supplemental symbols
        r"\U0001FA00-\U0001FA6F"    # chess symbols
        r"\U0001FA70-\U0001FAFF"    # symbols extended-A
        r"\U00002600-\U000026FF"    # misc symbols
        r"\U0000FE00-\U0000FE0F"    # variation selectors
        r"\U0000200D"               # zero-width joiner
        r"]+", "", text,
    )
    # Remove repeated punctuation (¡¡¡, !!!, ???, ...)
    text = re.sub(r"([!?¡¿]){2,}", r"\1", text)
    # Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_mostly_code(text: str) -> bool:
    """Heuristic: if >60% of the text is inside code blocks, skip TTS."""
    code_blocks = re.findall(r"```[\s\S]*?```", text)
    code_len = sum(len(b) for b in code_blocks)
    return len(text) > 0 and (code_len / len(text)) > 0.6


class Synthesizer:
    """Text-to-speech synthesizer using Microsoft Edge TTS (free, high quality)."""

    async def synthesize(
        self,
        text: str,
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
    ) -> str | None:
        """Synthesize text to an MP3 temp file.

        Returns the file path on success, or None if there is nothing to synthesize
        (e.g. text is empty or mostly code blocks).
        """
        if not text or not text.strip():
            return None

        if is_mostly_code(text):
            return None

        clean = preprocess_text(text)
        if not clean:
            return None

        # Truncate to max length
        if len(clean) > MAX_TTS_LENGTH:
            clean = clean[:MAX_TTS_LENGTH] + "..."

        # Validate voice
        if voice not in VALID_VOICES:
            voice = DEFAULT_VOICE

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()

        communicate = edge_tts.Communicate(clean, voice, rate=rate)
        await communicate.save(tmp.name)

        return tmp.name

    async def synthesize_streaming(
        self,
        text: str,
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
    ) -> AsyncIterator[bytes]:
        """Synthesize text and yield MP3 byte chunks as they arrive.

        Unlike ``synthesize()``, this never writes to disk — audio bytes
        are yielded progressively via ``edge_tts.Communicate.stream()``.
        """
        clean = preprocess_text(text)
        if not clean:
            return

        if len(clean) > MAX_TTS_LENGTH:
            clean = clean[:MAX_TTS_LENGTH] + "..."

        if voice not in VALID_VOICES:
            voice = DEFAULT_VOICE

        communicate = edge_tts.Communicate(clean, voice, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]


# Common abbreviations that should NOT trigger a sentence split
_ABBREVIATIONS = re.compile(
    r"(?:Mr|Mrs|Ms|Dr|Prof|Jr|Sr|vs|etc|inc|ltd|Corp|approx|dept|est|vol"
    r"|No|no|St|Ave|Blvd|Rd|Fig|fig|Eq|eq|e\.g|i\.e|a\.m|p\.m)\.$",
    re.IGNORECASE,
)


class SentenceBuffer:
    """Accumulates streamed LLM text and splits on sentence boundaries.

    Usage::

        buf = SentenceBuffer()
        for delta in llm_stream:
            for sentence in buf.feed(delta):
                synthesize(sentence)
        remaining = buf.flush()
        if remaining:
            synthesize(remaining)
    """

    def __init__(self, min_length: int = 8) -> None:
        self._buf = ""
        self._min_length = min_length

    def feed(self, delta: str) -> list[str]:
        """Feed a text delta and return any completed sentences."""
        self._buf += delta
        sentences: list[str] = []

        while True:
            # Look for sentence-ending punctuation followed by whitespace
            match = re.search(r"([.!?])\s", self._buf)
            if not match:
                # Also split on double newlines (paragraph breaks)
                nl_pos = self._buf.find("\n\n")
                if nl_pos != -1 and nl_pos >= self._min_length:
                    sentence = self._buf[:nl_pos].strip()
                    self._buf = self._buf[nl_pos + 2:]
                    if sentence:
                        sentences.append(sentence)
                    continue
                break

            pos = match.end()
            candidate = self._buf[:pos].strip()

            # Skip if too short (likely not a real sentence)
            if len(candidate) < self._min_length:
                # But only skip if there's more text coming — if we have
                # a lot of short text accumulated, emit it anyway
                if len(self._buf) < self._min_length * 3:
                    break

            # Skip abbreviations (e.g. "Dr. Smith" should not split)
            before_punct = self._buf[: match.start() + 1]
            if _ABBREVIATIONS.search(before_punct):
                # Move past this match and keep scanning
                # We need to look for the next boundary
                next_buf = self._buf[pos:]
                # If there's no more text to check, stop
                if not re.search(r"[.!?]\s", next_buf) and "\n\n" not in next_buf:
                    break
                # Otherwise, we skip this one and the while loop continues
                # by searching from the remaining buffer
                self._buf = self._buf  # no-op, let the loop re-match
                break

            sentences.append(candidate)
            self._buf = self._buf[pos:]

        return sentences

    def flush(self) -> str | None:
        """Return any remaining buffered text."""
        text = self._buf.strip()
        self._buf = ""
        return text or None
