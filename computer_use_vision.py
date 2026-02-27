"""
computer_use_vision.py — Vision Enhancement for Computer Use

Phase 6: OCR text extraction, bounding box detection,
Windows UI Automation integration, and screenshot context enhancement.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PIL import Image

logger = logging.getLogger("rain.computer_use.vision")

# ── Feature flags (lazy-detected) ────────────────────────────────────────

_HAS_TESSERACT: Optional[bool] = None
_HAS_UIAUTOMATION: Optional[bool] = None

MAX_OCR_TEXT_LENGTH = 3000
MIN_OCR_CONFIDENCE = 40


def _check_tesseract() -> bool:
    global _HAS_TESSERACT
    if _HAS_TESSERACT is None:
        try:
            import pytesseract  # noqa: F401
            # Quick check that tesseract binary is available
            pytesseract.get_tesseract_version()
            _HAS_TESSERACT = True
            logger.info("Tesseract OCR available")
        except Exception:
            _HAS_TESSERACT = False
            logger.info("Tesseract OCR not available — vision text extraction disabled")
    return _HAS_TESSERACT


def _check_uiautomation() -> bool:
    global _HAS_UIAUTOMATION
    if _HAS_UIAUTOMATION is None:
        try:
            import comtypes  # noqa: F401
            import comtypes.client  # noqa: F401
            _HAS_UIAUTOMATION = True
            logger.info("Windows UI Automation available")
        except ImportError:
            _HAS_UIAUTOMATION = False
            logger.info("comtypes not installed — UI Automation disabled")
    return _HAS_UIAUTOMATION


# ── OCR Text Extraction ─────────────────────────────────────────────────

def extract_text_ocr(image: Image.Image, lang: str = "eng+spa") -> str:
    """Extract text from a screenshot using Tesseract OCR.

    Args:
        image: PIL Image to extract text from.
        lang: Tesseract language code(s), e.g. "eng", "eng+spa".

    Returns:
        Extracted text, truncated to MAX_OCR_TEXT_LENGTH chars.
        Empty string if Tesseract is not available or fails.
    """
    if not _check_tesseract():
        return ""

    try:
        import pytesseract
        text = pytesseract.image_to_string(image, lang=lang)
        text = text.strip()
        if len(text) > MAX_OCR_TEXT_LENGTH:
            text = text[:MAX_OCR_TEXT_LENGTH] + "..."
        return text
    except Exception as e:
        logger.error("OCR extraction failed: %s", e)
        return ""


def extract_text_with_boxes(image: Image.Image, lang: str = "eng+spa") -> list[dict]:
    """Extract text with bounding boxes from a screenshot.

    Returns a list of dicts with keys: text, x, y, w, h, confidence.
    Only includes entries with confidence > MIN_OCR_CONFIDENCE.
    """
    if not _check_tesseract():
        return []

    try:
        import pytesseract
        data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

        results = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            conf = int(data["conf"][i]) if data["conf"][i] != "-1" else 0

            if not text or conf < MIN_OCR_CONFIDENCE:
                continue

            results.append({
                "text": text,
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
                "confidence": conf,
            })

        return results
    except Exception as e:
        logger.error("OCR box extraction failed: %s", e)
        return []


# ── Windows UI Automation ────────────────────────────────────────────────

def get_ui_elements_windows() -> list[dict]:
    """Get visible UI elements using Windows UI Automation API.

    Returns a list of dicts with keys: name, type, x, y, w, h.
    Only returns elements that have a bounding rectangle.
    """
    if not _check_uiautomation():
        return []

    try:
        import comtypes.client

        # Load UI Automation COM interface
        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=None,
        )

        root = uia.GetRootElement()
        if root is None:
            return []

        # Get focused window's children
        condition = uia.CreateTrueCondition()
        walker = uia.CreateTreeWalker(condition)

        elements = []
        _walk_elements(walker, root, elements, max_depth=3, max_elements=50)
        return elements

    except Exception as e:
        logger.error("UI Automation failed: %s", e)
        return []


def _walk_elements(
    walker, element, results: list[dict],
    max_depth: int, max_elements: int, depth: int = 0,
) -> None:
    """Recursively walk UI automation tree to collect element info."""
    if depth >= max_depth or len(results) >= max_elements:
        return

    try:
        child = walker.GetFirstChildElement(element)
        while child is not None and len(results) < max_elements:
            try:
                name = child.CurrentName or ""
                control_type = child.CurrentLocalizedControlType or ""
                rect = child.CurrentBoundingRectangle

                if rect and (rect.right - rect.left) > 0:
                    results.append({
                        "name": name[:100],
                        "type": control_type,
                        "x": rect.left,
                        "y": rect.top,
                        "w": rect.right - rect.left,
                        "h": rect.bottom - rect.top,
                    })

                _walk_elements(walker, child, results, max_depth, max_elements, depth + 1)
            except Exception:
                pass

            try:
                child = walker.GetNextSiblingElement(child)
            except Exception:
                break
    except Exception:
        pass


# ── Screenshot Context Enhancement ──────────────────────────────────────

def enhance_screenshot_context(image: Image.Image) -> dict:
    """Run all available vision enhancements on a screenshot.

    Returns a dict with available context:
    - ocr_text: extracted text (if Tesseract available)
    - ui_elements: list of UI elements (if UI Automation available)
    - text_boxes: list of text regions with positions (if Tesseract available)
    """
    result: dict = {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {}

        if _check_tesseract():
            futures["ocr_text"] = pool.submit(extract_text_ocr, image)
            futures["text_boxes"] = pool.submit(extract_text_with_boxes, image)

        if _check_uiautomation():
            futures["ui_elements"] = pool.submit(get_ui_elements_windows)

        for key, future in futures.items():
            try:
                result[key] = future.result(timeout=10)
            except Exception as e:
                logger.error("Vision enhancement '%s' failed: %s", key, e)
                result[key] = [] if key != "ocr_text" else ""

    return result


def is_available() -> bool:
    """Check if any vision capability is available."""
    return _check_tesseract() or _check_uiautomation()
