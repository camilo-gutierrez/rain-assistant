"""Tests for the Computer Use module.

Covers: ComputerUseExecutor initialization, scale factor calculation,
coordinate scaling, screenshot capture, action dispatch, text editor tool,
describe_action, and security blocking.
"""

import base64
import math
import os
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_mock_sct(monitors=None):
    """Create a mock mss screen capture context."""
    if monitors is None:
        monitors = [
            {"width": 3840, "height": 2160, "left": 0, "top": 0},   # virtual
            {"width": 1920, "height": 1080, "left": 0, "top": 0},   # primary
        ]
    mock_sct = MagicMock()
    mock_sct.monitors = monitors
    grab_result = MagicMock()
    w, h = monitors[1]["width"], monitors[1]["height"]
    grab_result.size = (w, h)
    grab_result.bgra = b'\x00' * (w * h * 4)
    mock_sct.grab.return_value = grab_result
    return mock_sct


def _patch_mss(mock_sct):
    """Return a patch context for mss.mss() that yields mock_sct."""
    mock_mss = MagicMock()
    mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
    mock_mss.return_value.__exit__ = MagicMock(return_value=False)
    return patch('computer_use.mss.mss', mock_mss)


@pytest.fixture
def mock_sct():
    return _make_mock_sct()


@pytest.fixture
def executor(mock_sct):
    """Create a ComputerUseExecutor with mocked mss."""
    with _patch_mss(mock_sct):
        from computer_use import ComputerUseExecutor
        exe = ComputerUseExecutor()
    return exe


@pytest.fixture
def mock_pyautogui():
    """Patch all pyautogui functions used by computer_use."""
    with patch('computer_use.pyautogui') as mock_pag:
        mock_pag.FAILSAFE = True
        mock_pag.PAUSE = 0.1
        mock_pag.FailSafeException = type('FailSafeException', (Exception,), {})
        yield mock_pag


# ===========================================================================
# Initialization tests
# ===========================================================================


class TestComputerUseInit:
    """Tests for ComputerUseExecutor.__init__ and monitor selection."""

    def test_init_default_monitor(self, mock_sct):
        with _patch_mss(mock_sct):
            from computer_use import ComputerUseExecutor
            exe = ComputerUseExecutor()
        assert exe.screen_width == 1920
        assert exe.screen_height == 1080
        assert exe.monitor_index == 1
        assert exe.monitor_left == 0
        assert exe.monitor_top == 0

    def test_init_explicit_resolution(self, mock_sct):
        with _patch_mss(mock_sct):
            from computer_use import ComputerUseExecutor
            exe = ComputerUseExecutor(display_width=1280, display_height=720)
        assert exe.screen_width == 1280
        assert exe.screen_height == 720

    def test_init_invalid_monitor_index_falls_back_to_1(self):
        sct = _make_mock_sct()
        with _patch_mss(sct):
            from computer_use import ComputerUseExecutor
            exe = ComputerUseExecutor(monitor_index=99)
        assert exe.monitor_index == 1

    def test_init_multi_monitor(self):
        monitors = [
            {"width": 5760, "height": 2160, "left": 0, "top": 0},   # virtual
            {"width": 1920, "height": 1080, "left": 0, "top": 0},   # primary
            {"width": 2560, "height": 1440, "left": 1920, "top": 0},  # secondary
        ]
        sct = _make_mock_sct(monitors)
        with _patch_mss(sct):
            from computer_use import ComputerUseExecutor
            exe = ComputerUseExecutor(monitor_index=2)
        assert exe.screen_width == 2560
        assert exe.screen_height == 1440
        assert exe.monitor_left == 1920
        assert exe.monitor_top == 0
        assert exe.monitor_index == 2

    def test_init_smart_screenshot_state(self, executor):
        assert executor._last_screenshot_hash is None
        assert executor._last_screenshot_b64 is None
        assert executor._last_screenshot_media_type == "image/png"
        assert executor._consecutive_unchanged == 0


# ===========================================================================
# Scale factor tests
# ===========================================================================


