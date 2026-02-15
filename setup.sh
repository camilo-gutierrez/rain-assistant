#!/usr/bin/env bash
set -e

echo "============================================"
echo "  Voice Claude - Instalacion automatica"
echo "============================================"
echo

OS="$(uname -s)"

# ---- 1. ffmpeg ----
echo "[1/3] Verificando ffmpeg..."
if command -v ffmpeg &>/dev/null; then
    echo "  ffmpeg ya esta instalado. OK"
else
    echo "  ffmpeg no encontrado. Instalando..."
    if [ "$OS" = "Darwin" ]; then
        if ! command -v brew &>/dev/null; then
            echo "  ERROR: Homebrew no esta instalado. Instalalo desde https://brew.sh"
            exit 1
        fi
        brew install ffmpeg
    else
        if command -v apt-get &>/dev/null; then
            sudo apt-get update && sudo apt-get install -y ffmpeg portaudio19-dev
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y ffmpeg portaudio-devel
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm ffmpeg portaudio
        else
            echo "  ERROR: No se detecto un gestor de paquetes compatible (apt/dnf/pacman)."
            exit 1
        fi
    fi
fi

# ---- 2. PortAudio (macOS) ----
if [ "$OS" = "Darwin" ]; then
    echo
    echo "[1.5/3] Verificando portaudio (macOS)..."
    if brew list portaudio &>/dev/null; then
        echo "  portaudio ya esta instalado. OK"
    else
        brew install portaudio
    fi
fi
echo

# ---- 3. Python dependencies ----
echo "[2/3] Instalando dependencias de Python..."
pip install -r requirements.txt
echo

# ---- 4. Verify ----
echo "[3/3] Verificando instalacion..."
python -c "import sounddevice; print('  sounddevice: OK')"
python -c "import faster_whisper; print('  faster-whisper: OK')"
python -c "import numpy; print('  numpy: OK')"
python -c "import fastapi; print('  fastapi: OK')"
echo

echo "============================================"
echo "  Instalacion completada!"
echo "  Ejecuta: python server.py"
echo "============================================"
