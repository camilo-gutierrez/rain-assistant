"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Awaitable, Any


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
    ) -> None:
        """Initialize the provider. Called when the user sets a working directory."""
        ...

    @abstractmethod
    async def send_message(self, text: str) -> None:
        """Send a user message, starting the agentic loop."""
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
