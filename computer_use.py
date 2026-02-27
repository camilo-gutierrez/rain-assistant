"""
computer_use.py — Rain Assistant Computer Use Module

Executes computer use actions on the local PC using PyAutoGUI + mss.
Handles screenshot capture, coordinate scaling, and all mouse/keyboard actions.

Phase 3: Smart screenshot optimization (perceptual hash diff, JPEG compression).
Phase 7: Multi-monitor support (monitor selection, offset coordinates).
"""
import asyncio
import base64
import io
import math
import logging
import time as _time
from typing import Any, Optional

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
COMPUTER_USE_MODEL = "claude-sonnet-4-6"
COMPUTER_USE_MAX_TOKENS = 4096
COMPUTER_USE_MAX_ITERATIONS = 50
COMPUTER_USE_TIMEOUT = 600  # 10 minutes

# ── Phase 3: Smart screenshot constants ──────────────────────────────────
PHASH_DIFF_THRESHOLD = 5       # perceptual hash hamming distance threshold
MAX_CONSECUTIVE_SKIP = 3       # max times to reuse cached screenshot
JPEG_SIZE_THRESHOLD = 200_000  # bytes: if PNG > this, try JPEG q85
MEDIA_PNG = "image/png"
MEDIA_JPEG = "image/jpeg"

# ── Scroll direction → function mapping (module-level) ────────────────────
_SCROLL_FNS = {
    "down": lambda amt: pyautogui.scroll(-amt),
    "up": lambda amt: pyautogui.scroll(amt),
    "left": lambda amt: pyautogui.hscroll(-amt),
    "right": lambda amt: pyautogui.hscroll(amt),
}

# ── Lazy import for perceptual hashing ────────────────────────────────────
_HAS_IMAGEHASH = None  # None = not checked yet


def _check_imagehash():
    global _HAS_IMAGEHASH
    if _HAS_IMAGEHASH is None:
        try:
            import imagehash  # noqa: F401
            _HAS_IMAGEHASH = True
        except ImportError:
            _HAS_IMAGEHASH = False
            logger.info("imagehash not installed — smart screenshot diff disabled")
    return _HAS_IMAGEHASH


COMPUTER_USE_SYSTEM_PROMPT = (
    "You are Rain, an AI assistant with full computer access. "
    "You can see the screen, control the mouse and keyboard. "
    "After each action, take a screenshot to verify the result. "
    "Be precise with clicks. If an action fails, try an alternative approach. "
    "Use keyboard shortcuts when possible (they're more reliable than mouse clicks). "
    "The user's OS is Windows. Respond in Spanish unless told otherwise."
)


