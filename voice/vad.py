"""Voice Activity Detection using Silero VAD (MIT license, 1.8MB model).

Processes 16-bit PCM audio at 16kHz mono in 512-sample (32ms) chunks
and emits speech_start / speech_end / speech_ongoing / silence events.
"""

from __future__ import annotations

import enum
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class VADEvent(str, enum.Enum):
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    SPEECH_ONGOING = "speech_ongoing"
    SILENCE = "silence"


class VoiceActivityDetector:
    """Lightweight wrapper around Silero VAD v5.

    Parameters
    ----------
    threshold : float
        Probability above which a chunk is considered speech (0.0–1.0).
    min_speech_ms : int
        Minimum consecutive speech duration before emitting ``speech_start``.
    min_silence_ms : int
        Minimum consecutive silence after speech before emitting ``speech_end``.
    sample_rate : int
        Expected sample rate (must be 8000 or 16000 for Silero).
    """

    CHUNK_SAMPLES = 512  # 32ms at 16kHz — Silero's native frame size

    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_ms: int = 250,
        min_silence_ms: int = 800,
        sample_rate: int = 16000,
    ) -> None:
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.sample_rate = sample_rate

        self._model = None
        self._is_speaking = False
        self._speech_start_time: float | None = None
        self._silence_start_time: float | None = None
        self._speech_confirmed = False

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch

            self._model, _utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
            )
            self._model.eval()
        except Exception as exc:
            raise RuntimeError(
                "Failed to load Silero VAD. Install with: pip install silero-vad torch"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_chunk(self, pcm_bytes: bytes) -> VADEvent:
        """Process a single audio chunk and return a VAD event.

        Parameters
        ----------
        pcm_bytes : bytes
            Raw 16-bit little-endian PCM audio, 16kHz mono.
            Must be exactly ``CHUNK_SAMPLES * 2`` bytes (1024 bytes for 512 samples).
        """
        self._ensure_model()
        import torch
        import numpy as _np

        # Convert bytes → float32 tensor normalised to [-1, 1]
        audio_int16 = _np.frombuffer(pcm_bytes, dtype=_np.int16)
        audio_f32 = audio_int16.astype(_np.float32) / 32768.0
        tensor = torch.from_numpy(audio_f32)

        # Silero inference
        prob: float = self._model(tensor, self.sample_rate).item()  # type: ignore[union-attr]

        now = time.monotonic()
        is_speech = prob >= self.threshold

        if is_speech:
            self._silence_start_time = None

            if not self._is_speaking:
                # Possible speech start
                if self._speech_start_time is None:
                    self._speech_start_time = now

                elapsed_ms = (now - self._speech_start_time) * 1000
                if elapsed_ms >= self.min_speech_ms:
                    self._is_speaking = True
                    self._speech_confirmed = True
                    return VADEvent.SPEECH_START

                return VADEvent.SILENCE  # Not enough speech yet
            else:
                return VADEvent.SPEECH_ONGOING
        else:
            # Silence
            self._speech_start_time = None

            if self._is_speaking:
                if self._silence_start_time is None:
                    self._silence_start_time = now

                elapsed_ms = (now - self._silence_start_time) * 1000
                if elapsed_ms >= self.min_silence_ms:
                    self._is_speaking = False
                    self._speech_confirmed = False
                    self._silence_start_time = None
                    return VADEvent.SPEECH_END

                return VADEvent.SPEECH_ONGOING  # Short pause, still "speaking"

            return VADEvent.SILENCE

    def reset(self) -> None:
        """Reset the detector state (e.g. between sessions)."""
        self._is_speaking = False
        self._speech_start_time = None
        self._silence_start_time = None
        self._speech_confirmed = False
        if self._model is not None:
            self._model.reset_states()  # type: ignore[union-attr]

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
