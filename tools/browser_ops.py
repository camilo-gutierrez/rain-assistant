"""
Browser tool operations using Playwright.

Provides the AI agent with web browsing capabilities as a lightweight tool,
without requiring full computer_use mode.

Uses a BrowserPool to manage per-agent pages (tabs) in a shared browser
instance, so multiple agents can browse concurrently without interference.
"""

import asyncio
import base64
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── BrowserPool ──────────────────────────────────────────────

MAX_PAGES = 5  # Maximum concurrent agent pages


class BrowserPool:
    """Manages per-agent browser pages in a shared Playwright browser.

    Each agent_id gets its own page (tab).  The browser is lazy-launched on
    first request and automatically cleaned up when the last page is released.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self, max_pages: int = MAX_PAGES):
        self._max_pages = max_pages
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        # agent_id -> Page
        self._pages: dict[str, Any] = {}

    async def acquire(self, agent_id: str = "default"):
        """Get or create a page for *agent_id*.  Returns a Playwright Page.

        Raises RuntimeError if Playwright is not installed or the max page
        limit has been reached.
        """
        async with self._lock:
            # Return existing live page
            page = self._pages.get(agent_id)
            if page is not None and not page.is_closed():
                return page

            # Clean up stale entry if page was closed externally
            self._pages.pop(agent_id, None)

            # Enforce limit
            if len(self._pages) >= self._max_pages:
                raise RuntimeError(
                    f"Browser page limit reached ({self._max_pages}). "
                    "Close an existing browser session before opening a new one."
                )

            # Lazy-start Playwright + browser
            await self._ensure_browser()

            page = await self._browser.new_page()
            page.set_default_timeout(30000)
            self._pages[agent_id] = page
            logger.info("BrowserPool: created page for agent %s (%d/%d)",
                        agent_id, len(self._pages), self._max_pages)
            return page

    async def release(self, agent_id: str = "default"):
        """Close and remove the page for *agent_id*.

        If no pages remain, the browser and Playwright are shut down to free
        resources.
        """
        async with self._lock:
            page = self._pages.pop(agent_id, None)
            if page is not None and not page.is_closed():
                try:
                    await page.close()
                except Exception:
                    pass
            logger.info("BrowserPool: released page for agent %s (%d remaining)",
                        agent_id, len(self._pages))

            # Auto-cleanup when no pages remain
            if not self._pages:
                await self._shutdown_browser()

    async def release_all(self):
        """Close every page and shut down the browser."""
        async with self._lock:
            for aid, page in list(self._pages.items()):
                if page and not page.is_closed():
                    try:
                        await page.close()
                    except Exception:
                        pass
            self._pages.clear()
            await self._shutdown_browser()
            logger.info("BrowserPool: released all pages and shut down")

    # ── internal helpers (must be called while holding _lock) ─

    async def _ensure_browser(self):
        """Start Playwright and launch the browser if needed."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. "
                "Install with: pip install rain-assistant[browser]"
            )

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

    async def _shutdown_browser(self):
        """Close browser and Playwright (call while holding _lock)."""
        if self._browser is not None and self._browser.is_connected():
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None


# Module-level singleton pool
_pool = BrowserPool()


def get_pool() -> BrowserPool:
    """Return the module-level BrowserPool singleton."""
    return _pool


# ── Security ──────────────────────────────────────────────────

BLOCKED_URL_PATTERNS = [
    "chrome://", "file://", "javascript:",
    "data:text/html",
]

BLOCKED_DOMAINS = [
    "localhost", "127.0.0.1", "0.0.0.0",
    "169.254.",  # link-local
]


def _is_url_blocked(url: str) -> str | None:
    """Return a reason string if the URL is blocked, else None."""
    url_lower = url.lower().strip()

    for pattern in BLOCKED_URL_PATTERNS:
        if url_lower.startswith(pattern):
            return f"Blocked URL scheme: {pattern}"

    try:
        from urllib.parse import urlparse
        parsed = urlparse(url_lower)
        host = parsed.hostname or ""
        for blocked in BLOCKED_DOMAINS:
            if host == blocked or host.startswith(blocked):
                return f"Blocked domain: {host}"
    except Exception:
        pass

    return None


# ── Helpers ───────────────────────────────────────────────────

def _agent_id_from(args: dict) -> str:
    """Extract agent_id from args, defaulting to 'default'.

    The executor injects '_agent_id' into the args dict before calling
    browser handlers.  The LLM never sees or supplies this field.
    """
    return args.get("_agent_id", "default")


# ── Tool handlers ─────────────────────────────────────────────
# All handlers follow the signature: (args: dict, cwd: str) -> dict
# The executor injects '_agent_id' into args for browser tools.

async def browser_navigate(args: dict, cwd: str) -> dict:
    """Navigate to a URL and return the page title."""
    url = args.get("url", "").strip()
    if not url:
        return {"content": "Error: 'url' parameter is required.", "is_error": True}

    # Add https:// if no scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    blocked = _is_url_blocked(url)
    if blocked:
        return {"content": f"Error: {blocked}", "is_error": True}

    agent_id = _agent_id_from(args)
    try:
        page = await _pool.acquire(agent_id)
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status = response.status if response else "unknown"
        title = await page.title()
        current_url = page.url
        return {
            "content": (
                f"Navigated to: {current_url}\n"
                f"Title: {title}\n"
                f"Status: {status}"
            ),
            "is_error": False,
        }
    except RuntimeError as e:
        # Pool limit or Playwright not installed
        return {"content": f"Browser error: {e}", "is_error": True}
    except Exception as e:
        return {"content": f"Navigation error: {e}", "is_error": True}


