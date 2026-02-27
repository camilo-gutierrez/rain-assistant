"""
computer_use_recorder.py — Recording & Replay for Computer Use

Phase 8: Records computer use sessions (actions, screenshots, text).
Supports export to JSON, Python script, and HTML timeline.
Supports replay of recorded sessions.
"""

import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("rain.computer_use.recorder")

# ── Storage path ─────────────────────────────────────────────────────────
RECORDINGS_DIR = Path.home() / ".rain-assistant" / "recordings"


@dataclass
class RecordedEvent:
    """A single recorded event in a computer use session."""
    timestamp: float
    event_type: str  # "action", "screenshot", "text"
    data: dict = field(default_factory=dict)


class SessionRecorder:
    """Records computer use sessions for later replay or export.

    Records actions, screenshots (as base64), and text events
    with timestamps relative to session start.
    """

    def __init__(self, session_id: str, screen_width: int, screen_height: int):
        self.session_id = session_id
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._events: list[RecordedEvent] = []
        self._start_time = time.time()
        self._recording = True

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Session recorder started: %s", session_id)

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def duration(self) -> float:
        if not self._events:
            return 0.0
        return self._events[-1].timestamp - self._start_time

    def record_action(self, action: str, params: dict) -> None:
        """Record a computer use action."""
        if not self._recording:
            return
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type="action",
            data={"action": action, "params": params},
        ))

    def record_screenshot(self, b64_data: str, media_type: str = "image/png") -> None:
        """Record a screenshot (stores base64 data)."""
        if not self._recording:
            return
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type="screenshot",
            data={"base64": b64_data, "media_type": media_type},
        ))

    def record_text(self, role: str, text: str) -> None:
        """Record a text message (user or assistant)."""
        if not self._recording:
            return
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type="text",
            data={"role": role, "text": text[:5000]},
        ))

    def stop(self) -> None:
        """Stop recording."""
        self._recording = False
        logger.info(
            "Session recorder stopped: %s (%d events, %.1fs)",
            self.session_id, len(self._events), self.duration,
        )

    # ── Export methods ────────────────────────────────────────────────

    def save_json(self, path: Optional[str] = None) -> str:
        """Save session as JSON. Returns the file path."""
        if path is None:
            path = str(RECORDINGS_DIR / f"{self.session_id}.json")

        data = {
            "session_id": self.session_id,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "start_time": self._start_time,
            "duration": self.duration,
            "event_count": len(self._events),
            "events": [
                {
                    "timestamp": e.timestamp,
                    "relative_time": round(e.timestamp - self._start_time, 3),
                    "type": e.event_type,
                    "data": e.data if e.event_type != "screenshot"
                            else {"media_type": e.data.get("media_type", "image/png"),
                                  "base64_length": len(e.data.get("base64", ""))},
                }
                for e in self._events
            ],
        }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("Session saved to %s", path)
        return path

    def export_script(self, output_path: Optional[str] = None) -> str:
        """Export as a Python pyautogui script for replay.

        Returns the file path. Only exports action events.
        """
        if output_path is None:
            output_path = str(RECORDINGS_DIR / f"{self.session_id}_replay.py")

        lines = [
            '"""Auto-generated replay script from Rain Computer Use session."""',
            "import time",
            "import pyautogui",
            "",
            "pyautogui.FAILSAFE = True",
            "pyautogui.PAUSE = 0.1",
            f"# Session: {self.session_id}",
            f"# Screen: {self.screen_width}x{self.screen_height}",
            f"# Duration: {self.duration:.1f}s",
            "",
            'print("Starting replay in 3 seconds...")',
            "time.sleep(3)",
            "",
        ]

        prev_time = self._start_time
        for event in self._events:
            if event.event_type != "action":
                continue

            # Add delay between actions
            delay = event.timestamp - prev_time
            if delay > 0.2:
                lines.append(f"time.sleep({delay:.2f})")

            action = event.data.get("action", "")
            params = event.data.get("params", {})

            line = _action_to_pyautogui(action, params)
            if line:
                lines.append(line)

            prev_time = event.timestamp

        lines.append("")
        lines.append('print("Replay complete.")')

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("Replay script exported to %s", output_path)
        return output_path

    def export_html(self, output_path: Optional[str] = None) -> str:
        """Export as a standalone HTML file with embedded screenshots and timeline.

        Returns the file path.
        """
        if output_path is None:
            output_path = str(RECORDINGS_DIR / f"{self.session_id}.html")

        timeline_items = []
        for event in self._events:
            rel_time = round(event.timestamp - self._start_time, 2)

            if event.event_type == "screenshot":
                b64 = event.data.get("base64", "")
                mt = event.data.get("media_type", "image/png")
                timeline_items.append(
                    f'<div class="event screenshot">'
                    f'<span class="time">{rel_time}s</span>'
                    f'<img src="data:{mt};base64,{b64}" />'
                    f'</div>'
                )
            elif event.event_type == "action":
                action = event.data.get("action", "")
                params_str = json.dumps(event.data.get("params", {}), default=str)
                timeline_items.append(
                    f'<div class="event action">'
                    f'<span class="time">{rel_time}s</span>'
                    f'<strong>{action}</strong> <code>{_escape_html(params_str)}</code>'
                    f'</div>'
                )
            elif event.event_type == "text":
                role = event.data.get("role", "")
                text = _escape_html(event.data.get("text", ""))
                timeline_items.append(
                    f'<div class="event text {role}">'
                    f'<span class="time">{rel_time}s</span>'
                    f'<em>{role}:</em> {text}'
                    f'</div>'
                )

        html = _HTML_TEMPLATE.format(
            session_id=self.session_id,
            screen_info=f"{self.screen_width}x{self.screen_height}",
            duration=f"{self.duration:.1f}",
            event_count=len(self._events),
            timeline="\n".join(timeline_items),
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("HTML timeline exported to %s", output_path)
        return output_path


# ── Session Replayer ─────────────────────────────────────────────────────

class SessionReplayer:
    """Loads and replays a recorded session without Claude.

    Replays only action events using pyautogui with original timing.
    """

    def __init__(self, session_path: str):
        with open(session_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        self.session_id = self._data.get("session_id", "unknown")
        self.events = self._data.get("events", [])
        logger.info(
            "Loaded session %s: %d events", self.session_id, len(self.events),
        )

    async def replay(self, speed: float = 1.0) -> int:
        """Replay action events with timing.

        Args:
            speed: Playback speed multiplier (1.0 = original, 2.0 = 2x fast).

        Returns:
            Number of actions replayed.
        """
        import asyncio

        actions = [e for e in self.events if e.get("type") == "action"]
        if not actions:
            return 0

        count = 0
        prev_time = actions[0].get("relative_time", 0)

        for event in actions:
            rel = event.get("relative_time", 0)
            delay = (rel - prev_time) / speed
            if delay > 0.1:
                await asyncio.sleep(delay)

            data = event.get("data", {})
            action = data.get("action", "")
            params = data.get("params", {})

            line = _action_to_pyautogui(action, params)
            if line:
                try:
                    exec(line)  # noqa: S102
                    count += 1
                except Exception as e:
                    logger.error("Replay action failed: %s - %s", action, e)

            prev_time = rel

        return count


# ── Helpers ──────────────────────────────────────────────────────────────

def _action_to_pyautogui(action: str, params: dict) -> Optional[str]:
    """Convert a recorded action to a pyautogui Python statement."""
    coord = params.get("coordinate")

    if action == "left_click" and coord:
        return f"pyautogui.click({coord[0]}, {coord[1]})"
    elif action == "right_click" and coord:
        return f"pyautogui.rightClick({coord[0]}, {coord[1]})"
    elif action == "double_click" and coord:
        return f"pyautogui.doubleClick({coord[0]}, {coord[1]})"
    elif action == "triple_click" and coord:
        return f"pyautogui.tripleClick({coord[0]}, {coord[1]})"
    elif action == "mouse_move" and coord:
        return f"pyautogui.moveTo({coord[0]}, {coord[1]})"
    elif action == "type":
        text = params.get("text", "").replace("'", "\\'")
        return f"pyautogui.write('{text}')"
    elif action == "key":
        keys = params.get("text", "")
        if "+" in keys:
            parts = ", ".join(f"'{k.strip()}'" for k in keys.split("+"))
            return f"pyautogui.hotkey({parts})"
        return f"pyautogui.press('{keys}')"
    elif action == "scroll":
        direction = params.get("scroll_direction", "down")
        amount = params.get("scroll_amount", 3)
        sign = -1 if direction == "down" else 1
        return f"pyautogui.scroll({sign * amount})"
    elif action == "wait":
        duration = min(params.get("duration", 1.0), 10.0)
        return f"time.sleep({duration})"

    return None


def _escape_html(text: str) -> str:
    """Basic HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ── HTML Template ────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Rain Session: {session_id}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #1a1a2e; color: #e0e0e0; }}
h1 {{ color: #7c3aed; }}
.meta {{ color: #888; margin-bottom: 2rem; }}
.event {{ padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 8px; border-left: 3px solid #333; }}
.event.screenshot {{ border-color: #7c3aed; }}
.event.screenshot img {{ max-width: 100%; border-radius: 4px; margin-top: 0.5rem; }}
.event.action {{ border-color: #f59e0b; background: rgba(245,158,11,0.05); }}
.event.text {{ border-color: #10b981; background: rgba(16,185,129,0.05); }}
.event.text.user {{ border-color: #3b82f6; }}
.time {{ color: #888; font-size: 0.85em; margin-right: 0.5rem; }}
code {{ background: rgba(255,255,255,0.1); padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>Rain Computer Use Session</h1>
<div class="meta">
    Session: {session_id} |
    Screen: {screen_info} |
    Duration: {duration}s |
    Events: {event_count}
</div>
<div class="timeline">
{timeline}
</div>
</body>
</html>"""
