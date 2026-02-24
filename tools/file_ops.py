"""File operations for the tool system."""

import os
from pathlib import Path

MAX_READ_LINES = 2000
MAX_LINE_LENGTH = 2000


def resolve_path(path_str: str, cwd: str) -> Path:
    """Resolve a path relative to the working directory. Raises ValueError on traversal."""
    p = Path(path_str)
    if not p.is_absolute():
        p = Path(cwd) / p
    try:
        resolved = p.resolve(strict=True)
    except OSError:
        # For new files that don't exist yet, resolve the parent
        try:
            parent_resolved = p.parent.resolve(strict=True)
        except OSError:
            raise ValueError(f"Path does not exist: {path_str}")
        resolved = parent_resolved / p.name
    cwd_resolved = Path(cwd).resolve()
    if not str(resolved).startswith(str(cwd_resolved) + os.sep) and resolved != cwd_resolved:
        raise ValueError(f"Path traversal blocked: {path_str}")
    return resolved


async def read_file(args: dict, cwd: str) -> dict:
    """Read a file with optional offset/limit. Returns content with line numbers."""
    path = resolve_path(args["path"], cwd)
    if not path.exists():
        return {"content": f"Error: File not found: {args['path']}", "is_error": True}
    if not path.is_file():
        return {"content": f"Error: Not a file: {args['path']}", "is_error": True}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"content": f"Error reading file: {e}", "is_error": True}

    lines = text.splitlines()
    offset = max(args.get("offset", 1), 1) - 1  # 1-based to 0-based
    limit = args.get("limit", MAX_READ_LINES)
    selected = lines[offset : offset + limit]

    numbered = []
    for i, line in enumerate(selected, start=offset + 1):
        truncated = line[:MAX_LINE_LENGTH]
        numbered.append(f"{i:>6}\t{truncated}")

    result = "\n".join(numbered)
    if len(lines) > offset + limit:
        result += f"\n\n... ({len(lines) - offset - limit} more lines)"

    return {"content": result, "is_error": False}


async def write_file(args: dict, cwd: str) -> dict:
    """Write content to a file, creating parent directories if needed."""
    path = resolve_path(args["path"], cwd)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return {"content": f"File written: {args['path']} ({len(args['content'])} chars)", "is_error": False}
    except Exception as e:
        return {"content": f"Error writing file: {e}", "is_error": True}


async def edit_file(args: dict, cwd: str) -> dict:
    """Edit a file by replacing old_string with new_string."""
    path = resolve_path(args["path"], cwd)
    if not path.exists():
        return {"content": f"Error: File not found: {args['path']}", "is_error": True}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"content": f"Error reading file: {e}", "is_error": True}

    old = args["old_string"]
    new = args["new_string"]

    count = text.count(old)
    if count == 0:
        return {"content": f"Error: old_string not found in {args['path']}", "is_error": True}
    if count > 1:
        return {
            "content": f"Error: old_string found {count} times in {args['path']}. Must be unique.",
            "is_error": True,
        }

    updated = text.replace(old, new, 1)
    try:
        path.write_text(updated, encoding="utf-8")
        return {"content": f"File edited: {args['path']}", "is_error": False}
    except Exception as e:
        return {"content": f"Error writing file: {e}", "is_error": True}


async def list_directory(args: dict, cwd: str) -> dict:
    """List directory contents."""
    dir_path = args.get("path", ".")
    path = resolve_path(dir_path, cwd)
    if not path.exists():
        return {"content": f"Error: Directory not found: {dir_path}", "is_error": True}
    if not path.is_dir():
        return {"content": f"Error: Not a directory: {dir_path}", "is_error": True}

    try:
        entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        lines = []
        for entry in entries[:500]:  # Limit entries
            name = entry.name + ("/" if entry.is_dir() else "")
            lines.append(name)
        result = "\n".join(lines) if lines else "(empty directory)"
        if len(list(path.iterdir())) > 500:
            result += f"\n\n... (truncated, {len(list(path.iterdir()))} total entries)"
        return {"content": result, "is_error": False}
    except Exception as e:
        return {"content": f"Error listing directory: {e}", "is_error": True}
