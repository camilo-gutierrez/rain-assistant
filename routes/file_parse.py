"""File parse endpoint — uploads a file and returns extracted text.

Used by the Flutter app to parse binary files (PDF, DOCX) into text
that can be stored in director context_window fields.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse

from shared_state import verify_token, get_token

_logger = logging.getLogger("rain.server")

file_parse_router = APIRouter(tags=["file_parse"])

MAX_PARSE_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
READ_CHUNK_SIZE = 64 * 1024  # 64 KB

_ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".csv", ".tsv", ".json",
    ".pdf", ".docx", ".html", ".htm",
}


@file_parse_router.post("/api/parse-file")
async def parse_file_upload(request: Request, file: UploadFile = File(...)):
    """Upload a file and get back its extracted text content.

    Supports: .txt, .md, .csv, .json, .pdf, .docx, .html
    For text files, returns content as-is.
    For PDF/DOCX, uses the Rain document parser to extract text.
    """
    if not verify_token(get_token(request)):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

    if ext not in _ALLOWED_EXTENSIONS:
        return JSONResponse(
            {
                "error": f"Unsupported file type: '{ext}'. "
                f"Supported: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            },
            status_code=400,
        )

    # Read file in chunks with size limit
    content = bytearray()
    while True:
        chunk = await file.read(READ_CHUNK_SIZE)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_PARSE_FILE_SIZE:
            return JSONResponse(
                {"error": f"File too large (max {MAX_PARSE_FILE_SIZE // (1024 * 1024)} MB)"},
                status_code=413,
            )

    if not content:
        return JSONResponse({"error": "Empty file"}, status_code=400)

    # For plain text files, decode directly
    if ext in {".txt", ".md", ".csv", ".tsv", ".json"}:
        try:
            text = bytes(content).decode("utf-8", errors="replace")
        except Exception as e:
            return JSONResponse(
                {"error": f"Failed to decode text file: {e}"},
                status_code=400,
            )
        return {
            "text": text,
            "filename": filename,
            "size": len(content),
            "chars": len(text),
        }

    # For binary files (PDF, DOCX, HTML), write to temp file and use parser
    try:
        from documents.parser import parse_file
    except ImportError:
        return JSONResponse(
            {"error": "Document parser not available. Install: pip install rain-assistant[documents]"},
            status_code=422,
        )

    tmp_path = None
    try:
        # Write to a temp file with the correct extension
        with tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, mode="wb"
        ) as tmp:
            tmp.write(bytes(content))
            tmp_path = tmp.name

        text = parse_file(tmp_path)

        _logger.info(
            "File parsed: name=%s ext=%s size=%d chars=%d",
            filename, ext, len(content), len(text),
        )

        return {
            "text": text,
            "filename": filename,
            "size": len(content),
            "chars": len(text),
        }
    except ImportError as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500,
        )
    except (ValueError, Exception) as e:
        _logger.warning("Failed to parse file %s: %s", filename, e)
        return JSONResponse(
            {"error": f"Failed to parse file: {e}"},
            status_code=400,
        )
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
