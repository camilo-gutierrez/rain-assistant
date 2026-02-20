"""Gemini provider — custom agentic loop with function calling.

Uses the native async methods from the google-generativeai SDK (v0.8+):
  - ChatSession.send_message_async() instead of blocking send_message()

This avoids the need for loop.run_in_executor() and plays nicely with the
asyncio event loop that the rest of Rain's backend relies on.
"""

import json
import time
from typing import AsyncIterator, Callable, Awaitable, Any

from .base import BaseProvider, NormalizedEvent
from tools import ToolExecutor
from tools.definitions import get_all_tool_definitions_gemini


# Pricing per 1M tokens (USD) — update as needed
MODEL_PRICING = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash-lite": {"input": 0.0, "output": 0.0},  # Free tier
}

MAX_ITERATIONS = 50


class GeminiProvider(BaseProvider):
    """Provider using Google Gemini's function calling for agentic tool use.

    The google-generativeai SDK exposes async-native methods
    (send_message_async, generate_content_async) so we call those directly
    instead of wrapping the sync API in run_in_executor().
    """

    provider_name = "gemini"

    def __init__(self):
        self._model = None
        self._model_name = "gemini-2.0-flash"
        self._chat = None
        self._tool_executor: ToolExecutor | None = None
        self._interrupted = False
        self._genai = None

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
        import google.generativeai as genai

        self._genai = genai
        genai.configure(api_key=api_key)

        self._model_name = model if model and model != "auto" else "gemini-2.0-flash"

        gemini_tools = get_all_tool_definitions_gemini()

        self._model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
            tools=gemini_tools,
        )
        self._chat = self._model.start_chat()
        self._tool_executor = ToolExecutor(cwd=cwd, permission_callback=can_use_tool, agent_id=agent_id)
        self._interrupted = False

    async def send_message(self, text: str) -> None:
        self._pending_text = text
        self._interrupted = False

    async def stream_response(self) -> AsyncIterator[NormalizedEvent]:
        if not self._model or not self._chat or not self._tool_executor:
            return

        yield NormalizedEvent("model_info", {"model": self._model_name})

        iterations = 0
        total_input_tokens = 0
        total_output_tokens = 0
        start_time = time.time()
        last_text = ""
        current_content = self._pending_text

        while iterations < MAX_ITERATIONS and not self._interrupted:
            iterations += 1

            # Send message to Gemini using native async API
            try:
                response = await self._chat.send_message_async(current_content)
            except Exception as e:
                yield NormalizedEvent("error", {"text": f"Gemini API error: {e}"})
                break

            if self._interrupted:
                break

            # Track usage
            if hasattr(response, "usage_metadata"):
                um = response.usage_metadata
                total_input_tokens += getattr(um, "prompt_token_count", 0) or 0
                total_output_tokens += getattr(um, "candidates_token_count", 0) or 0

            # Process response parts
            function_calls = []
            text_content = ""

            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        text_content += part.text
                        yield NormalizedEvent("assistant_text", {"text": part.text})

                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        # Convert proto args to dict
                        args = dict(fc.args) if fc.args else {}
                        function_calls.append({
                            "name": fc.name,
                            "args": args,
                        })

            last_text = text_content

            # If no function calls, we are done
            if not function_calls:
                break

            # Execute function calls and build response parts
            from google.generativeai.types import content_types
            response_parts = []

            for fc in function_calls:
                if self._interrupted:
                    break

                # Generate a pseudo-ID for the tool call
                tool_id = f"call_{fc['name']}_{iterations}"

                yield NormalizedEvent("tool_use", {
                    "tool": fc["name"],
                    "id": tool_id,
                    "input": fc["args"],
                })

                result = await self._tool_executor.execute(fc["name"], fc["args"])

                yield NormalizedEvent("tool_result", {
                    "tool_use_id": tool_id,
                    "content": result["content"],
                    "is_error": result.get("is_error", False),
                })

                # Build Gemini function response part
                response_parts.append(
                    self._genai.protos.Part(
                        function_response=self._genai.protos.FunctionResponse(
                            name=fc["name"],
                            response={"result": result["content"]},
                        )
                    )
                )

            if self._interrupted:
                break

            # Send tool results back to Gemini for next iteration
            current_content = response_parts

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
        pricing = MODEL_PRICING.get(self._model_name, {"input": 0.10, "output": 0.40})
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    async def interrupt(self) -> None:
        self._interrupted = True

    async def disconnect(self) -> None:
        self._model = None
        self._chat = None

    def supports_session_resumption(self) -> bool:
        return False

    def supports_computer_use(self) -> bool:
        return False
