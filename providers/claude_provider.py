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

from .base import BaseProvider, NormalizedEvent, _sanitize_api_error


def _mark_mcp_server_failed(server_name: str, error: str) -> None:
    """Mark an MCP server as failed in shared state."""
    try:
        import shared_state
        shared_state.mcp_server_status[server_name] = {
            "status": "error",
            "error": error,
        }
    except Exception:
        pass


def _mark_all_mcp_servers_failed(mcp_config: dict, error: str) -> None:
    """Mark all MCP servers in a flat config dict as failed."""
    for name in mcp_config:
        _mark_mcp_server_failed(name, error)


class ClaudeProvider(BaseProvider):
    """Provider that wraps the Claude Agent SDK (existing Rain behavior)."""

    provider_name = "claude"

    def __init__(self):
        self._client: ClaudeSDKClient | None = None
        # Track which MCP servers failed during connect so callers can notify
        self.failed_mcp_servers: list[str] = []

    def _build_options(
        self,
        cwd: str,
        model: str,
        can_use_tool: Callable[..., Awaitable[Any]] | None,
        env: dict,
        system_prompt: str,
        resume_session_id: str | None,
        mcp_config: dict | str,
    ) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions with the given MCP config."""
        return ClaudeAgentOptions(
            cwd=cwd,
            model=model if model and model != "auto" else None,
            permission_mode="default",
            can_use_tool=can_use_tool,
            include_partial_messages=True,
            env=env,
            system_prompt=system_prompt,
            resume=resume_session_id or None,
            mcp_servers=mcp_config,
        )

    async def _try_connect(self, options: ClaudeAgentOptions) -> None:
        """Create a client and attempt to connect."""
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()

    async def _try_progressive_fallback(
        self,
        server_dict: dict,
        error_str: str,
        cwd: str,
        model: str,
        can_use_tool: Callable[..., Awaitable[Any]] | None,
        env: dict,
        system_prompt: str,
        resume_session_id: str | None,
    ) -> bool:
        """Try connecting by removing MCP servers one at a time.

        Args:
            server_dict: Flat dict ``{"server-name": config, ...}``

        Returns True if a reduced set succeeded, False otherwise.
        """
        server_names = list(server_dict.keys())
        if len(server_names) <= 1:
            return False

        for skip_name in server_names:
            remaining = {k: v for k, v in server_dict.items() if k != skip_name}
            if not remaining:
                continue

            try:
                reduced_options = self._build_options(
                    cwd, model, can_use_tool, env,
                    system_prompt, resume_session_id, remaining,
                )
                await self._try_connect(reduced_options)
            except Exception:
                continue

            # Success — the skipped server was the problem
            self.failed_mcp_servers.append(skip_name)
            _mark_mcp_server_failed(skip_name, f"Server failed to start: {error_str}")
            ok_names = ", ".join(remaining.keys())
            print(
                f"  [MCP] Server '{skip_name}' disabled (failed to start). "
                f"Active: {ok_names}",
                flush=True,
            )
            return True

        return False

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
        env = {"ANTHROPIC_API_KEY": api_key} if api_key else {}
        resolved_mcp = mcp_servers or {}
        self.failed_mcp_servers = []

        options = self._build_options(
            cwd, model, can_use_tool, env, system_prompt, resume_session_id,
            resolved_mcp,
        )

        try:
            await self._try_connect(options)
            return  # Success with all MCP servers
        except Exception as e:
            if not resolved_mcp:
                raise  # No MCP servers configured — nothing to degrade

            error_str = str(e)
            print(
                f"  [MCP] Warning: connect() failed with MCP servers ({e}). "
                "Attempting per-server fallback...",
                flush=True,
            )

        # --- Progressive MCP server removal ---
        # The flat dict format {"server-name": config, ...} lets us remove
        # servers one at a time. String-based configs cannot be decomposed.
        if isinstance(resolved_mcp, dict) and len(resolved_mcp) > 1:
            success = await self._try_progressive_fallback(
                resolved_mcp, error_str, cwd, model, can_use_tool,
                env, system_prompt, resume_session_id,
            )
            if success:
                return

        # Mark all servers as failed
        if isinstance(resolved_mcp, dict):
            _mark_all_mcp_servers_failed(resolved_mcp, f"All servers failed: {error_str}")
            self.failed_mcp_servers = list(resolved_mcp.keys())

        # Final fallback: start without any MCP servers
        print(
            "  [MCP] Warning: Could not start with any MCP servers. "
            "Starting without MCP...",
            flush=True,
        )
        fallback_options = self._build_options(
            cwd, model, can_use_tool, env, system_prompt,
            resume_session_id, {},
        )
        await self._try_connect(fallback_options)
        print("  [MCP] Agent started without MCP servers.", flush=True)

    async def send_message(self, text: str, images: list[dict] | None = None) -> None:
        if not self._client:
            raise RuntimeError("Provider not initialized")

        if images:
            # Build multi-part content: images first, then text
            content_blocks: list[dict] = []
            for img in images:
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("mediaType", "image/png"),
                        "data": img["base64"],
                    },
                })
            content_blocks.append({"type": "text", "text": text})

            # SDK iterable mode expects: {"type": "user", "message": {...}}
            async def _content_iter():
                yield {
                    "type": "user",
                    "message": {"role": "user", "content": content_blocks},
                    "parent_tool_use_id": None,
                }

            await self._client.query(_content_iter())
        else:
            await self._client.query(text)

    async def stream_response(self) -> AsyncIterator[NormalizedEvent]:
        """Stream Claude SDK messages as NormalizedEvents.

        This is a refactored version of the old stream_claude_response() function
        from server.py. The caller handles database persistence and WebSocket sending.
        """
        if not self._client:
            return

        try:
            # Wrap the SDK iterator to survive unknown message types
            # (e.g. rate_limit_event) that the SDK doesn't handle
            response_iter = self._client.receive_response().__aiter__()
            while True:
                try:
                    message = await response_iter.__anext__()
                except StopAsyncIteration:
                    break
                except Exception as iter_err:
                    # SDK raised on an unrecognized message — skip and continue
                    print(f"  [Claude] Skipping SDK event: {iter_err}", flush=True)
                    continue

                try:
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

                    # else: silently ignore unknown message types (e.g. rate_limit_event)

                except Exception as inner_err:
                    # Don't break the stream for a single bad message
                    print(f"  [Claude] Skipping message: {inner_err}", flush=True)
                    continue

        except Exception as e:
            yield NormalizedEvent("error", {"text": _sanitize_api_error("Claude", e)})

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
