"""Bash/shell command execution for the tool system."""

import asyncio
import sys

DEFAULT_TIMEOUT = 120  # seconds
MAX_OUTPUT_LENGTH = 30000


async def run_bash(args: dict, cwd: str) -> dict:
    """Execute a shell command in the working directory."""
    command = args.get("command", "").strip()
    if not command:
        return {"content": "Error: No command provided", "is_error": True}

    timeout = min(args.get("timeout", DEFAULT_TIMEOUT), 300)  # Max 5 minutes

    try:
        if sys.platform == "win32":
            proc = await asyncio.create_subprocess_exec(
                "cmd.exe", "/c", command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "bash", "-c", command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"content": f"Error: Command timed out after {timeout}s", "is_error": True}

        output_parts = []
        if stdout:
            decoded = stdout.decode("utf-8", errors="replace")
            output_parts.append(decoded)
        if stderr:
            decoded = stderr.decode("utf-8", errors="replace")
            output_parts.append(f"STDERR:\n{decoded}")

        output = "\n".join(output_parts) if output_parts else "(no output)"

        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n\n... (output truncated)"

        if proc.returncode != 0:
            output = f"Exit code: {proc.returncode}\n{output}"

        return {
            "content": output,
            "is_error": proc.returncode != 0,
        }

    except Exception as e:
        return {"content": f"Error executing command: {e}", "is_error": True}