class TestScaleFactor:
    """Tests for _calculate_scale_factor with various resolutions."""

    def _make_executor_at(self, width, height):
        monitors = [
            {"width": width + height, "height": height, "left": 0, "top": 0},
            {"width": width, "height": height, "left": 0, "top": 0},
        ]
        sct = _make_mock_sct(monitors)
        with _patch_mss(sct):
            from computer_use import ComputerUseExecutor
            return ComputerUseExecutor()

    def test_1920x1080_scale(self):
        exe = self._make_executor_at(1920, 1080)
        # long_edge_scale = 1568/1920 ~ 0.8167
        # pixel_scale = sqrt(1_150_000 / (1920*1080)) ~ 0.7445
        expected = min(1.0, 1568 / 1920, math.sqrt(1_150_000 / (1920 * 1080)))
        assert abs(exe.scale_factor - expected) < 0.001

    def test_3840x2160_4k(self):
        exe = self._make_executor_at(3840, 2160)
        expected = min(1.0, 1568 / 3840, math.sqrt(1_150_000 / (3840 * 2160)))
        assert abs(exe.scale_factor - expected) < 0.001
        assert exe.scale_factor < 0.5  # 4K needs significant downscaling

    def test_800x600_no_upscale(self):
        exe = self._make_executor_at(800, 600)
        # Both constraints allow >= 1.0, so factor should be 1.0 (no upscale)
        assert exe.scale_factor == 1.0

    def test_scaled_dimensions_are_ints(self):
        exe = self._make_executor_at(1920, 1080)
        assert isinstance(exe.scaled_width, int)
        assert isinstance(exe.scaled_height, int)


# ===========================================================================
# Coordinate scaling tests
# ===========================================================================


class TestCoordinateScaling:
    """Tests for _scale_to_screen coordinate conversion."""

    def test_basic_scaling(self, executor):
        # With scale_factor for 1920x1080, a coordinate in scaled space
        # should map back to real screen coordinates
        sf = executor.scale_factor
        # Center of scaled space
        cx = executor.scaled_width // 2
        cy = executor.scaled_height // 2
        rx, ry = executor._scale_to_screen(cx, cy)
        # Should be close to center of real screen
        assert abs(rx - 960) < 5
        assert abs(ry - 540) < 5

    def test_origin_maps_to_monitor_offset(self):
        monitors = [
            {"width": 3840, "height": 1080, "left": 0, "top": 0},
            {"width": 1920, "height": 1080, "left": 1920, "top": 100},
        ]
        sct = _make_mock_sct(monitors)
        with _patch_mss(sct):
            from computer_use import ComputerUseExecutor
            exe = ComputerUseExecutor()
        rx, ry = exe._scale_to_screen(0, 0)
        # Origin should include monitor offset
        assert rx == 1920
        assert ry == 100

    def test_clamping_prevents_overflow(self, executor):
        # Very large coordinates should be clamped
        rx, ry = executor._scale_to_screen(99999, 99999)
        assert rx <= executor.screen_width + executor.monitor_left
        assert ry <= executor.screen_height + executor.monitor_top


# ===========================================================================
# Screenshot tests
# ===========================================================================


class TestScreenshot:
    """Tests for take_screenshot and take_screenshot_smart."""

    @pytest.mark.asyncio
    async def test_take_screenshot_returns_base64(self, executor):
        mock_sct = _make_mock_sct()
        mock_img = MagicMock()
        mock_img.resize.return_value = mock_img
        mock_buf = MagicMock()
        mock_buf.getvalue.return_value = b'\x89PNG_FAKE_DATA'

        with _patch_mss(mock_sct), \
             patch('computer_use.Image.frombytes', return_value=mock_img), \
             patch('computer_use.io.BytesIO', return_value=mock_buf):
            result = await executor.take_screenshot()

        assert isinstance(result, str)
        # Should be valid base64
        decoded = base64.b64decode(result)
        assert decoded == b'\x89PNG_FAKE_DATA'

    @pytest.mark.asyncio
    async def test_take_screenshot_smart_returns_tuple(self, executor):
        mock_sct = _make_mock_sct()
        mock_img = MagicMock()
        mock_img.resize.return_value = mock_img
        mock_buf = MagicMock()
        mock_buf.getvalue.return_value = b'\x89PNG_SMALL'

        with _patch_mss(mock_sct), \
             patch('computer_use.Image.frombytes', return_value=mock_img), \
             patch('computer_use.io.BytesIO', return_value=mock_buf), \
             patch('computer_use._check_imagehash', return_value=False):
            b64, media, changed = await executor.take_screenshot_smart()

        assert isinstance(b64, str)
        assert media in ("image/png", "image/jpeg")
        assert changed is True  # First call is always "changed"


# ===========================================================================
# Action dispatch tests
# ===========================================================================


