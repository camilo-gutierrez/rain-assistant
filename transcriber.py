from __future__ import annotations

import io
import wave
from typing import Iterator

from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size="base", language="es"):
        self.language = language
        self._model = None
        self._model_size = model_size

    def load_model(self):
        """Load the Whisper model. Call this once at startup."""
        self._model = WhisperModel(
            self._model_size,
            device="cpu",
            compute_type="int8",
        )

    def transcribe(self, audio_path):
        """Transcribe an audio file to text. Returns the transcribed string."""
        if self._model is None:
            self.load_model()

        segments, _ = self._model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            vad_filter=True,
        )

        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()

    def transcribe_streaming(self, audio_path: str) -> Iterator[tuple[str, bool]]:
        """Transcribe audio yielding partial results as segments complete.

        Yields (text, is_final) tuples where ``is_final=True`` on the last segment.
        This allows the caller to send partial transcription updates.
        """
        if self._model is None:
            self.load_model()

        segments, info = self._model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            vad_filter=True,
        )

        accumulated = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                accumulated.append(text)
                yield " ".join(accumulated), False

        # Final yield with all text
        final_text = " ".join(accumulated) if accumulated else ""
        if final_text:
            yield final_text, True

    def transcribe_pcm_buffer(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM audio bytes directly (no temp file needed).

        Parameters
        ----------
        pcm_bytes : bytes
            Raw 16-bit little-endian PCM audio.
        sample_rate : int
            Sample rate of the audio (default 16000).
        """
        if self._model is None:
            self.load_model()

        # Convert PCM bytes to WAV in memory
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        buf.seek(0)

        segments, _ = self._model.transcribe(
            buf,
            language=self.language,
            beam_size=5,
            vad_filter=True,
        )

        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()