async def browser_screenshot(args: dict, cwd: str) -> dict:
    """Take a screenshot of the current page. Returns base64 PNG."""
    full_page = args.get("full_page", False)
    agent_id = _agent_id_from(args)

    try:
        page = await _pool.acquire(agent_id)
        screenshot_bytes = await page.screenshot(full_page=full_page, type="png")
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        title = await page.title()
        return {
            "content": (
                f"Screenshot taken of: {page.url} ({title})\n"
                f"[Image data: {len(screenshot_bytes)} bytes, base64-encoded]\n"
                f"data:image/png;base64,{b64[:100]}..."
            ),
            "is_error": False,
        }
    except RuntimeError as e:
        return {"content": f"Browser error: {e}", "is_error": True}
    except Exception as e:
        return {"content": f"Screenshot error: {e}", "is_error": True}


async def browser_click(args: dict, cwd: str) -> dict:
    """Click an element by CSS selector or text content."""
    selector = args.get("selector", "").strip()
    by_text = args.get("by_text", False)

    if not selector:
        return {"content": "Error: 'selector' parameter is required.", "is_error": True}

    agent_id = _agent_id_from(args)
    try:
        page = await _pool.acquire(agent_id)
        if by_text:
            element = page.get_by_text(selector, exact=False)
            await element.first.click(timeout=10000)
        else:
            await page.click(selector, timeout=10000)

        await page.wait_for_load_state("domcontentloaded", timeout=5000)
        title = await page.title()
        return {
            "content": f"Clicked: {selector}\nCurrent page: {page.url} ({title})",
            "is_error": False,
        }
    except RuntimeError as e:
        return {"content": f"Browser error: {e}", "is_error": True}
    except Exception as e:
        return {"content": f"Click error: {e}", "is_error": True}


async def browser_type(args: dict, cwd: str) -> dict:
    """Type text into a form field identified by CSS selector."""
    selector = args.get("selector", "").strip()
    text = args.get("text", "")
    clear_first = args.get("clear_first", True)

    if not selector:
        return {"content": "Error: 'selector' parameter is required.", "is_error": True}

    agent_id = _agent_id_from(args)
    try:
        page = await _pool.acquire(agent_id)
        if clear_first:
            await page.fill(selector, text, timeout=10000)
        else:
            await page.type(selector, text, timeout=10000)
        return {
            "content": f"Typed into '{selector}': {text[:100]}{'...' if len(text) > 100 else ''}",
            "is_error": False,
        }
    except RuntimeError as e:
        return {"content": f"Browser error: {e}", "is_error": True}
    except Exception as e:
        return {"content": f"Type error: {e}", "is_error": True}


async def browser_extract_text(args: dict, cwd: str) -> dict:
    """Extract text content from the page or a specific element."""
    selector = args.get("selector", "").strip()
    max_length = args.get("max_length", 10000)
    agent_id = _agent_id_from(args)

    try:
        page = await _pool.acquire(agent_id)
        if selector:
            element = await page.query_selector(selector)
            if not element:
                return {"content": f"Element not found: {selector}", "is_error": True}
            text = await element.inner_text()
        else:
            text = await page.inner_text("body")

        text = text.strip()
        if len(text) > max_length:
            text = text[:max_length] + f"\n\n[...truncated, {len(text)} total chars]"

        title = await page.title()
        return {
            "content": f"Page: {page.url} ({title})\n\n{text}",
            "is_error": False,
        }
    except RuntimeError as e:
        return {"content": f"Browser error: {e}", "is_error": True}
    except Exception as e:
        return {"content": f"Extract error: {e}", "is_error": True}


async def browser_scroll(args: dict, cwd: str) -> dict:
    """Scroll the page up or down by a given amount."""
    direction = args.get("direction", "down")
    amount = args.get("amount", 500)
    agent_id = _agent_id_from(args)

    try:
        page = await _pool.acquire(agent_id)
        delta = amount if direction == "down" else -amount
        await page.evaluate(f"window.scrollBy(0, {delta})")
        scroll_y = await page.evaluate("window.scrollY")
        scroll_height = await page.evaluate("document.documentElement.scrollHeight")
        return {
            "content": (
                f"Scrolled {direction} by {amount}px. "
                f"Position: {int(scroll_y)}/{int(scroll_height)}px"
            ),
            "is_error": False,
        }
    except RuntimeError as e:
        return {"content": f"Browser error: {e}", "is_error": True}
    except Exception as e:
        return {"content": f"Scroll error: {e}", "is_error": True}


async def browser_close(args: dict, cwd: str) -> dict:
    """Close the browser page for this agent, freeing resources."""
    agent_id = _agent_id_from(args)
    try:
        await _pool.release(agent_id)
        return {"content": "Browser closed.", "is_error": False}
    except Exception as e:
        return {"content": f"Close error: {e}", "is_error": True}