class ComputerUseExecutor:
    """Executes computer use actions on the local machine.

    Phase 3: Smart screenshot optimization (perceptual hash diff, JPEG).
    Phase 7: Multi-monitor support (monitor selection, offsets).
    """

    def __init__(
        self,
        display_width: int = 0,
        display_height: int = 0,
        monitor_index: int = 1,
        vision_enabled: bool = False,
    ):
        with mss.mss() as sct:
            self.all_monitors = list(sct.monitors)
            if monitor_index < 1 or monitor_index >= len(sct.monitors):
                monitor_index = 1
            self.monitor_index = monitor_index
            monitor = sct.monitors[monitor_index]
            self.screen_width = display_width or monitor["width"]
            self.screen_height = display_height or monitor["height"]
            self.monitor_left = monitor["left"]
            self.monitor_top = monitor["top"]

        self.scale_factor = self._calculate_scale_factor()
        self.scaled_width = int(self.screen_width * self.scale_factor)
        self.scaled_height = int(self.screen_height * self.scale_factor)
        self.vision_enabled = vision_enabled

        # Phase 3: Smart screenshot state
        self._last_screenshot_hash = None
        self._last_screenshot_b64: Optional[str] = None
        self._last_screenshot_media_type: str = MEDIA_PNG
        self._consecutive_unchanged: int = 0

        logger.info(
            f"ComputerUse: monitor {monitor_index}, "
            f"{self.screen_width}x{self.screen_height} "
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
        """Convert Claude coordinates (scaled space) to real screen coordinates.

        Phase 7: adds monitor offset so coordinates target the correct monitor.
        """
        screen_x = int(x / self.scale_factor)
        screen_y = int(y / self.scale_factor)
        screen_x = max(0, min(screen_x, self.screen_width - 1))
        screen_y = max(0, min(screen_y, self.screen_height - 1))
        # Add monitor offset for multi-monitor setups
        return screen_x + self.monitor_left, screen_y + self.monitor_top

    async def take_screenshot(self) -> str:
        """Capture screen and return as base64 PNG string.

        Phase 7: captures selected monitor instead of hardcoded monitor 1.
        """
        monitor_idx = self.monitor_index

        def _capture():
            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[monitor_idx])
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                img = img.resize(
                    (self.scaled_width, self.scaled_height),
                    Image.LANCZOS,
                )
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", optimize=True)
                return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")

        return await asyncio.to_thread(_capture)

    # ── Phase 3: Smart screenshot methods ─────────────────────────────

    def _compute_phash(self, img: Image.Image) -> object:
        """Compute perceptual hash for an image. Returns hash or None."""
        if not _check_imagehash():
            return None
        try:
            import imagehash
            return imagehash.phash(img)
        except Exception:
            return None

    def _screenshots_differ(self, current_hash) -> bool:
        """Check if current screenshot differs from the last one."""
        if current_hash is None or self._last_screenshot_hash is None:
            return True
        try:
            diff = current_hash - self._last_screenshot_hash
            return diff > PHASH_DIFF_THRESHOLD
        except Exception:
            return True

    async def take_screenshot_smart(self) -> tuple[str, str, bool]:
        """Smart screenshot: skip if unchanged, compress large images.

        Returns (base64_data, media_type, changed).
        """
        monitor_idx = self.monitor_index

        def _capture_and_analyze():
            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[monitor_idx])
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                img = img.resize(
                    (self.scaled_width, self.scaled_height),
                    Image.LANCZOS,
                )
                return img

        img = await asyncio.to_thread(_capture_and_analyze)

        # Compute perceptual hash and check for changes
        current_hash = self._compute_phash(img)
        changed = self._screenshots_differ(current_hash)

        if not changed and self._consecutive_unchanged < MAX_CONSECUTIVE_SKIP:
            # Screen unchanged — reuse cached screenshot
            self._consecutive_unchanged += 1
            logger.debug(
                "Screenshot unchanged (%d/%d), reusing cache",
                self._consecutive_unchanged, MAX_CONSECUTIVE_SKIP,
            )
            return (
                self._last_screenshot_b64,
                self._last_screenshot_media_type,
                False,
            )

        # Screen changed or max skips reached — encode new screenshot
        self._consecutive_unchanged = 0
        self._last_screenshot_hash = current_hash

        def _encode(image):
            buf = io.BytesIO()
            image.save(buf, format="PNG", optimize=True)
            png_bytes = buf.getvalue()

            # Try JPEG compression if PNG is too large
            if len(png_bytes) > JPEG_SIZE_THRESHOLD:
                jpg_buf = io.BytesIO()
                image.save(jpg_buf, format="JPEG", quality=85)
                jpg_bytes = jpg_buf.getvalue()
                if len(jpg_bytes) < len(png_bytes):
                    return base64.standard_b64encode(jpg_bytes).decode("utf-8"), MEDIA_JPEG

            return base64.standard_b64encode(png_bytes).decode("utf-8"), MEDIA_PNG

        b64_data, media_type = await asyncio.to_thread(_encode, img)
        self._last_screenshot_b64 = b64_data
        self._last_screenshot_media_type = media_type

        return b64_data, media_type, True

    def reset_screenshot_cache(self) -> None:
        """Reset smart screenshot state. Call when context changes significantly."""
        self._last_screenshot_hash = None
        self._last_screenshot_b64 = None
        self._last_screenshot_media_type = MEDIA_PNG
        self._consecutive_unchanged = 0

    async def execute_action(self, action: str, params: dict[str, Any]) -> list[dict]:
        """Execute a computer use action and return tool_result content blocks.

        Phase 3: Uses smart screenshots (perceptual hash diff, JPEG compression).
        Always returns a screenshot after executing the action.
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

        # Phase 3: smart screenshot with hash diff + compression
        b64_data, media_type, changed = await self.take_screenshot_smart()
        result = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64_data,
                },
            }
        ]

        if not changed:
            result.append({"type": "text", "text": "[screenshot unchanged]"})

        return result

    async def _do_action(self, action: str, params: dict[str, Any]) -> None:
        """Execute the actual PyAutoGUI action in a thread."""
        handler = self._ACTION_DISPATCH.get(action)
        if handler is None:
            if action == "screenshot":
                return  # Handled by execute_action
            raise ValueError(f"Unknown computer action: {action}")
        await asyncio.to_thread(handler, self, params)

    # ── Individual action handlers ──────────────────────────────────

    def _click_with_modifier(self, params: dict, click_fn) -> None:
        x, y = self._scale_to_screen(*params["coordinate"])
        modifier = params.get("text")
        if modifier:
            pyautogui.keyDown(modifier)
        click_fn(x, y)
        if modifier:
            pyautogui.keyUp(modifier)

    def _act_left_click(self, params: dict) -> None:
        self._click_with_modifier(params, pyautogui.click)

    def _act_right_click(self, params: dict) -> None:
        self._click_with_modifier(params, pyautogui.rightClick)

    def _act_double_click(self, params: dict) -> None:
        x, y = self._scale_to_screen(*params["coordinate"])
        pyautogui.doubleClick(x, y)

    def _act_triple_click(self, params: dict) -> None:
        x, y = self._scale_to_screen(*params["coordinate"])
        pyautogui.tripleClick(x, y)

    def _act_middle_click(self, params: dict) -> None:
        x, y = self._scale_to_screen(*params["coordinate"])
        pyautogui.middleClick(x, y)

    def _act_mouse_move(self, params: dict) -> None:
        x, y = self._scale_to_screen(*params["coordinate"])
        pyautogui.moveTo(x, y)

    def _act_left_click_drag(self, params: dict) -> None:
        start = params.get("start_coordinate", params.get("coordinate"))
        end = params.get("coordinate")
        if start and end:
            sx, sy = self._scale_to_screen(*start)
            ex, ey = self._scale_to_screen(*end)
            pyautogui.moveTo(sx, sy)
            pyautogui.mouseDown()
            pyautogui.moveTo(ex, ey, duration=0.5)
            pyautogui.mouseUp()

    def _act_left_mouse_down(self, _params: dict) -> None:
        pyautogui.mouseDown()

    def _act_left_mouse_up(self, _params: dict) -> None:
        pyautogui.mouseUp()

    def _act_type(self, params: dict) -> None:
        text = params.get("text", "")
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")

    def _act_key(self, params: dict) -> None:
        keys = params.get("text", "")
        if "+" in keys:
            pyautogui.hotkey(*keys.split("+"))
        else:
            pyautogui.press(keys)

    def _act_scroll(self, params: dict) -> None:
        coord = params.get("coordinate", [self.scaled_width // 2, self.scaled_height // 2])
        x, y = self._scale_to_screen(*coord)
        direction = params.get("scroll_direction", "down")
        amount = params.get("scroll_amount", 3)
        pyautogui.moveTo(x, y)
        _SCROLL_FNS[direction](amount)

    def _act_hold_key(self, params: dict) -> None:
        key = params.get("text", "")
        duration = min(params.get("duration", 1.0), 10.0)
        pyautogui.keyDown(key)
        _time.sleep(duration)
        pyautogui.keyUp(key)

    def _act_wait(self, params: dict) -> None:
        duration = min(params.get("duration", 1.0), 10.0)
        _time.sleep(duration)

    _ACTION_DISPATCH: dict[str, Any] = {
        "left_click": _act_left_click,
        "right_click": _act_right_click,
        "double_click": _act_double_click,
        "triple_click": _act_triple_click,
        "middle_click": _act_middle_click,
        "mouse_move": _act_mouse_move,
        "left_click_drag": _act_left_click_drag,
        "left_mouse_down": _act_left_mouse_down,
        "left_mouse_up": _act_left_mouse_up,
        "type": _act_type,
        "key": _act_key,
        "scroll": _act_scroll,
        "hold_key": _act_hold_key,
        "wait": _act_wait,
    }

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
        """Return display info for the frontend.

        Phase 7: includes monitor info for multi-monitor support.
        """
        return {
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "scaled_width": self.scaled_width,
            "scaled_height": self.scaled_height,
            "scale_factor": round(self.scale_factor, 4),
            "monitor_index": self.monitor_index,
            "monitor_count": len(self.all_monitors) - 1,  # exclude virtual monitor [0]
            "monitor_offset": {"left": self.monitor_left, "top": self.monitor_top},
        }

    @staticmethod
    def get_available_monitors() -> list[dict]:
        """Return info about all available monitors.

        Phase 7: used by MonitorSelector frontend component.
        """
        with mss.mss() as sct:
            monitors = []
            for i, mon in enumerate(sct.monitors):
                if i == 0:
                    continue  # skip virtual combined monitor
                monitors.append({
                    "index": i,
                    "width": mon["width"],
                    "height": mon["height"],
                    "left": mon["left"],
                    "top": mon["top"],
                    "primary": i == 1,
                })
            return monitors

    def recalculate_for_resolution(self, monitor_index: int = 0) -> None:
        """Recalculate scaling for a new monitor or resolution change.

        Phase 7: allows mid-session monitor switching.
        """
        with mss.mss() as sct:
            self.all_monitors = list(sct.monitors)
            idx = monitor_index or self.monitor_index
            if idx < 1 or idx >= len(sct.monitors):
                idx = 1
            self.monitor_index = idx
            monitor = sct.monitors[idx]
            self.screen_width = monitor["width"]
            self.screen_height = monitor["height"]
            self.monitor_left = monitor["left"]
            self.monitor_top = monitor["top"]

        self.scale_factor = self._calculate_scale_factor()
        self.scaled_width = int(self.screen_width * self.scale_factor)
        self.scaled_height = int(self.screen_height * self.scale_factor)
        self.reset_screenshot_cache()

        logger.info(
            "Monitor recalculated: %d, %dx%d -> %dx%d (factor: %.3f)",
            self.monitor_index, self.screen_width, self.screen_height,
            self.scaled_width, self.scaled_height, self.scale_factor,
        )


# ── Text Editor Tool ────────────────────────────────────────────────────

async def handle_text_editor(tool_input: dict, cwd: str) -> list[dict]:
    """Handle str_replace_based_edit_tool calls from Claude.

    Supports commands: view, create, str_replace, insert.
    Returns tool_result content blocks.
    """
    import os

    command = tool_input.get("command", "")
    file_path = tool_input.get("path", "")

    if not file_path:
        return [{"type": "text", "text": "Error: 'path' is required."}]

    # Resolve relative paths against cwd
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    file_path = os.path.realpath(file_path)

    # Security: block sensitive directories
    home = os.path.expanduser("~")
    _blocked = [".ssh", ".aws", ".gnupg", ".rain-assistant"]
    for blocked in _blocked:
        if os.path.join(home, blocked) in file_path:
            return [{"type": "text", "text": f"Access denied: cannot access {blocked}"}]

    try:
        if command == "view":
            return await _te_view(file_path, tool_input)
        elif command == "create":
            return await _te_create(file_path, tool_input)
        elif command == "str_replace":
            return await _te_str_replace(file_path, tool_input)
        elif command == "insert":
            return await _te_insert(file_path, tool_input)
        else:
            return [{"type": "text", "text": f"Unknown command: {command}"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


async def _te_view(file_path: str, tool_input: dict) -> list[dict]:
    """View file content with line numbers."""
    import os

    if not os.path.exists(file_path):
        return [{"type": "text", "text": f"File not found: {file_path}"}]

    def _read():
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        view_range = tool_input.get("view_range")
        if view_range and len(view_range) == 2:
            start, end = view_range[0] - 1, view_range[1]
            lines = lines[start:end]
            offset = start
        else:
            offset = 0

        numbered = []
        for i, line in enumerate(lines, start=offset + 1):
            numbered.append(f"{i:6d}\t{line.rstrip()}")

        return "\n".join(numbered)

    content = await asyncio.to_thread(_read)
    # Truncate very large files
    if len(content) > 20000:
        content = content[:20000] + "\n[... truncated]"
    return [{"type": "text", "text": content}]


async def _te_create(file_path: str, tool_input: dict) -> list[dict]:
    """Create a new file with content."""
    import os

    file_text = tool_input.get("file_text", "")

    if os.path.exists(file_path):
        return [{"type": "text", "text": f"File already exists: {file_path}. Use str_replace to edit."}]

    def _write():
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_text)
        line_count = file_text.count("\n") + 1
        return f"File created: {file_path} ({line_count} lines)"

    result = await asyncio.to_thread(_write)
    return [{"type": "text", "text": result}]


async def _te_str_replace(file_path: str, tool_input: dict) -> list[dict]:
    """Replace a string in a file (exact match)."""
    import os

    old_str = tool_input.get("old_str", "")
    new_str = tool_input.get("new_str", "")

    if not old_str:
        return [{"type": "text", "text": "Error: 'old_str' is required."}]
    if not os.path.exists(file_path):
        return [{"type": "text", "text": f"File not found: {file_path}"}]

    def _replace():
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        count = content.count(old_str)
        if count == 0:
            return f"Error: '{old_str[:80]}' not found in {file_path}"
        if count > 1:
            return f"Error: '{old_str[:80]}' found {count} times. Provide more context for a unique match."

        new_content = content.replace(old_str, new_str, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Show context around the edit
        idx = new_content.find(new_str)
        start = max(0, idx - 100)
        end = min(len(new_content), idx + len(new_str) + 100)
        snippet = new_content[start:end]
        return f"Edit applied to {file_path}.\n\nContext:\n{snippet}"

    result = await asyncio.to_thread(_replace)
    return [{"type": "text", "text": result}]


async def _te_insert(file_path: str, tool_input: dict) -> list[dict]:
    """Insert text at a specific line number."""
    import os

    insert_line = tool_input.get("insert_line", 0)
    new_str = tool_input.get("new_str", "")

    if not os.path.exists(file_path):
        return [{"type": "text", "text": f"File not found: {file_path}"}]

    def _insert():
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # insert_line is 1-based, insert after that line
        idx = max(0, min(insert_line, len(lines)))
        new_lines = new_str.split("\n")
        for i, nl in enumerate(new_lines):
            lines.insert(idx + i, nl + "\n")

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return f"Inserted {len(new_lines)} lines at line {insert_line} in {file_path}."

    result = await asyncio.to_thread(_insert)
    return [{"type": "text", "text": result}]


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
