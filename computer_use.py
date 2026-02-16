"""
computer_use.py — Rain Assistant Computer Use Module

Executes computer use actions on the local PC using PyAutoGUI + mss.
Handles screenshot capture, coordinate scaling, and all mouse/keyboard actions.
"""
import asyncio
import base64
import io
import math
import logging
import time as _time
from typing import Any

import pyautogui
import mss
from PIL import Image

logger = logging.getLogger("rain.computer_use")

# ── PyAutoGUI safety config ──────────────────────────────────────────────
pyautogui.FAILSAFE = True       # Move mouse to top-left corner = ABORT
pyautogui.PAUSE = 0.1           # 100ms pause between actions

# ── Anthropic API image constraints ──────────────────────────────────────
MAX_LONG_EDGE = 1568
MAX_TOTAL_PIXELS = 1_150_000

# ── Computer Use API constants ───────────────────────────────────────────
COMPUTER_USE_BETA = "computer-use-2025-01-24"
COMPUTER_USE_MODEL = "claude-sonnet-4-5"
COMPUTER_USE_MAX_TOKENS = 4096
COMPUTER_USE_MAX_ITERATIONS = 50
COMPUTER_USE_TIMEOUT = 600  # 10 minutes

COMPUTER_USE_SYSTEM_PROMPT = (
    "You are Rain, an AI assistant with full computer access. "
    "You can see the screen, control the mouse and keyboard. "
    "After each action, take a screenshot to verify the result. "
    "Be precise with clicks. If an action fails, try an alternative approach. "
    "Use keyboard shortcuts when possible (they're more reliable than mouse clicks). "
    "The user's OS is Windows. Respond in Spanish unless told otherwise."
)


