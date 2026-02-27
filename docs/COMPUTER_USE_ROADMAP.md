# Computer Use System — Next Level Roadmap

## Current State (v1)

**Pipeline:** `User Request → Claude Sonnet → pyautogui/mss → Screenshot → Loop`

| Component | Implementation | Limitations |
|-----------|---------------|-------------|
| Model | claude-sonnet-4-6 + computer-use-2025-01-24 beta | Fixed model |
| Actions | click, type, scroll, key, drag, wait, bash | text_editor not implemented |
| Screenshots | mss capture → PIL resize → base64 PNG | Every action triggers screenshot |
| Scaling | Auto-scale to API limits (1568px max edge) | Coordinate precision on HiDPI |
| Permissions | YELLOW for all actions, GREEN for screenshots | No granular per-action levels |
| Loop | Max 50 iterations, 10 min timeout | No continuation/resume |
| UI | ScreenshotViewer, ActionBubble, EmergencyStop | No click-on-screenshot interaction |

---

## Phase 1: Text Editor Tool (HIGH PRIORITY) ✅ IMPLEMENTED

**Goal:** Implement the `str_replace_based_edit_tool` that Claude expects.

### Changes to `server.py` (_computer_use_loop):
- [x] Handle `str_replace_based_edit_tool` tool calls
- [x] Support `view`, `create`, `str_replace`, `insert` commands
- [x] File path validation (block sensitive dirs)
- [x] Return file content after edit for Claude to verify

### Implementation:
```python
async def _handle_text_editor(tool_input: dict, cwd: str) -> list:
    command = tool_input.get("command")
    path = tool_input.get("path")

    if command == "view":
        # Read file, return content with line numbers
    elif command == "create":
        # Create new file with content
    elif command == "str_replace":
        # Find old_str, replace with new_str
    elif command == "insert":
        # Insert text at line number
```

---

## Phase 2: Loop Continuation & Resume (HIGH PRIORITY) ✅ IMPLEMENTED

**Goal:** Don't lose progress when hitting the 50-iteration limit.

### Changes to `server.py`:
- [x] When iteration limit reached, ask user "Continue?" via WebSocket
- [x] If user confirms, resume loop with preserved message history
- [x] Configurable max iterations per session (default 50, max 200)
- [x] Session persistence: save conversation state for resume after disconnect

### WebSocket Messages:
```python
# Server → Frontend
{"type": "computer_use_paused", "reason": "iteration_limit", "iterations": 50}

# Frontend → Server
{"type": "computer_use_continue", "max_iterations": 50}  # Add 50 more
```

---

## Phase 3: Smart Screenshot Optimization (MEDIUM PRIORITY) ✅ IMPLEMENTED

**Goal:** Reduce latency and API costs by skipping redundant screenshots.

### Changes to `computer_use.py`:
- [ ] Screenshot diff detection: compare current vs previous (perceptual hash)
- [ ] Skip screenshot if screen unchanged (e.g., after `wait`, failed click)
- [ ] Batch sequential mouse moves without intermediate screenshots
- [ ] Compress screenshots more aggressively (JPEG for large images, quality 85)
- [ ] Only send full-page screenshots when content changes significantly

### Implementation:
```python
def _screenshots_differ(self, img1_bytes: bytes, img2_bytes: bytes) -> bool:
    """Compare screenshots using perceptual hashing."""
    hash1 = imagehash.phash(Image.open(BytesIO(img1_bytes)))
    hash2 = imagehash.phash(Image.open(BytesIO(img2_bytes)))
    return (hash1 - hash2) > SIMILARITY_THRESHOLD  # e.g., 5
```

---

## Phase 4: Enhanced Safety & Sandboxing (MEDIUM PRIORITY) ✅ IMPLEMENTED

**Goal:** Stronger isolation for computer use actions.

### Bash Sandboxing:
- [ ] Run bash commands in subprocess with resource limits (timeout, memory, CPU)
- [ ] Whitelist safe directories (user home, project dirs)
- [ ] Block access to system directories (Windows/System32, /etc, registry)
- [ ] Log all executed commands with timestamps for audit trail
- [ ] Per-session command history with undo capability

