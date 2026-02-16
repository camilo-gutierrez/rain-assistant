#!/usr/bin/env bash
set -e

URL="https://github.com/camilo-gutierrez/rain-releases/releases/download/v1.0/rain-assistant.zip"
DIR="rain-assistant"

printf '\n  Rain Assistant - Instalador\n  ============================\n\n'

# ---- Python ----
printf '  Verificando Python...  '
PY=""
command -v python3 &>/dev/null && PY=python3
[ -z "$PY" ] && command -v python &>/dev/null && PY=python
if [ -z "$PY" ]; then
    printf 'NO ENCONTRADO\n\n'
    printf '  Instala Python 3.10+ desde:\n  https://www.python.org/downloads/\n\n'
    exit 1
fi
PY_MINOR=$($PY -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    printf 'VERSION MUY VIEJA\n\n'
    printf '  Necesitas Python 3.10 o mayor.\n  https://www.python.org/downloads/\n\n'
    exit 1
fi
printf 'OK (%s)\n' "$($PY --version 2>&1)"

# ---- ffmpeg ----
printf '  Verificando ffmpeg...  '
if command -v ffmpeg &>/dev/null; then
    printf 'OK\n'
else
    printf 'instalando...\n'
    OS="$(uname -s)"
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            brew install --quiet ffmpeg portaudio 2>/dev/null
        else
            printf '\n  Necesitas Homebrew. Ejecuta esto primero:\n'
            printf '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"\n\n'
            printf '  Luego ejecuta este instalador de nuevo.\n\n'
            exit 1
        fi
    else
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg portaudio19-dev unzip
        fi
    fi
    printf '  ffmpeg instalado.\n'
fi

# ---- macOS portaudio ----
if [ "$(uname -s)" = "Darwin" ]; then
    if ! brew list portaudio &>/dev/null 2>&1; then
        brew install --quiet portaudio 2>/dev/null
    fi
fi

# ---- Descargar ----
printf '  Descargando...         '
ZIP="/tmp/rain-assistant-$$.zip"
curl -fSL -o "$ZIP" "$URL" 2>/dev/null
printf 'OK\n'

printf '  Instalando...          '
[ -d "$DIR" ] && rm -rf "$DIR"
unzip -q "$ZIP" -d .
rm -f "$ZIP"
printf 'OK\n'

cd "$DIR"

# ---- Dependencias Python ----
printf '  Instalando paquetes... (esto tarda 1-2 min)\n'
$PY -m pip install --quiet --upgrade pip 2>/dev/null
$PY -m pip install --quiet -r requirements.txt 2>/dev/null
printf '  Paquetes instalados.\n'

# ---- Listo ----
printf '\n'
printf '  ============================\n'
printf '  Listo! Para usar Rain:\n'
printf '\n'
printf '  1. Ejecuta:\n'
printf '     cd %s && %s server.py\n' "$DIR" "$PY"
printf '\n'
printf '  2. Abre en el navegador:\n'
printf '     http://localhost:8000\n'
printf '\n'
printf '  3. Para usarlo en el celular,\n'
printf '     copia la URL que dice "Public:"\n'
printf '     y abrela en el navegador del cel.\n'
printf '  ============================\n\n'
