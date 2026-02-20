"""Talk Session — State machine for continuous voice conversation.

Manages the lifecycle of a voice conversation:
  IDLE → WAKE_LISTENING → LISTENING → RECORDING → TRANSCRIBING → PROCESSING → SPEAKING → LISTENING

Supports interruption (user speaks during TTS) and inactivity timeout.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time

logger = logging.getLogger(__name__)


class TalkState(str, enum.Enum):
    IDLE = "idle"
    WAKE_LISTENING = "wake_listening"
    LISTENING = "listening"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class TalkSession:
    """Per-agent state machine for continuous voice conversation.

    Parameters
    ----------
    agent_id : str
        The agent this session belongs to.
    on_state_change : callable
        ``async (agent_id, state) -> None`` — called when state changes.
    on_transcription_ready : callable
        ``async (agent_id, text) -> None`` — called when speech is transcribed.
    on_tts_request : callable
        ``async (agent_id, text) -> None`` — called when response should be spoken.
    inactivity_timeout_s : float
        Seconds of silence before returning to IDLE (default 30).
    use_wake_word : bool
        If True, starts in WAKE_LISTENING instead of LISTENING.
    """

    def __init__(
        self,
        agent_id: str,
        on_state_change=None,
        on_transcription_ready=None,
        on_tts_request=None,
        inactivity_timeout_s: float = 30.0,
        use_wake_word: bool = False,
    ) -> None:
        self.agent_id = agent_id
        self._on_state_change = on_state_change
        self._on_transcription_ready = on_transcription_ready
        self._on_tts_request = on_tts_request
        self._inactivity_timeout = inactivity_timeout_s
        self._use_wake_word = use_wake_word

        self._state = TalkState.IDLE
        self._last_activity = time.monotonic()
        self._inactivity_task: asyncio.Task | None = None
        self._active = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> TalkState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def _set_state(self, new_state: TalkState) -> None:
        if new_state == self._state:
            return
        old = self._state
        self._state = new_state
        self._last_activity = time.monotonic()
        logger.debug("TalkSession[%s]: %s → %s", self.agent_id, old.value, new_state.value)
        if self._on_state_change:
            await self._on_state_change(self.agent_id, new_state.value)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Begin the talk session."""
        self._active = True
        initial = TalkState.WAKE_LISTENING if self._use_wake_word else TalkState.LISTENING
        await self._set_state(initial)
        self._start_inactivity_timer()

    async def stop(self) -> None:
        """End the talk session."""
        self._active = False
        self._cancel_inactivity_timer()
        await self._set_state(TalkState.IDLE)

    # ------------------------------------------------------------------
    # Event handlers (called by the voice pipeline in server.py)
    # ------------------------------------------------------------------

    async def on_wake_word_detected(self) -> None:
        """Called when wake word is detected."""
        if not self._active:
            return
        if self._state == TalkState.WAKE_LISTENING:
            await self._set_state(TalkState.LISTENING)
            self._restart_inactivity_timer()

    async def on_speech_start(self) -> None:
        """Called when VAD detects speech."""
        if not self._active:
            return

        if self._state == TalkState.SPEAKING:
            # Interruption! User speaks while Rain is talking
            await self.on_interruption()
            return

        if self._state in (TalkState.LISTENING, TalkState.WAKE_LISTENING):
            await self._set_state(TalkState.RECORDING)
            self._restart_inactivity_timer()

    async def on_speech_end(self) -> None:
        """Called when VAD detects end of speech."""
        if not self._active:
            return
        if self._state == TalkState.RECORDING:
            await self._set_state(TalkState.TRANSCRIBING)

    async def on_transcription(self, text: str) -> None:
        """Called when transcription is complete."""
        if not self._active:
            return
        if self._state == TalkState.TRANSCRIBING:
            await self._set_state(TalkState.PROCESSING)
            if self._on_transcription_ready:
                await self._on_transcription_ready(self.agent_id, text)

    async def on_response_ready(self, text: str) -> None:
        """Called when the AI response is ready — trigger TTS."""
        if not self._active:
            return
        if self._state == TalkState.PROCESSING:
            await self._set_state(TalkState.SPEAKING)
            if self._on_tts_request:
                await self._on_tts_request(self.agent_id, text)

    async def on_tts_done(self) -> None:
        """Called when TTS playback finishes."""
        if not self._active:
            return
        if self._state == TalkState.SPEAKING:
            # Loop back to listening
            next_state = TalkState.WAKE_LISTENING if self._use_wake_word else TalkState.LISTENING
            await self._set_state(next_state)
            self._restart_inactivity_timer()

    async def on_interruption(self) -> None:
        """Called when user interrupts (speaks during TTS)."""
        if not self._active:
            return
        await self._set_state(TalkState.RECORDING)
        self._restart_inactivity_timer()

    # ------------------------------------------------------------------
    # Inactivity timer
    # ------------------------------------------------------------------

    def _start_inactivity_timer(self) -> None:
        self._cancel_inactivity_timer()
        self._inactivity_task = asyncio.create_task(self._inactivity_watchdog())

    def _restart_inactivity_timer(self) -> None:
        self._last_activity = time.monotonic()
        if self._inactivity_task is None or self._inactivity_task.done():
            self._start_inactivity_timer()

    def _cancel_inactivity_timer(self) -> None:
        if self._inactivity_task and not self._inactivity_task.done():
            self._inactivity_task.cancel()
        self._inactivity_task = None

    async def _inactivity_watchdog(self) -> None:
        """Periodically checks if session has been idle too long."""
        try:
            while self._active:
                await asyncio.sleep(5.0)
                elapsed = time.monotonic() - self._last_activity
                if elapsed >= self._inactivity_timeout and self._state in (
                    TalkState.LISTENING,
                    TalkState.WAKE_LISTENING,
                ):
                    logger.info(
                        "TalkSession[%s]: inactivity timeout (%.0fs), stopping",
                        self.agent_id,
                        elapsed,
                    )
                    await self.stop()
                    return
        except asyncio.CancelledError:
            pass
