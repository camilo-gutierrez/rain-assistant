import re
import tempfile

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
