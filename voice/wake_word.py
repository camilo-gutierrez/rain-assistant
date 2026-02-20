"""Wake Word Detection using OpenWakeWord (Apache 2.0).

Listens for "Hey Rain" (or fallback "hey jarvis") in audio chunks.
Processes 16-bit PCM audio at 16kHz mono in 1280-sample (80ms) frames.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).parent / "models"
_CUSTOM_MODEL = _MODELS_DIR / "hey_rain.onnx"
_FALLBACK_MODELS = ["hey_jarvis_v0.1"]  # built-in openwakeword models


class WakeWordDetector:
    """Wrapper around OpenWakeWord for detecting a trigger phrase.

    Parameters
    ----------
    threshold : float
        Detection confidence threshold (0.0–1.0). Higher = fewer false positives.
    model_path : str | Path | None
        Path to custom ONNX model. Falls back to built-in models if None or missing.
    """

    FRAME_SAMPLES = 1280  # 80ms at 16kHz — OpenWakeWord's native frame size

    def __init__(
        self,
        threshold: float = 0.6,
        model_path: str | Path | None = None,
    ) -> None:
        self.threshold = threshold
        self._model_path = Path(model_path) if model_path else _CUSTOM_MODEL
        self._oww = None
        self._detected_model: str | None = None

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._oww is not None:
            return

        try:
            import openwakeword
            from openwakeword.model import Model

            # Try custom model first
            if self._model_path.exists():
                logger.info("Loading custom wake word model: %s", self._model_path)
                self._oww = Model(
                    wakeword_models=[str(self._model_path)],
                    inference_framework="onnx",
                )
            else:
                # Fall back to built-in models
                logger.info(
                    "Custom model not found at %s, using built-in: %s",
                    self._model_path,
                    _FALLBACK_MODELS,
                )
                openwakeword.utils.download_models(model_names=_FALLBACK_MODELS)
                self._oww = Model(
                    wakeword_models=_FALLBACK_MODELS,
                    inference_framework="onnx",
                )
        except Exception as exc:
            raise RuntimeError(
                "Failed to load OpenWakeWord. Install with: pip install openwakeword"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_chunk(self, pcm_bytes: bytes) -> tuple[bool, float]:
        """Process a single audio frame and check for wake word.

        Parameters
        ----------
        pcm_bytes : bytes
            Raw 16-bit little-endian PCM audio, 16kHz mono.
            Must be exactly ``FRAME_SAMPLES * 2`` bytes (2560 bytes).

        Returns
        -------
        tuple[bool, float]
            (detected, confidence) — True if wake word was detected above threshold.
        """
        self._ensure_loaded()
        import numpy as np

        audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        self._oww.predict(audio_int16)  # type: ignore[union-attr]

        # Check all loaded models for detection
        for model_name in self._oww.prediction_buffer.keys():  # type: ignore[union-attr]
            scores = self._oww.prediction_buffer[model_name]  # type: ignore[union-attr]
            if len(scores) > 0:
                confidence = float(scores[-1])
                if confidence >= self.threshold:
                    self._detected_model = model_name
                    self._oww.reset()  # type: ignore[union-attr]
                    return True, confidence

        return False, 0.0

    def reset(self) -> None:
        """Reset the detector state."""
        if self._oww is not None:
            self._oww.reset()  # type: ignore[union-attr]
        self._detected_model = None

    @property
    def detected_model(self) -> str | None:
        """Name of the last detected wake word model."""
        return self._detected_model

    @property
    def is_loaded(self) -> bool:
        return self._oww is not None

    @property
    def available_models(self) -> list[str]:
        """List of loaded wake word model names."""
        if self._oww is None:
            return []
        return list(self._oww.prediction_buffer.keys())  # type: ignore[union-attr]