### Computer Action Safety:
- [ ] Detect and warn about sensitive areas (password fields, payment forms)
- [ ] Block interactions with system tray, task manager by default
- [ ] OCR-based detection of sensitive content on screen
- [ ] Rate limit actions (max 5 clicks/second)

---

## Phase 5: Interactive Screenshot (MEDIUM PRIORITY) ✅ IMPLEMENTED

**Goal:** Let users click on screenshots to provide coordinates to Claude.

### Frontend Changes (`ScreenshotViewer.tsx`):
- [ ] Click handler that captures (x, y) relative to image
- [ ] Scale coordinates back to screen space
- [ ] Send as user hint: "I'm pointing at coordinates (x, y)"
- [ ] Visual crosshair/indicator on hover
- [ ] Zoom capability for precise targeting

### Implementation:
```tsx
const handleScreenshotClick = (e: React.MouseEvent<HTMLImageElement>) => {
  const rect = e.currentTarget.getBoundingClientRect();
  const scaleX = displayInfo.screen_width / rect.width;
  const scaleY = displayInfo.screen_height / rect.height;
  const x = Math.round((e.clientX - rect.left) * scaleX);
  const y = Math.round((e.clientY - rect.top) * scaleY);
  // Send as hint to Claude
  sendMessage({ type: "computer_use_hint", x, y, description: "User pointed here" });
};
```

---

## Phase 6: Vision Enhancement (LOW PRIORITY) ✅ IMPLEMENTED

**Goal:** Help Claude understand screen content better.

### OCR Integration:
- [ ] Optional OCR pass on screenshots (Tesseract or Windows OCR API)
- [ ] Extract visible text, include as context in tool result
- [ ] UI element detection: buttons, inputs, labels with bounding boxes
- [ ] Accessibility tree extraction (Windows UI Automation API)

### Implementation:
```python
# In computer_use.py
async def _enhance_screenshot(self, image: Image.Image) -> dict:
    """Extract text and UI elements from screenshot."""
    # OCR
    text = pytesseract.image_to_string(image)
    # UI elements (optional)
    elements = await self._get_ui_elements()
    return {
        "ocr_text": text[:2000],  # Truncate
        "elements": elements[:50],  # Top 50 elements
    }
```

---

## Phase 7: Multi-Monitor & Resolution (LOW PRIORITY) ✅ IMPLEMENTED

**Goal:** Support multi-monitor setups and dynamic resolution changes.

- [ ] Detect all monitors via `mss` (already supports it)
- [ ] Let user select which monitor to control
- [ ] Handle resolution changes mid-session (recalculate scale factor)
- [ ] Support different DPI scales per monitor
- [ ] Virtual desktop switching (Windows 10/11)

---

## Phase 8: Recording & Replay (LOW PRIORITY) ✅ IMPLEMENTED

**Goal:** Record computer use sessions for review and replay.

- [ ] Save all actions + screenshots as session log
- [ ] Export as video (ffmpeg: screenshots → mp4)
- [ ] Export as action script (reproducible automation)
- [ ] Replay mode: execute recorded actions without Claude
- [ ] Share sessions as interactive HTML reports

---

## Implementation Status

| Phase | Status | Priority | Effort |
|-------|--------|----------|--------|
| 1. Text Editor Tool | ✅ Done | High | ~2h |
| 2. Loop Continuation | ✅ Done | High | ~2h |
| 3. Smart Screenshots | ✅ Done | Medium | ~3h |
| 4. Enhanced Safety | ✅ Done | Medium | ~4h |
| 5. Interactive Screenshot | ✅ Done | Medium | ~3h |
| 6. Vision Enhancement | ✅ Done | Low | ~5h |
| 7. Multi-Monitor | ✅ Done | Low | ~3h |
| 8. Recording & Replay | ✅ Done | Low | ~6h |

---

## Files Modified

- `computer_use.py` — Text editor handler, smart screenshots, vision
- `server.py` — Loop continuation, text editor routing, session persistence
- `permission_classifier.py` — (Phase 4: granular action permissions)
- `frontend/src/components/computer-use/ScreenshotViewer.tsx` — (Phase 5: interactive clicks)
- `frontend/src/hooks/useComputerUseMessages.ts` — (Phase 2: continuation messages)
- `pyproject.toml` — New optional dependencies (imagehash, pytesseract)
- `tests/test_computer_use.py` — New test file for computer use features