class TestActionDispatch:
    """Tests for execute_action and individual action handlers."""

    @pytest.mark.asyncio
    async def test_left_click(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            result = await executor.execute_action("left_click", {
                "coordinate": [100, 200]
            })
        mock_pyautogui.click.assert_called_once()
        assert result[0]["type"] == "image"

    @pytest.mark.asyncio
    async def test_right_click(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("right_click", {
                "coordinate": [50, 50]
            })
        mock_pyautogui.rightClick.assert_called_once()

    @pytest.mark.asyncio
    async def test_double_click(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("double_click", {
                "coordinate": [300, 400]
            })
        mock_pyautogui.doubleClick.assert_called_once()

    @pytest.mark.asyncio
    async def test_triple_click(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("triple_click", {
                "coordinate": [300, 400]
            })
        mock_pyautogui.tripleClick.assert_called_once()

    @pytest.mark.asyncio
    async def test_middle_click(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("middle_click", {
                "coordinate": [300, 400]
            })
        mock_pyautogui.middleClick.assert_called_once()

    @pytest.mark.asyncio
    async def test_mouse_move(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("mouse_move", {
                "coordinate": [500, 500]
            })
        mock_pyautogui.moveTo.assert_called()

    @pytest.mark.asyncio
    async def test_type_action(self, executor, mock_pyautogui):
        mock_clip = MagicMock()
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)), \
             patch.dict('sys.modules', {'pyperclip': mock_clip}):
            await executor.execute_action("type", {"text": "hello world"})
        mock_clip.copy.assert_called_once_with("hello world")
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "v")

    @pytest.mark.asyncio
    async def test_key_single(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("key", {"text": "enter"})
        mock_pyautogui.press.assert_called_once_with("enter")

    @pytest.mark.asyncio
    async def test_key_combo(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("key", {"text": "ctrl+c"})
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")

    @pytest.mark.asyncio
    async def test_scroll_down(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("scroll", {
                "coordinate": [500, 500],
                "scroll_direction": "down",
                "scroll_amount": 5,
            })
        mock_pyautogui.moveTo.assert_called()
        mock_pyautogui.scroll.assert_called_once_with(-5)

    @pytest.mark.asyncio
    async def test_scroll_up(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("scroll", {
                "coordinate": [500, 500],
                "scroll_direction": "up",
                "scroll_amount": 3,
            })
        mock_pyautogui.scroll.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_screenshot_action(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            result = await executor.execute_action("screenshot", {})
        assert result[0]["type"] == "image"

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            result = await executor.execute_action("nonexistent_action", {})
        assert result[0]["type"] == "text"
        assert "Error" in result[0]["text"] or "error" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_failsafe_returns_emergency(self, executor):
        with patch('computer_use.pyautogui') as mock_pag:
            mock_pag.FailSafeException = type('FailSafeException', (Exception,), {})
            mock_pag.click.side_effect = mock_pag.FailSafeException()
            result = await executor.execute_action("left_click", {
                "coordinate": [0, 0]
            })
        assert "EMERGENCY" in result[0]["text"] or "FailSafe" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_unchanged_screenshot_appends_text(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", False)):
            result = await executor.execute_action("screenshot", {})
        assert len(result) == 2
        assert "[screenshot unchanged]" in result[1]["text"]

    @pytest.mark.asyncio
    async def test_left_click_with_modifier(self, executor, mock_pyautogui):
        with patch.object(executor, 'take_screenshot_smart',
                          new_callable=AsyncMock,
                          return_value=("b64data", "image/png", True)):
            await executor.execute_action("left_click", {
                "coordinate": [100, 200],
                "text": "shift",
            })
        mock_pyautogui.keyDown.assert_called_once_with("shift")
        mock_pyautogui.click.assert_called_once()
        mock_pyautogui.keyUp.assert_called_once_with("shift")


# ===========================================================================
# Release all / utility tests
# ===========================================================================


class TestUtilities:
    """Tests for release_all, get_tool_definition, get_display_info, etc."""

    def test_release_all(self, executor, mock_pyautogui):
        executor.release_all()
        mock_pyautogui.mouseUp.assert_called_once()
        # Should attempt keyUp for shift, ctrl, alt, win
        assert mock_pyautogui.keyUp.call_count == 4

    def test_get_tool_definition(self, executor):
        td = executor.get_tool_definition()
        assert td["type"] == "computer_20250124"
        assert td["name"] == "computer"
        assert td["display_width_px"] == executor.scaled_width
        assert td["display_height_px"] == executor.scaled_height

    def test_get_display_info(self, executor):
        info = executor.get_display_info()
        assert info["screen_width"] == 1920
        assert info["screen_height"] == 1080
        assert info["scaled_width"] == executor.scaled_width
        assert info["scaled_height"] == executor.scaled_height
        assert "scale_factor" in info
        assert info["monitor_index"] == 1
        assert info["monitor_count"] == 1  # only 1 real monitor
        assert "monitor_offset" in info

    def test_get_available_monitors(self):
        monitors = [
            {"width": 3840, "height": 2160, "left": 0, "top": 0},
            {"width": 1920, "height": 1080, "left": 0, "top": 0},
            {"width": 2560, "height": 1440, "left": 1920, "top": 0},
        ]
        sct = _make_mock_sct(monitors)
        with _patch_mss(sct):
            from computer_use import ComputerUseExecutor
            result = ComputerUseExecutor.get_available_monitors()
        assert len(result) == 2  # excludes virtual monitor [0]
        assert result[0]["index"] == 1
        assert result[0]["primary"] is True
        assert result[1]["index"] == 2
        assert result[1]["primary"] is False

    def test_reset_screenshot_cache(self, executor):
        executor._last_screenshot_hash = "fakehash"
        executor._last_screenshot_b64 = "fakedata"
        executor._last_screenshot_media_type = "image/jpeg"
        executor._consecutive_unchanged = 3

        executor.reset_screenshot_cache()

        assert executor._last_screenshot_hash is None
        assert executor._last_screenshot_b64 is None
        assert executor._last_screenshot_media_type == "image/png"
        assert executor._consecutive_unchanged == 0

    def test_recalculate_for_resolution(self):
        monitors = [
            {"width": 3840, "height": 2160, "left": 0, "top": 0},
            {"width": 1920, "height": 1080, "left": 0, "top": 0},
            {"width": 2560, "height": 1440, "left": 1920, "top": 0},
        ]
        sct = _make_mock_sct(monitors)
        with _patch_mss(sct):
            from computer_use import ComputerUseExecutor
            exe = ComputerUseExecutor(monitor_index=1)
            assert exe.screen_width == 1920

            # Switch to monitor 2
            exe.recalculate_for_resolution(2)
            assert exe.monitor_index == 2
            assert exe.screen_width == 2560
            assert exe.screen_height == 1440
            assert exe.monitor_left == 1920
            # Cache should be reset
            assert exe._last_screenshot_hash is None


# ===========================================================================
# Text Editor tests
# ===========================================================================


class TestTextEditor:
    """Tests for handle_text_editor (view, create, str_replace, insert)."""

    @pytest.mark.asyncio
    async def test_view_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": str(f)},
            cwd=str(tmp_path),
        )
        assert len(result) == 1
        text = result[0]["text"]
        assert "line1" in text
        assert "line2" in text
        assert "line3" in text

    @pytest.mark.asyncio
    async def test_view_with_range(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": str(f), "view_range": [2, 4]},
            cwd=str(tmp_path),
        )
        text = result[0]["text"]
        assert "b" in text
        assert "c" in text
        assert "d" in text

    @pytest.mark.asyncio
    async def test_view_nonexistent_file(self, tmp_path):
        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": str(tmp_path / "nope.txt")},
            cwd=str(tmp_path),
        )
        assert "not found" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_create_file(self, tmp_path):
        target = tmp_path / "new_file.txt"
        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "create", "path": str(target), "file_text": "hello\nworld"},
            cwd=str(tmp_path),
        )
        assert "created" in result[0]["text"].lower()
        assert target.read_text(encoding="utf-8") == "hello\nworld"

    @pytest.mark.asyncio
    async def test_create_already_exists(self, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("existing content", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "create", "path": str(f), "file_text": "overwrite"},
            cwd=str(tmp_path),
        )
        assert "already exists" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_str_replace(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("hello world\n", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "str_replace", "path": str(f),
             "old_str": "hello", "new_str": "goodbye"},
            cwd=str(tmp_path),
        )
        assert "applied" in result[0]["text"].lower() or "edit" in result[0]["text"].lower()
        assert "goodbye world" in f.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_str_replace_not_found(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("hello world\n", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "str_replace", "path": str(f),
             "old_str": "nonexistent", "new_str": "replacement"},
            cwd=str(tmp_path),
        )
        assert "not found" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_str_replace_multiple_matches(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("foo bar foo baz\n", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "str_replace", "path": str(f),
             "old_str": "foo", "new_str": "qux"},
            cwd=str(tmp_path),
        )
        assert "2 times" in result[0]["text"] or "found" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_insert_at_line(self, tmp_path):
        f = tmp_path / "insert.txt"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "insert", "path": str(f),
             "insert_line": 2, "new_str": "inserted"},
            cwd=str(tmp_path),
        )
        assert "inserted" in result[0]["text"].lower()
        content = f.read_text(encoding="utf-8")
        lines = content.split("\n")
        assert "inserted" in lines

    @pytest.mark.asyncio
    async def test_missing_path(self, tmp_path):
        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": ""},
            cwd=str(tmp_path),
        )
        assert "required" in result[0]["text"].lower() or "path" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_unknown_command(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("x", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "delete_all", "path": str(f)},
            cwd=str(tmp_path),
        )
        assert "unknown" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_relative_path_resolved(self, tmp_path):
        f = tmp_path / "relative.txt"
        f.write_text("content", encoding="utf-8")

        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": "relative.txt"},
            cwd=str(tmp_path),
        )
        assert "content" in result[0]["text"]


# ===========================================================================
# Security blocking tests
# ===========================================================================


class TestSecurityBlocking:
    """Tests for blocked directory access in handle_text_editor."""

    @pytest.mark.asyncio
    async def test_block_ssh_dir(self, tmp_path):
        home = os.path.expanduser("~")
        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": os.path.join(home, ".ssh", "id_rsa")},
            cwd=str(tmp_path),
        )
        assert "denied" in result[0]["text"].lower() or "access" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_block_aws_dir(self, tmp_path):
        home = os.path.expanduser("~")
        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": os.path.join(home, ".aws", "credentials")},
            cwd=str(tmp_path),
        )
        assert "denied" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_block_gnupg_dir(self, tmp_path):
        home = os.path.expanduser("~")
        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": os.path.join(home, ".gnupg", "key")},
            cwd=str(tmp_path),
        )
        assert "denied" in result[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_block_rain_assistant_dir(self, tmp_path):
        home = os.path.expanduser("~")
        from computer_use import handle_text_editor
        result = await handle_text_editor(
            {"command": "view", "path": os.path.join(home, ".rain-assistant", "config.json")},
            cwd=str(tmp_path),
        )
        assert "denied" in result[0]["text"].lower()


# ===========================================================================
# describe_action tests
# ===========================================================================


class TestDescribeAction:
    """Tests for the describe_action function."""

    def test_screenshot(self):
        from computer_use import describe_action
        assert describe_action("computer", {"action": "screenshot"}) == "Capturar pantalla"

    def test_left_click(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "left_click", "coordinate": [100, 200]})
        assert "Left Click" in result
        assert "(100, 200)" in result

    def test_right_click(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "right_click", "coordinate": [50, 50]})
        assert "Right Click" in result

    def test_double_click(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "double_click", "coordinate": [10, 20]})
        assert "Double Click" in result

    def test_triple_click(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "triple_click", "coordinate": [10, 20]})
        assert "Triple click" in result

    def test_type_action(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "type", "text": "hello"})
        assert "Escribir" in result
        assert "hello" in result

    def test_key_action(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "key", "text": "ctrl+c"})
        assert "Tecla" in result
        assert "ctrl+c" in result

    def test_scroll(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "scroll", "scroll_direction": "down"})
        assert "Scroll" in result
        assert "down" in result

    def test_mouse_move(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "mouse_move", "coordinate": [300, 400]})
        assert "Mover" in result

    def test_left_click_drag(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "left_click_drag", "coordinate": [500, 600]})
        assert "Arrastrar" in result

    def test_wait(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "wait", "duration": 2})
        assert "Esperar" in result
        assert "2" in result

    def test_hold_key(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "hold_key", "text": "shift"})
        assert "Mantener" in result

    def test_unknown_action(self):
        from computer_use import describe_action
        result = describe_action("computer", {"action": "unknown_thing"})
        assert "Accion" in result

    def test_bash_tool(self):
        from computer_use import describe_action
        result = describe_action("bash", {"command": "ls -la"})
        assert "Ejecutar" in result
        assert "ls -la" in result

    def test_text_editor_tool(self):
        from computer_use import describe_action
        result = describe_action("str_replace_based_edit_tool", {"path": "/tmp/test.py"})
        assert "Editar" in result

    def test_generic_tool(self):
        from computer_use import describe_action
        result = describe_action("some_other_tool", {})
        assert "Tool: some_other_tool" in result
