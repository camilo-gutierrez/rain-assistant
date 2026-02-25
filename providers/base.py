"""Abstract base class for AI providers."""

import logging
import re
from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Awaitable, Any

_logger = logging.getLogger(__name__)


def _sanitize_api_error(provider_name: str, error: Exception) -> str:
    """Log full error server-side, return safe message for client.

    Strips API keys, bearer tokens, and other secrets from the error
    message so they are never leaked over the WebSocket to the frontend.
    """
    _logger.error("%s API error: %s", provider_name, error, exc_info=True)
    error_type = type(error).__name__
    # Extract only the first line, truncate, and strip potential secrets
    msg = str(error).split('\n')[0][:200]
    # Remove anything that looks like an API key (sk-..., AIza..., etc.)
    msg = re.sub(r'(sk-[a-zA-Z0-9]{6})[a-zA-Z0-9]+', r'\1...', msg)
    msg = re.sub(r'(AIza[a-zA-Z0-9]{6})[a-zA-Z0-9]+', r'\1...', msg)
    msg = re.sub(r'(Bearer\s+)[^\s"]+', r'\1[REDACTED]', msg)
    msg = re.sub(r'(key[=:]\s*)[^\s&"]+', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
    return f"{provider_name} error ({error_type}): {msg}"


class NormalizedEvent:
    """Normalized event emitted by all providers.

    Event types match the existing WSReceiveMessage types so the frontend
    needs zero changes to its WebSocket message routing:
      - assistant_text  : streaming text chunk
      - tool_use        : tool call started
      - tool_result     : tool call result
      - result          : final result with usage/cost
      - model_info      : model name
      - status          : status text
      - error           : error message
    """

    __slots__ = ("type", "data")

    def __init__(self, event_type: str, data: dict):
        self.type = event_type
        self.data = data

    def __repr__(self) -> str:
        return f"NormalizedEvent({self.type!r}, {self.data!r})"


class BaseProvider(ABC):
    """Abstract base for all AI provider integrations."""

    provider_name: str  # "claude" | "openai" | "gemini" | "ollama"

    @abstractmethod
    async def initialize(
        self,
        api_key: str,
        model: str,
        cwd: str,
        system_prompt: str,
        can_use_tool: Callable[..., Awaitable[Any]] | None = None,
        resume_session_id: str | None = None,
        mcp_servers: dict | str | None = None,
        agent_id: str = "default",
        user_id: str = "default",
    ) -> None:
        """Initialize the provider. Called when the user sets a working directory."""
        ...

    @abstractmethod
    async def send_message(self, text: str, images: list[dict] | None = None) -> None:
        """Send a user message, starting the agentic loop.

        Args:
            text: User message text.
            images: Optional list of image dicts with keys ``base64`` (raw
                    base64-encoded data) and ``mediaType`` (e.g. ``"image/png"``).
        """
        ...

    @abstractmethod
    async def stream_response(self) -> AsyncIterator[NormalizedEvent]:
        """Yield NormalizedEvents during the agentic loop.

        The caller iterates these and forwards them to the WebSocket.
        """
        ...

    @abstractmethod
    async def interrupt(self) -> None:
        """Interrupt the current agentic loop."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up resources."""
        ...

    def supports_session_resumption(self) -> bool:
        """Whether this provider supports session/conversation resumption."""
        return False

    def supports_computer_use(self) -> bool:
        """Whether this provider supports Computer Use mode."""
        return False
