"""OpenAI provider — custom agentic loop with function calling."""

import asyncio
import json
import time
from typing import AsyncIterator, Callable, Awaitable, Any

from .base import BaseProvider, NormalizedEvent
from tools import ToolExecutor
from tools.definitions import get_all_tool_definitions


# Pricing per 1M tokens (USD) — update as needed
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "o4-mini": {"input": 1.10, "output": 4.40},
}

MAX_ITERATIONS = 50  # Safety limit for the agentic loop


class OpenAIProvider(BaseProvider):
    """Provider using OpenAI's function calling for agentic tool use."""

    provider_name = "openai"

    def __init__(self):
        self._client = None
        self._model = "gpt-4o"
        self._system_prompt = ""
        self._messages: list[dict] = []
        self._tool_executor: ToolExecutor | None = None
        self._interrupted = False

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
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model if model and model != "auto" else "gpt-4o"
        self._system_prompt = system_prompt
        self._messages = []
        self._tool_executor = ToolExecutor(cwd=cwd, permission_callback=can_use_tool, agent_id=agent_id)
        self._interrupted = False

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

            # Call OpenAI with streaming
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=api_messages,
                tools=get_all_tool_definitions(),
                stream=True,
                stream_options={"include_usage": True},
            )

            # Accumulate streamed response
            full_content = ""
            tool_calls_map: dict[int, dict] = {}  # index -> {id, name, arguments}

            async for chunk in stream:
                if self._interrupted:
                    break

                # Usage is in the final chunk
                if chunk.usage:
                    total_input_tokens += chunk.usage.prompt_tokens or 0
                    total_output_tokens += chunk.usage.completion_tokens or 0

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Stream text content
                if delta and delta.content:
                    full_content += delta.content
                    yield NormalizedEvent("assistant_text", {"text": delta.content})

                # Accumulate tool call deltas
                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            tool_calls_map[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_map[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_map[idx]["arguments"] += tc_delta.function.arguments

            if self._interrupted:
                break

            last_text = full_content

            # Build tool_calls list from accumulated deltas
            tool_calls = [tool_calls_map[i] for i in sorted(tool_calls_map.keys())]

            # Add assistant message to conversation history
            assistant_msg: dict = {"role": "assistant", "content": full_content or None}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
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

                try:
                    args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    args = {}

                yield NormalizedEvent("tool_use", {
                    "tool": tc["name"],
                    "id": tc["id"],
                    "input": args,
                })

                result = await self._tool_executor.execute(tc["name"], args)

                yield NormalizedEvent("tool_result", {
                    "tool_use_id": tc["id"],
                    "content": result["content"],
                    "is_error": result.get("is_error", False),
                })

                # Add tool result to conversation for next iteration
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result["content"],
                })

        # Emit final result
        elapsed_ms = int((time.time() - start_time) * 1000)
        cost = self._calculate_cost(total_input_tokens, total_output_tokens)

        yield NormalizedEvent("result", {
            "text": last_text,
            "session_id": None,
            "cost": round(cost, 6),
            "duration_ms": elapsed_ms,
            "num_turns": iterations,
            "is_error": False,
            "usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            },
        })

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = MODEL_PRICING.get(self._model, {"input": 2.50, "output": 10.00})
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    async def interrupt(self) -> None:
        self._interrupted = True

    async def disconnect(self) -> None:
        self._client = None
        self._messages = []

    def supports_session_resumption(self) -> bool:
        return False

    def supports_computer_use(self) -> bool:
        return False
