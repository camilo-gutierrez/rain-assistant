"""Claude provider — wraps claude_agent_sdk (existing behavior)."""

import json
from typing import AsyncIterator, Callable, Awaitable, Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    SystemMessage as SDKSystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from claude_agent_sdk.types import StreamEvent

from .base import BaseProvider, NormalizedEvent


class ClaudeProvider(BaseProvider):
    """Provider that wraps the Claude Agent SDK (existing Rain behavior)."""

    provider_name = "claude"

    def __init__(self):
        self._client: ClaudeSDKClient | None = None

    async def initialize(
        self,
        api_key: str,
        model: str,
        cwd: str,
        system_prompt: str,
        can_use_tool: Callable[..., Awaitable[Any]] | None = None,
        resume_session_id: str | None = None,
        mcp_servers: dict | str | None = None,
    ) -> None:
        env = {"ANTHROPIC_API_KEY": api_key} if api_key else {}

        options = ClaudeAgentOptions(
            cwd=cwd,
            permission_mode="default",
            can_use_tool=can_use_tool,
            include_partial_messages=True,
            env=env,
            system_prompt=system_prompt,
            resume=resume_session_id or None,
            mcp_servers=mcp_servers or {},
        )
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()

    async def send_message(self, text: str) -> None:
        if not self._client:
            raise RuntimeError("Provider not initialized")
        await self._client.query(text)

    async def stream_response(self) -> AsyncIterator[NormalizedEvent]:
        """Stream Claude SDK messages as NormalizedEvents.

        This is a refactored version of the old stream_claude_response() function
        from server.py. The caller handles database persistence and WebSocket sending.
        """
        if not self._client:
            return

        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                model_name = getattr(message, "model", None)
                if model_name:
                    yield NormalizedEvent("model_info", {"model": model_name})

                for block in message.content:
                    if isinstance(block, TextBlock):
                        yield NormalizedEvent("assistant_text", {"text": block.text})

                    elif isinstance(block, ToolUseBlock):
                        yield NormalizedEvent("tool_use", {
                            "tool": block.name,
                            "id": block.id,
                            "input": block.input,
                        })

                    elif isinstance(block, ToolResultBlock):
                        content_str = ""
                        if isinstance(block.content, str):
                            content_str = block.content
                        elif isinstance(block.content, list):
                            content_str = json.dumps(block.content, default=str)
                        elif block.content is not None:
                            content_str = str(block.content)

                        yield NormalizedEvent("tool_result", {
                            "tool_use_id": block.tool_use_id,
                            "content": content_str,
                            "is_error": block.is_error or False,
                        })

            elif isinstance(message, StreamEvent):
                pass  # Text already handled via AssistantMessage TextBlocks

            elif isinstance(message, ResultMessage):
                yield NormalizedEvent("result", {
                    "text": message.result or "",
                    "session_id": message.session_id,
                    "cost": message.total_cost_usd,
                    "duration_ms": message.duration_ms,
                    "num_turns": message.num_turns,
                    "is_error": message.is_error,
                    "usage": message.usage,
                })

            elif isinstance(message, SDKSystemMessage):
                yield NormalizedEvent("status", {
                    "text": f"System: {message.subtype}",
                })

    async def interrupt(self) -> None:
        if self._client:
            try:
                await self._client.interrupt()
            except Exception:
                pass

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def supports_session_resumption(self) -> bool:
        return True

    def supports_computer_use(self) -> bool:
        return True
