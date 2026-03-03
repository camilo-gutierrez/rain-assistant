from __future__ import annotations

import io
import logging
import os
import wave
from typing import Iterator

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Prompts that guide Whisper toward correct punctuation and vocabulary.
# These are injected as initial_prompt so the model "continues" in the same style.
LANGUAGE_PROMPTS: dict[str, str] = {
    "es": (
        "Hola, ¿cómo estás? Bien, gracias. "
        "Quiero que hagas lo siguiente: primero, revisa el código; "
        "segundo, ejecuta las pruebas. ¿Entendido?"
    ),
    "en": (
        "Hello, how are you? Fine, thanks. "
        "I'd like you to do the following: first, review the code; "
        "second, run the tests. Understood?"
    ),
}


def detect_best_config() -> tuple[str, str, str, int]:
    """Auto-detect the best model size, device, compute type, and CPU threads.

    Returns (model_size, device, compute_type, cpu_threads).

    Strategy:
    - CUDA GPU available    → large-v3 + float16       (best quality, fast)
    - CPU ≥8 cores + ≥8 GB → medium                    (good quality)
    - CPU ≥4 cores + ≥4 GB → small                     (decent quality)
    - Anything else         → base                      (fallback)

    For CPU inference, ``cpu_threads`` is set to the number of physical cores
    (capped at 8) so that faster-whisper uses parallelism effectively — this
    helps a lot on modern AMD Ryzen / Intel i7+ processors.

    Note: AMD GPUs are NOT supported by CTranslate2 (no ROCm backend).
    However AMD CPUs benefit from the thread optimization.

    The env var ``RAIN_WHISPER_MODEL`` overrides auto-detection entirely.
    The env var ``RAIN_WHISPER_DEVICE`` forces a device ("cpu" or "cuda").
    """
    # Allow manual override
    forced_model = os.environ.get("RAIN_WHISPER_MODEL", "").strip()
    forced_device = os.environ.get("RAIN_WHISPER_DEVICE", "").strip()

    # --- Detect CUDA (NVIDIA only) ---
    has_cuda = False
    if forced_device == "cuda":
        has_cuda = True
    elif forced_device != "cpu":
        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except ImportError:
            # ctranslate2 can also use CUDA without torch
            try:
                import ctranslate2
                has_cuda = "cuda" in ctranslate2.get_supported_compute_types("default")
            except Exception:
                has_cuda = False

    cpu_threads = _get_cpu_threads()

    if forced_model:
        device = "cuda" if has_cuda else "cpu"
        compute = "float16" if has_cuda else "int8"
        threads = 0 if has_cuda else cpu_threads
        logger.info("Whisper override: model=%s device=%s compute=%s threads=%d", forced_model, device, compute, threads)
        return forced_model, device, compute, threads

    if has_cuda:
        logger.info("CUDA GPU detected — using large-v3 (float16)")
        return "large-v3", "cuda", "float16", 0

    # --- CPU: pick model based on available RAM + cores ---
    ram_gb = _get_available_ram_gb()
    cores = os.cpu_count() or 2

    if ram_gb >= 8 and cores >= 8:
        model = "medium"
    elif ram_gb >= 4 and cores >= 4:
        model = "small"
    elif ram_gb >= 4:
        model = "small"
    else:
        model = "base"

    logger.info(
        "CPU mode — RAM ~%.1f GB, %d cores, %d threads → using '%s' (int8)",
        ram_gb, cores, cpu_threads, model,
    )
    return model, "cpu", "int8", cpu_threads


def _get_cpu_threads() -> int:
    """Return an optimal thread count for CPU inference.

    Uses physical core count (not hyperthreaded), capped at 8 to avoid
    diminishing returns and memory pressure.
    """
    try:
        import psutil
        physical = psutil.cpu_count(logical=False) or (os.cpu_count() or 2)
    except ImportError:
        # Rough heuristic: logical cores / 2
        physical = max(1, (os.cpu_count() or 2) // 2)
    return min(physical, 8)


def _get_available_ram_gb() -> float:
    """Get available system RAM in GB."""
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except ImportError:
        pass
    # Fallback: assume 8 GB if psutil is not installed
    return 8.0


class Transcriber:
    def __init__(
        self,
        model_size: str = "auto",
        language: str = "es",
        device: str | None = None,
        compute_type: str | None = None,
    ):
        self.language = language
        self._model: WhisperModel | None = None

        if model_size == "auto":
            self._model_size, self._device, self._compute_type, self._cpu_threads = detect_best_config()
        else:
            self._model_size = model_size
            self._device = device or "cpu"
            self._compute_type = compute_type or "int8"
            self._cpu_threads = 0

    @property
    def model_size(self) -> str:
        return self._model_size

    def load_model(self):
        """Load the Whisper model. Call this once at startup."""
        logger.info(
            "Loading Whisper model '%s' on %s (%s, threads=%d)...",
            self._model_size, self._device, self._compute_type, self._cpu_threads,
        )
        kwargs: dict = dict(
            device=self._device,
            compute_type=self._compute_type,
        )
        if self._cpu_threads > 0:
            kwargs["cpu_threads"] = self._cpu_threads
        self._model = WhisperModel(self._model_size, **kwargs)
        logger.info("Whisper model loaded successfully.")

    def _get_language(self) -> str | None:
        """Return the language code, or None for auto-detection."""
        if self.language in ("auto", ""):
            return None
        return self.language

    def _get_prompt(self) -> str | None:
        """Return a language-specific initial prompt to improve accuracy."""
        lang = self._get_language()
        return LANGUAGE_PROMPTS.get(lang) if lang else None

    def transcribe(self, audio_path):
        """Transcribe an audio file to text. Returns the transcribed string."""
        if self._model is None:
            self.load_model()

        segments, _ = self._model.transcribe(
            audio_path,
            language=self._get_language(),
            beam_size=5,
            vad_filter=True,
            initial_prompt=self._get_prompt(),
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
            language=self._get_language(),
            beam_size=5,
            vad_filter=True,
            initial_prompt=self._get_prompt(),
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

    def transcribe_pcm_buffer(
        self, pcm_bytes: bytes, sample_rate: int = 16000, *, fast: bool = False,
    ) -> str:
        """Transcribe raw PCM audio bytes directly (no temp file needed).

        Parameters
        ----------
        pcm_bytes : bytes
            Raw 16-bit little-endian PCM audio.
        sample_rate : int
            Sample rate of the audio (default 16000).
        fast : bool
            If True, use greedy decoding (beam_size=1) for lower latency.
            Suitable for short voice utterances.
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
            language=self._get_language(),
            beam_size=1 if fast else 5,
            vad_filter=True,
            initial_prompt=self._get_prompt(),
        )

        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()
