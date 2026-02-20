"""Ollama provider — local AI models with optional tool calling."""

import json
import time
import uuid
from typing import AsyncIterator, Callable, Awaitable, Any

from .base import BaseProvider, NormalizedEvent
from tools import ToolExecutor
from tools.definitions import get_all_tool_definitions


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1"
MAX_ITERATIONS = 50  # Safety limit for the agentic loop


def _convert_tools_for_ollama(tool_defs: list[dict]) -> list[dict]:
    """Convert OpenAI-format tool definitions to Ollama format.

    Ollama uses an OpenAI-compatible format for tool calling, so the
    conversion is minimal — we just ensure the structure is correct.
    """
    tools = []
    for tool in tool_defs:
        tools.append({
            "type": "function",
            "function": {
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "parameters": tool["function"]["parameters"],
            },
        })
    return tools


class OllamaProvider(BaseProvider):
    """Provider using Ollama for local AI model inference with optional tool calling."""

    provider_name = "ollama"

    def __init__(self):
        self._client = None
        self._model = DEFAULT_MODEL
        self._system_prompt = ""
        self._messages: list[dict] = []
        self._tool_executor: ToolExecutor | None = None
        self._interrupted = False
        self._tools: list[dict] = []
        self._supports_tools = True  # Will be set to False if model doesn't support tools

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
        import ollama

        # api_key is used as the base URL for Ollama
        base_url = api_key.strip() if api_key and api_key.strip() else DEFAULT_BASE_URL

        # Ensure the URL has a scheme
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            base_url = "http://" + base_url

        self._client = ollama.AsyncClient(host=base_url)
        self._model = model if model and model != "auto" else DEFAULT_MODEL
        self._system_prompt = system_prompt
        self._messages = []
        self._tool_executor = ToolExecutor(cwd=cwd, permission_callback=can_use_tool, agent_id=agent_id)
        self._interrupted = False
        self._supports_tools = True

        # Pre-convert tools
        self._tools = _convert_tools_for_ollama(get_all_tool_definitions())

    async def send_message(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})
        self._interrupted = False

    async def stream_response(self) -> AsyncIterator[NormalizedEvent]:
        if not self._client or not self._tool_executor:
            return

        yield NormalizedEvent("model_info", {"model": self._model})

        iterations = 0
        total_input_tokens = 0
        total_output_tokens = 0
        start_time = time.time()
        last_text = ""

        while iterations < MAX_ITERATIONS and not self._interrupted:
            iterations += 1

            # Build messages with system prompt
            api_messages = [{"role": "system", "content": self._system_prompt}] + self._messages

            # Call Ollama with streaming
            try:
                kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": api_messages,
                    "stream": True,
                }

                # Only include tools if the model supports them
                if self._supports_tools and self._tools:
                    kwargs["tools"] = self._tools

                stream = await self._client.chat(**kwargs)
            except Exception as e:
                error_msg = str(e)
                # Some models don't support tool calling — retry without tools
                if self._supports_tools and ("tool" in error_msg.lower() or "function" in error_msg.lower()):
                    self._supports_tools = False
                    kwargs.pop("tools", None)
                    try:
                        stream = await self._client.chat(**kwargs)
                    except Exception as e2:
                        yield NormalizedEvent("error", {"text": f"Ollama error: {e2}"})
                        return
                else:
                    yield NormalizedEvent("error", {"text": f"Ollama error: {e}"})
                    return

            # Accumulate streamed response
            full_content = ""
            tool_calls: list[dict] = []

            try:
                async for chunk in stream:
                    if self._interrupted:
                        break

                    # chunk is a ChatResponse pydantic model
                    message = chunk.message

                    # Stream text content
                    content = message.content or ""
                    if content:
                        full_content += content
                        yield NormalizedEvent("assistant_text", {"text": content})

                    # Collect tool calls (Ollama returns them in the message)
                    if message.tool_calls:
                        for tc in message.tool_calls:
                            tool_calls.append({
                                "id": f"call_{uuid.uuid4().hex[:24]}",
                                "name": tc.function.name,
                                "arguments": dict(tc.function.arguments) if tc.function.arguments else {},
                            })

                    # Track token usage from the final chunk
                    if chunk.done:
                        total_input_tokens += chunk.prompt_eval_count or 0
                        total_output_tokens += chunk.eval_count or 0

            except Exception as e:
                error_msg = str(e)
                # Handle tool-related errors mid-stream
                if self._supports_tools and ("tool" in error_msg.lower() or "function" in error_msg.lower()):
                    self._supports_tools = False
                    # We already have partial content, just stop trying tools
                    tool_calls = []
                else:
                    yield NormalizedEvent("error", {"text": f"Ollama stream error: {e}"})
                    return

            if self._interrupted:
                break

            last_text = full_content

            # Add assistant message to conversation history
            assistant_msg: dict = {"role": "assistant", "content": full_content or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for tc in tool_calls
                ]
            self._messages.append(assistant_msg)

            # If no tool calls, we are done
            if not tool_calls:
                break

            # Execute each tool call
            for tc in tool_calls:
                if self._interrupted:
                    break

                # Arguments should already be a dict from the pydantic model,
                # but handle JSON strings defensively
                args = tc["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                yield NormalizedEvent("tool_use", {
                    "tool": tc["name"],
                    "id": tc["id"],
                    "input": args,
                })

                try:
                    result = await self._tool_executor.execute(tc["name"], args)
                except Exception as e:
                    result = {"content": f"Tool execution error: {e}", "is_error": True}

                yield NormalizedEvent("tool_result", {
                    "tool_use_id": tc["id"],
                    "content": result["content"],
                    "is_error": result.get("is_error", False),
                })

                # Add tool result to conversation for next iteration
                self._messages.append({
                    "role": "tool",
                    "content": result["content"],
                })

        # Emit final result
        elapsed_ms = int((time.time() - start_time) * 1000)

        yield NormalizedEvent("result", {
            "text": last_text,
            "session_id": None,
            "cost": 0.0,  # Local models are free
            "duration_ms": elapsed_ms,
            "num_turns": iterations,
            "is_error": False,
            "usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            },
        })

    async def interrupt(self) -> None:
        self._interrupted = True

    async def disconnect(self) -> None:
        self._client = None
        self._messages = []

    def supports_session_resumption(self) -> bool:
        return False

    def supports_computer_use(self) -> bool:
        return False
