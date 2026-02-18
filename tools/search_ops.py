"""Search operations for the tool system."""

import fnmatch
import os
import re
from pathlib import Path

from .file_ops import resolve_path

MAX_RESULTS = 200
MAX_GREP_MATCHES = 100

# Directories to skip during search
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".venv", "venv",
    "dist", "build", ".cache", ".tox", "coverage", ".mypy_cache",
}


async def search_files(args: dict, cwd: str) -> dict:
    """Search for files matching a glob pattern."""
    pattern = args["pattern"]
    root = resolve_path(args.get("path", "."), cwd)

    if not root.exists() or not root.is_dir():
        return {"content": f"Error: Directory not found: {args.get('path', '.')}", "is_error": True}

    matches = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip common large directories
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            for filename in filenames:
                full = Path(dirpath) / filename
                rel = full.relative_to(root)
                if fnmatch.fnmatch(str(rel), pattern) or fnmatch.fnmatch(filename, pattern):
                    matches.append(str(rel))
                    if len(matches) >= MAX_RESULTS:
                        break
            if len(matches) >= MAX_RESULTS:
                break
    except Exception as e:
        return {"content": f"Error searching files: {e}", "is_error": True}

    if not matches:
        return {"content": f"No files matching '{pattern}'", "is_error": False}

    result = "\n".join(matches)
    if len(matches) >= MAX_RESULTS:
        result += f"\n\n... (truncated at {MAX_RESULTS} results)"
    return {"content": result, "is_error": False}


async def grep_search(args: dict, cwd: str) -> dict:
    """Search file contents for a regex pattern."""
    pattern = args["pattern"]
    root = resolve_path(args.get("path", "."), cwd)
    include = args.get("include")

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return {"content": f"Error: Invalid regex: {e}", "is_error": True}

    if not root.exists():
        return {"content": f"Error: Path not found: {args.get('path', '.')}", "is_error": True}

    matches = []

    def search_file(filepath: Path):
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    rel = filepath.relative_to(Path(cwd).resolve())
                    matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                    if len(matches) >= MAX_GREP_MATCHES:
                        return
        except (UnicodeDecodeError, PermissionError, OSError):
            pass

    try:
        if root.is_file():
            search_file(root)
        else:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for filename in filenames:
                    if include and not fnmatch.fnmatch(filename, include):
                        continue
                    filepath = Path(dirpath) / filename
                    search_file(filepath)
                    if len(matches) >= MAX_GREP_MATCHES:
                        break
                if len(matches) >= MAX_GREP_MATCHES:
                    break
    except Exception as e:
        return {"content": f"Error during grep: {e}", "is_error": True}

    if not matches:
        return {"content": f"No matches for '{pattern}'", "is_error": False}

    result = "\n".join(matches)
    if len(matches) >= MAX_GREP_MATCHES:
        result += f"\n\n... (truncated at {MAX_GREP_MATCHES} matches)"
    return {"content": result, "is_error": False}
