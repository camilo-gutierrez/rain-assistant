#!/usr/bin/env bash
set -e

echo "============================================"
echo "  Voice Claude - Build"
echo "============================================"
echo

# ---- 1. Check PyInstaller ----
echo "[1/3] Verificando PyInstaller..."
if python -m PyInstaller --version &>/dev/null; then
    echo "  PyInstaller encontrado. OK"
else
    echo "  PyInstaller no encontrado. Instalando..."
    pip install pyinstaller
fi
echo

# ---- 2. Build ----
echo "[2/3] Construyendo VoiceClaude..."
echo "  Esto puede tardar varios minutos..."
echo
python -m PyInstaller voice_claude.spec --noconfirm
echo

# ---- 3. Verify ----
echo "[3/3] Verificando build..."
if [ -d "dist/VoiceClaude" ]; then
    echo "============================================"
    echo "  Build exitoso!"
    echo "  Output: dist/VoiceClaude/"
    echo "============================================"
    echo
    echo "  Para ejecutar: ./dist/VoiceClaude/VoiceClaude"
else
    echo "============================================"
    echo "  Build FALLIDO. Revisa los errores arriba."
    echo "============================================"
    exit 1
fi
