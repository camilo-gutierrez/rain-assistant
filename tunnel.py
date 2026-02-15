"""Cloudflare Tunnel helper that works in both normal and PyInstaller frozen mode.

Instead of relying on pycloudflared (which breaks in frozen apps because it
resolves binary paths via ``Path(__file__).parent``), this module:

1. Stores / downloads the ``cloudflared`` binary in ``~/.rain-assistant/``
   (always writable, persists across runs).
2. Falls back to a copy shipped next to the .exe (``_internal/cloudflared.exe``
   or same directory) so offline usage is possible.
3. Runs the binary via subprocess and parses the tunnel URL from stderr.
"""

from __future__ import annotations

import atexit
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CLOUDFLARED_URLS = {
    ("windows", "amd64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    ("windows", "x86"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-386.exe",
    ("linux", "amd64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
    ("linux", "arm64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64",
    ("darwin", "amd64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz",
    ("darwin", "arm64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz",
}

_TUNNEL_RE = re.compile(r"(?P<url>https?://\S+\.trycloudflare\.com)")
_LINES_TO_CHECK = 50
_DATA_DIR = Path.home() / ".rain-assistant"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_platform_key() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    # Normalise machine names
    if machine in ("x86_64", "amd64"):
        machine = "amd64"
    elif machine in ("aarch64", "arm64"):
        machine = "arm64"
    elif machine in ("i386", "i686", "x86"):
        machine = "x86"
    return system, machine


def _binary_name() -> str:
    system, machine = _get_platform_key()
    # macOS .tgz archives contain a binary simply named "cloudflared"
    if system == "darwin":
        return "cloudflared"
    url = _CLOUDFLARED_URLS.get((system, machine), "")
    if url:
        return url.split("/")[-1]
    # Fallback for Windows
    if system == "windows":
        return "cloudflared-windows-amd64.exe"
    return "cloudflared"


def _find_binary() -> Path | None:
    """Look for an existing cloudflared binary in known locations."""
    name = _binary_name()

    # 1. ~/.rain-assistant/ (preferred persistent location)
    candidate = _DATA_DIR / name
    if candidate.exists():
        return candidate

    # 2. Next to the .exe (frozen mode: same dir or _internal/)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for loc in [exe_dir / name, exe_dir / "_internal" / name]:
            if loc.exists():
                return loc

    # 3. Inside pycloudflared site-packages (dev mode)
    try:
        import pycloudflared
        pkg_dir = Path(pycloudflared.__file__).parent
        candidate = pkg_dir / name
        if candidate.exists():
            return candidate
    except Exception:
        pass

    return None


def _download_binary() -> Path:
    """Download cloudflared to ~/.rain-assistant/ and return the path."""
    system, machine = _get_platform_key()
    url = _CLOUDFLARED_URLS.get((system, machine))
    if not url:
        raise RuntimeError(
            f"No cloudflared download available for {system}/{machine}"
        )

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = _DATA_DIR / _binary_name()

    print(f"  Downloading cloudflared...", flush=True)

    if url.endswith(".tgz"):
        # macOS releases are .tgz archives — download, extract, clean up
        with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            with urlopen(url) as resp:
                shutil.copyfileobj(resp, tmp)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extract("cloudflared", path=_DATA_DIR)
        tmp_path.unlink(missing_ok=True)
    else:
        with urlopen(url) as resp:
            with dest.open("wb") as f:
                shutil.copyfileobj(resp, f)

    if system != "windows":
        dest.chmod(0o755)

    print(f"  Downloaded to {dest}", flush=True)
    return dest


def _get_binary() -> Path:
    """Find or download the cloudflared binary."""
    binary = _find_binary()
    if binary is not None:
        return binary
    return _download_binary()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_process: subprocess.Popen | None = None


def start_tunnel(port: int) -> str | None:
    """Start a Cloudflare Tunnel on *port* and return the public URL.

    Returns ``None`` if the tunnel could not be started (no error raised).
    """
    global _process

    try:
        binary = _get_binary()
    except Exception as exc:
        print(f"  [tunnel] Could not find/download cloudflared: {exc}", flush=True)
        return None

    args = [
        str(binary),
        "tunnel",
        "--url",
        f"http://127.0.0.1:{port}",
    ]

    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"  [tunnel] Failed to start cloudflared: {exc}", flush=True)
        return None

    atexit.register(proc.terminate)
    _process = proc

    tunnel_url = ""
    for _ in range(_LINES_TO_CHECK):
        line = proc.stderr.readline()
        if not line:
            # Process exited
            break
        match = _TUNNEL_RE.search(line)
        if match:
            tunnel_url = match.group("url")
            break

    if not tunnel_url:
        print("  [tunnel] Could not obtain tunnel URL from cloudflared", flush=True)
        proc.terminate()
        _process = None
        return None

    return tunnel_url


def stop_tunnel() -> None:
    """Stop the running tunnel process if any."""
    global _process
    if _process is not None:
        _process.terminate()
        _process = None