class ComputerUseExecutor:
    """Executes computer use actions on the local machine."""

    def __init__(self, display_width: int = 0, display_height: int = 0):
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            self.screen_width = display_width or monitor["width"]
            self.screen_height = display_height or monitor["height"]

        self.scale_factor = self._calculate_scale_factor()
        self.scaled_width = int(self.screen_width * self.scale_factor)
        self.scaled_height = int(self.screen_height * self.scale_factor)

        logger.info(
            f"ComputerUse: {self.screen_width}x{self.screen_height} "
            f"-> scaled {self.scaled_width}x{self.scaled_height} "
            f"(factor: {self.scale_factor:.3f})"
        )

    def _calculate_scale_factor(self) -> float:
        """Calculate scale factor to meet Anthropic API image constraints."""
        long_edge = max(self.screen_width, self.screen_height)
        total_pixels = self.screen_width * self.screen_height

        long_edge_scale = MAX_LONG_EDGE / long_edge
        total_pixels_scale = math.sqrt(MAX_TOTAL_PIXELS / total_pixels)

        return min(1.0, long_edge_scale, total_pixels_scale)

    def _scale_to_screen(self, x: int, y: int) -> tuple[int, int]:
        """Convert Claude coordinates (scaled space) to real screen coordinates."""
        screen_x = int(x / self.scale_factor)
        screen_y = int(y / self.scale_factor)
        screen_x = max(0, min(screen_x, self.screen_width - 1))
        screen_y = max(0, min(screen_y, self.screen_height - 1))
        return screen_x, screen_y

    async def take_screenshot(self) -> str:
        """Capture screen and return as base64 PNG string."""
        def _capture():
            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                img = img.resize(
                    (self.scaled_width, self.scaled_height),
                    Image.LANCZOS,
                )
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", optimize=True)
                return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")

        return await asyncio.to_thread(_capture)

    async def execute_action(self, action: str, params: dict[str, Any]) -> list[dict]:
        """Execute a computer use action and return tool_result content blocks.

        Always returns a screenshot after executing the action (except for screenshot itself).
        """
        try:
            await self._do_action(action, params)
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI FAILSAFE triggered! Mouse moved to corner.")
            return [{"type": "text", "text": "EMERGENCY: FailSafe triggered. All actions halted."}]
        except Exception as e:
            logger.error(f"Computer action failed: {action} - {e}")
            return [{"type": "text", "text": f"Error executing {action}: {str(e)}"}]

        # Wait for UI to update after action
        if action != "screenshot":
            await asyncio.sleep(0.3)

        screenshot_b64 = await self.take_screenshot()
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot_b64,
                },
            }
        ]

    async def _do_action(self, action: str, params: dict[str, Any]) -> None:
        """Execute the actual PyAutoGUI action in a thread."""

        def _run():
            if action == "screenshot":
                pass  # Handled by execute_action

            elif action == "left_click":
                x, y = self._scale_to_screen(*params["coordinate"])
                modifier = params.get("text")
                if modifier:
                    pyautogui.keyDown(modifier)
                pyautogui.click(x, y)
                if modifier:
                    pyautogui.keyUp(modifier)

            elif action == "right_click":
                x, y = self._scale_to_screen(*params["coordinate"])
                modifier = params.get("text")
                if modifier:
                    pyautogui.keyDown(modifier)
                pyautogui.rightClick(x, y)
                if modifier:
                    pyautogui.keyUp(modifier)

            elif action == "double_click":
                x, y = self._scale_to_screen(*params["coordinate"])
                pyautogui.doubleClick(x, y)

            elif action == "triple_click":
                x, y = self._scale_to_screen(*params["coordinate"])
                pyautogui.tripleClick(x, y)

            elif action == "middle_click":
                x, y = self._scale_to_screen(*params["coordinate"])
                pyautogui.middleClick(x, y)

            elif action == "mouse_move":
                x, y = self._scale_to_screen(*params["coordinate"])
                pyautogui.moveTo(x, y)

            elif action == "left_click_drag":
                start = params.get("start_coordinate", params.get("coordinate"))
                end = params.get("coordinate")
                if start and end:
                    sx, sy = self._scale_to_screen(*start)
                    ex, ey = self._scale_to_screen(*end)
                    pyautogui.moveTo(sx, sy)
                    pyautogui.mouseDown()
                    pyautogui.moveTo(ex, ey, duration=0.5)
                    pyautogui.mouseUp()

            elif action == "left_mouse_down":
                pyautogui.mouseDown()

            elif action == "left_mouse_up":
                pyautogui.mouseUp()

            elif action == "type":
                text = params.get("text", "")
                # PyAutoGUI typewrite only supports ASCII.
                # Use clipboard for full Unicode support (Spanish, emojis, etc.)
                import pyperclip
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")

            elif action == "key":
                keys = params.get("text", "")
                if "+" in keys:
                    pyautogui.hotkey(*keys.split("+"))
                else:
                    pyautogui.press(keys)

            elif action == "scroll":
                coord = params.get("coordinate", [self.scaled_width // 2, self.scaled_height // 2])
                x, y = self._scale_to_screen(*coord)
                direction = params.get("scroll_direction", "down")
                amount = params.get("scroll_amount", 3)

                pyautogui.moveTo(x, y)
                if direction == "down":
                    pyautogui.scroll(-amount)
                elif direction == "up":
                    pyautogui.scroll(amount)
                elif direction == "left":
                    pyautogui.hscroll(-amount)
                elif direction == "right":
                    pyautogui.hscroll(amount)

            elif action == "hold_key":
                key = params.get("text", "")
                duration = min(params.get("duration", 1.0), 10.0)
                pyautogui.keyDown(key)
                _time.sleep(duration)
                pyautogui.keyUp(key)

            elif action == "wait":
                duration = min(params.get("duration", 1.0), 10.0)
                _time.sleep(duration)

            else:
                raise ValueError(f"Unknown computer action: {action}")

        await asyncio.to_thread(_run)

    def release_all(self) -> None:
        """Release all held keys and mouse buttons. Used by emergency stop."""
        try:
            pyautogui.mouseUp()
            for key in ("shift", "ctrl", "alt", "win"):
                try:
                    pyautogui.keyUp(key)
                except Exception:
                    pass
        except Exception:
            pass

    def get_tool_definition(self) -> dict:
        """Return the tool definition for the Anthropic API."""
        return {
            "type": "computer_20250124",
            "name": "computer",
            "display_width_px": self.scaled_width,
            "display_height_px": self.scaled_height,
        }

    def get_display_info(self) -> dict:
        """Return display info for the frontend."""
        return {
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "scaled_width": self.scaled_width,
            "scaled_height": self.scaled_height,
            "scale_factor": round(self.scale_factor, 4),
        }


def describe_action(tool_name: str, tool_input: dict) -> str:
    """Generate a human-readable description of a computer use action."""
    if tool_name == "computer":
        action = tool_input.get("action", "unknown")
        if action == "screenshot":
            return "Capturar pantalla"
        elif action in ("left_click", "right_click", "double_click", "middle_click"):
            coord = tool_input.get("coordinate", [0, 0])
            label = action.replace("_", " ").title()
            return f"{label} en ({coord[0]}, {coord[1]})"
        elif action == "triple_click":
            coord = tool_input.get("coordinate", [0, 0])
            return f"Triple click en ({coord[0]}, {coord[1]})"
        elif action == "type":
            text = tool_input.get("text", "")[:50]
            return f'Escribir: "{text}"'
        elif action == "key":
            return f"Tecla: {tool_input.get('text', '')}"
        elif action == "scroll":
            direction = tool_input.get("scroll_direction", "down")
            return f"Scroll {direction}"
        elif action == "mouse_move":
            coord = tool_input.get("coordinate", [0, 0])
            return f"Mover raton a ({coord[0]}, {coord[1]})"
        elif action == "left_click_drag":
            coord = tool_input.get("coordinate", [0, 0])
            return f"Arrastrar a ({coord[0]}, {coord[1]})"
        elif action == "wait":
            return f"Esperar {tool_input.get('duration', 1)}s"
        elif action == "hold_key":
            return f"Mantener tecla: {tool_input.get('text', '')}"
        else:
            return f"Accion: {action}"
    elif tool_name == "bash":
        cmd = tool_input.get("command", "")[:80]
        return f"Ejecutar: {cmd}"
    elif tool_name == "str_replace_based_edit_tool":
        path = tool_input.get("path", "")
        return f"Editar archivo: {path}"
    return f"Tool: {tool_name}"
