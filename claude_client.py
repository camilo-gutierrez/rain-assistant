import subprocess
import json
import os

_has_conversation = False

_BASE_CMD = (
    "npx -y @anthropic-ai/claude-code -p"
    " --output-format json"
    " --disallowedTools Bash,Read,Write,Edit,Glob,Grep,"
    "WebFetch,WebSearch,Task,NotebookEdit,TodoWrite"
)


def _parse_response(output):
    """Extract text from Claude CLI JSON output."""
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            return data.get("result", data.get("text", output))
        if isinstance(data, list):
            parts = []
            for item in data:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(parts) if parts else output
    except json.JSONDecodeError:
        pass
    return output


def send_message(text):
    """Send a message to Claude Code CLI and return the response text."""
    global _has_conversation

    cmd = _BASE_CMD + (" --continue" if _has_conversation else "")

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    prompt_bytes = text.encode("utf-8")

    result = subprocess.run(
        cmd,
        input=prompt_bytes,
        capture_output=True,
        timeout=120,
        shell=True,
        env=env,
    )

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", "replace").strip()
        return f"[Error de Claude]: {error or 'Error desconocido'}"

    output = result.stdout.decode("utf-8", "replace").strip()
    if not output:
        return "[Sin respuesta de Claude]"

    _has_conversation = True
    return _parse_response(output)


def clear_history():
    """Clear the conversation state."""
    global _has_conversation
    _has_conversation = False
