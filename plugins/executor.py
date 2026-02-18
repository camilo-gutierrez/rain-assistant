"""Plugin execution engine — HTTP, bash, and Python execution."""

import asyncio
import json
import os
import re
import sys
from typing import Any

from .schema import Plugin, PluginExecution
from .loader import get_plugin_env

TEMPLATE_PATTERN = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")
MAX_OUTPUT = 30000
TIMEOUT = 30


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
    """Execute an HTTP plugin."""
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
    """Execute a bash plugin."""
    command = _resolve_template(execution.command, arguments, env)
    if not command.strip():
        return {"content": "Error: Empty command after template resolution", "is_error": True}

    if sys.platform == "win32":
        proc = await asyncio.create_subprocess_shell(
            command, cwd=cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            shell=True,
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", command, cwd=cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
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
    """Execute a Python plugin script.

    The script receives arguments via stdin as JSON.
    It should print its result to stdout.
    """
    script = _resolve_template(execution.script, arguments, env)

    # Build environment with plugin env vars
    proc_env = {**os.environ, **env}

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=proc_env,
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
