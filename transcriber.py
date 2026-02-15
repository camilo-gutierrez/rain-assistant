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
