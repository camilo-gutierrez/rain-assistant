#!/usr/bin/env bash
set -e

printf '\n  Rain Assistant - Instalador\n  ============================\n\n'

# ---- Python ----
PY=""
command -v python3 &>/dev/null && PY=python3
[ -z "$PY" ] && command -v python &>/dev/null && PY=python
if [ -z "$PY" ]; then
    printf '  Python 3.11+ requerido.\n'
    printf '  https://www.python.org/downloads/\n\n'
    exit 1
fi
PY_VER=$($PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
printf '  Python: %s\n' "$PY_VER"

# ---- ffmpeg ----
if command -v ffmpeg &>/dev/null; then
    printf '  ffmpeg: OK\n'
else
    printf '  ffmpeg: no encontrado (necesario para voz)\n'
    OS="$(uname -s)"
    if [ "$OS" = "Darwin" ]; then
        printf '  Instalar: brew install ffmpeg\n'
    else
        printf '  Instalar: sudo apt install ffmpeg\n'
    fi
fi

# ---- Install ----
printf '\n  Instalando Rain Assistant...\n\n'
$PY -m pip install --upgrade rain-assistant

printf '\n  ============================\n'
printf '  Listo! Ejecuta:\n\n'
printf '    rain\n\n'
