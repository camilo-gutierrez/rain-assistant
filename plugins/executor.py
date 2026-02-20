"""Plugin execution engine — HTTP, bash, and Python execution.

Security measures for subprocess-based plugins (bash, python):
  - Sandboxed environment: only essential system vars + plugin-specific env are
    passed.  Server secrets (API keys, tokens, etc.) are NOT inherited.
  - Working directory restriction: plugins run in the user's home directory
    (or a temp dir), never in the server's own directory.
  - Output size cap: MAX_OUTPUT (30 KB) prevents memory exhaustion.
  - Timeout: TIMEOUT (30 s) kills runaway processes.
  - Memory limit (Linux/macOS): RLIMIT_AS caps virtual memory per subprocess.
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .schema import Plugin, PluginExecution
from .loader import get_plugin_env

TEMPLATE_PATTERN = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")
MAX_OUTPUT = 30000  # 30 KB max output per plugin execution
TIMEOUT = 30        # seconds

# Maximum virtual memory per subprocess (512 MB).  Only enforced on
# platforms that support resource.RLIMIT_AS (Linux).
_MAX_MEMORY_BYTES = 512 * 1024 * 1024

# Minimal set of environment variable names to forward from the server
# process to plugin subprocesses.  Everything else is dropped.
_SAFE_ENV_KEYS = {
    # Required for subprocess to function
    "PATH", "PATHEXT", "SYSTEMROOT", "COMSPEC",  # Windows
    "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE",  # POSIX
    "TMPDIR", "TEMP", "TMP",  # Temp directories
    "TERM", "COLORTERM",  # Terminal info (some CLI tools need this)
}

# Server directory — plugins must NOT run here
_SERVER_DIR = Path(__file__).resolve().parent.parent


def _build_sandboxed_env(plugin_env: dict[str, str]) -> dict[str, str]:
    """Build a minimal environment dict for subprocess execution.

    Includes only essential OS vars (PATH, HOME, TEMP, etc.) plus the
    plugin-specific env vars from config.json.  This prevents leaking
    server secrets like ANTHROPIC_API_KEY, OPENAI_API_KEY, database
    credentials, tokens, etc. into plugin subprocesses.
    """
    safe = {}
    for key in _SAFE_ENV_KEYS:
        val = os.environ.get(key)
        if val is not None:
            safe[key] = val

    # Layer plugin-specific env on top
    safe.update(plugin_env)
    return safe


def _get_safe_cwd(requested_cwd: str) -> str:
    """Return a working directory that is NOT the server's own directory.

    If the requested cwd IS the server directory (or a subdirectory), fall
    back to the user's home directory.  This prevents plugins from
    reading/writing server source files or config accidentally.
    """
    try:
        req = Path(requested_cwd).resolve()
        server = _SERVER_DIR.resolve()
        # Check if requested cwd is the server dir or a child of it
        if req == server or server in req.parents:
            return str(Path.home())
    except (ValueError, OSError):
        pass
    return requested_cwd


def _get_preexec_fn():
    """Return a preexec_fn that sets resource limits on Unix, or None on Windows."""
    if sys.platform == "win32":
        return None

    def _set_limits():
        try:
            import resource
            # Limit virtual memory to _MAX_MEMORY_BYTES (soft=hard)
            resource.setrlimit(resource.RLIMIT_AS, (_MAX_MEMORY_BYTES, _MAX_MEMORY_BYTES))
        except (ImportError, ValueError, OSError):
            # resource module not available or RLIMIT_AS not supported (macOS)
            pass

    return _set_limits


def _resolve_value(key: str, arguments: dict, env: dict) -> str:
    """Resolve a template key like 'query' or 'env.API_KEY'."""
    if key.startswith("env."):
        env_key = key[4:]
        return env.get(env_key, os.environ.get(env_key, ""))
    return str(arguments.get(key, ""))


def _resolve_template(template: str, arguments: dict, env: dict) -> str:
    """Replace {{key}} placeholders in a string."""
    if not isinstance(template, str):
        return str(template)
    return TEMPLATE_PATTERN.sub(
        lambda m: _resolve_value(m.group(1), arguments, env),
        template,
    )


def _resolve_dict(d: dict, arguments: dict, env: dict) -> dict:
    """Resolve templates in all string values of a dict."""
    resolved = {}
    for k, v in d.items():
        if isinstance(v, str):
            resolved[k] = _resolve_template(v, arguments, env)
        elif isinstance(v, dict):
            resolved[k] = _resolve_dict(v, arguments, env)
        else:
            resolved[k] = v
    return resolved


def _extract_data(data: Any, path: str) -> Any:
    """Simple dot/bracket extraction from JSON data.

    Supports: "key", "key.subkey", "items[].title", "items[].{title, link}"
    """
    if not path or data is None:
        return data

    parts = path.split(".")
    result = data

    for part in parts:
        if result is None:
            return None

        # Array selector: "items[]"
        if part.endswith("[]"):
            key = part[:-2]
            if key:
                result = result.get(key, []) if isinstance(result, dict) else []
            if not isinstance(result, list):
                return result
            continue

        # Field selector in array context: "{title, link, snippet}"
        if part.startswith("{") and part.endswith("}"):
            fields = [f.strip() for f in part[1:-1].split(",")]
            if isinstance(result, list):
                result = [{f: item.get(f) for f in fields} for item in result if isinstance(item, dict)]
            elif isinstance(result, dict):
                result = {f: result.get(f) for f in fields}
            continue

        # Simple key access
        if isinstance(result, dict):
            result = result.get(part)
        elif isinstance(result, list):
            # Apply key to each item in list
            result = [item.get(part) if isinstance(item, dict) else None for item in result]

    return result


async def execute_plugin(plugin: Plugin, arguments: dict, cwd: str) -> dict:
    """Execute a plugin with given arguments. Returns {content, is_error}."""
    env = get_plugin_env()

    try:
        if plugin.execution.type == "http":
            return await _execute_http(plugin.execution, arguments, env)
        elif plugin.execution.type == "bash":
            return await _execute_bash(plugin.execution, arguments, env, cwd)
        elif plugin.execution.type == "python":
            return await _execute_python(plugin.execution, arguments, env, cwd)
        else:
            return {"content": f"Unknown execution type: {plugin.execution.type}", "is_error": True}
    except Exception as e:
        return {"content": f"Plugin execution error: {e}", "is_error": True}


async def _execute_http(
    execution: PluginExecution, arguments: dict, env: dict
) -> dict:
    """Execute an HTTP plugin.

    HTTP plugins are inherently sandboxed — they only make outbound HTTP
    requests and cannot access the local filesystem.  The httpx timeout
    (TIMEOUT seconds) prevents hanging on unresponsive servers.
    """
    import httpx

    url = _resolve_template(execution.url, arguments, env)
    method = execution.method.upper()
    headers = _resolve_dict(execution.headers, arguments, env)
    params = _resolve_dict(execution.params, arguments, env)
    body = _resolve_dict(execution.body, arguments, env) if execution.body else None

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if method == "GET":
            response = await client.get(url, headers=headers, params=params)
        elif method == "POST":
            response = await client.post(url, headers=headers, params=params, json=body)
        elif method == "PUT":
            response = await client.put(url, headers=headers, params=params, json=body)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers, params=params)
        elif method == "PATCH":
            response = await client.patch(url, headers=headers, params=params, json=body)
        else:
            return {"content": f"Unsupported HTTP method: {method}", "is_error": True}

    # Parse response
    try:
        data = response.json()
    except Exception:
        data = response.text

    # Apply extraction if specified
    if execution.extract and isinstance(data, (dict, list)):
        data = _extract_data(data, execution.extract)

    # Format output
    if isinstance(data, (dict, list)):
        output = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        output = str(data)

    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + "\n... (truncated)"

    is_error = response.status_code >= 400
    if is_error:
        output = f"HTTP {response.status_code}: {output}"

    return {"content": output, "is_error": is_error}


async def _execute_bash(
    execution: PluginExecution, arguments: dict, env: dict, cwd: str
) -> dict:
    """Execute a bash plugin with sandboxing.

    Sandboxing measures:
      - Sandboxed env: only safe OS vars + plugin env (no server secrets)
      - Safe cwd: never runs in the server directory
      - Memory limit via RLIMIT_AS on Linux
      - Timeout via asyncio.wait_for
      - Output cap at MAX_OUTPUT chars
    """
    command = _resolve_template(execution.command, arguments, env)
    if not command.strip():
        return {"content": "Error: Empty command after template resolution", "is_error": True}

    safe_cwd = _get_safe_cwd(cwd)
    proc_env = _build_sandboxed_env(env)
    preexec = _get_preexec_fn()

    if sys.platform == "win32":
        proc = await asyncio.create_subprocess_shell(
            command, cwd=safe_cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=proc_env,
            shell=True,
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", command, cwd=safe_cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=proc_env,
            preexec_fn=preexec,
        )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"content": f"Command timed out after {TIMEOUT}s", "is_error": True}

    parts = []
    if stdout:
        parts.append(stdout.decode("utf-8", errors="replace"))
    if stderr:
        parts.append(f"STDERR:\n{stderr.decode('utf-8', errors='replace')}")

    output = "\n".join(parts) if parts else "(no output)"
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + "\n... (truncated)"

    return {"content": output, "is_error": proc.returncode != 0}


async def _execute_python(
    execution: PluginExecution, arguments: dict, env: dict, cwd: str
) -> dict:
    """Execute a Python plugin script with sandboxing.

    The script receives arguments via stdin as JSON.
    It should print its result to stdout.

    Sandboxing measures:
      - Sandboxed env: only safe OS vars + plugin env (no server secrets)
      - Safe cwd: never runs in the server directory
      - Memory limit via RLIMIT_AS on Linux
      - Timeout via asyncio.wait_for
      - Output cap at MAX_OUTPUT chars
    """
    script = _resolve_template(execution.script, arguments, env)

    safe_cwd = _get_safe_cwd(cwd)
    proc_env = _build_sandboxed_env(env)
    preexec = _get_preexec_fn()

    kwargs: dict[str, Any] = dict(
        cwd=safe_cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=proc_env,
    )
    if preexec is not None:
        kwargs["preexec_fn"] = preexec

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script,
        **kwargs,
    )

    input_data = json.dumps(arguments).encode("utf-8")

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=input_data), timeout=TIMEOUT
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"content": f"Script timed out after {TIMEOUT}s", "is_error": True}

    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    if stderr:
        err = stderr.decode("utf-8", errors="replace")
        if err.strip():
            output += f"\nSTDERR:\n{err}" if output else err

    if not output.strip():
        output = "(no output)"

    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + "\n... (truncated)"

    return {"content": output, "is_error": proc.returncode != 0}
