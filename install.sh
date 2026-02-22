#!/usr/bin/env bash
# Rain Assistant - Zero-Dependency Installer (Linux/macOS)
# Usage: curl -fsSL https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant/main/install.sh | bash
#
# Installs Rain Assistant automatically:
# - Installs Python 3.11+ if missing (via brew/apt/dnf/pacman)
# - Installs ffmpeg if missing
# - Creates isolated virtualenv in ~/.rain/
# - Adds 'rain' command to PATH

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
RAIN_DIR="$HOME/.rain"
PACKAGE_NAME="rain-assistant"
MIN_PY_MAJOR=3
MIN_PY_MINOR=11

# Install from PyPI (published package)
PACKAGE_SOURCE="$PACKAGE_NAME"

# ── Colors ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── Banner ─────────────────────────────────────────────────────────────────────
printf "\n${CYAN}  Rain Assistant - Installer${NC}\n"
printf "${CYAN}  =================================${NC}\n"
printf "${GRAY}  Zero-dependency installation${NC}\n\n"

# ── Detect platform ───────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Darwin) PLATFORM="macos" ;;
    Linux)  PLATFORM="linux" ;;
    *)      printf "${RED}  OS no soportado: $OS${NC}\n"; exit 1 ;;
esac

# ── Helper: find suitable Python ───────────────────────────────────────────────
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge "$MIN_PY_MAJOR" ] && [ "$minor" -ge "$MIN_PY_MINOR" ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# ── Step 1: Python ─────────────────────────────────────────────────────────────
printf "${CYAN}  [1/4] Python...${NC}\n"

PYTHON=""
if PYTHON=$(find_python); then
    PY_VER=$($PYTHON --version 2>&1)
    printf "${GRAY}      $PY_VER encontrado${NC}\n"
else
    printf "${YELLOW}      Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ no encontrado. Instalando...${NC}\n"

    if [ "$PLATFORM" = "macos" ]; then
        if command -v brew &>/dev/null; then
            brew install python@3.12
        else
            printf "${YELLOW}      Instalando Homebrew primero...${NC}\n"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            # Add brew to PATH for this session
            if [ -f /opt/homebrew/bin/brew ]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [ -f /usr/local/bin/brew ]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi
            brew install python@3.12
        fi
    else
        # Linux — try common package managers
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq python3 python3-pip python3-venv
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 python3-pip
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm python python-pip
        elif command -v zypper &>/dev/null; then
            sudo zypper install -y python3 python3-pip python3-venv
        elif command -v apk &>/dev/null; then
            sudo apk add python3 py3-pip
        else
            printf "${RED}      No se pudo instalar Python automaticamente.${NC}\n"
            printf "${RED}      Instala Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ manualmente y vuelve a ejecutar.${NC}\n"
            exit 1
        fi
    fi

    if PYTHON=$(find_python); then
        printf "${GRAY}      $($PYTHON --version) instalado${NC}\n"
    else
        printf "${RED}      ERROR: No se encontro Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ tras la instalacion.${NC}\n"
        exit 1
    fi
fi

# ── Step 2: ffmpeg ─────────────────────────────────────────────────────────────
printf "${CYAN}  [2/4] ffmpeg...${NC}\n"

if command -v ffmpeg &>/dev/null; then
    printf "${GRAY}      ffmpeg ya instalado${NC}\n"
else
    printf "${GRAY}      Instalando ffmpeg...${NC}\n"
    if [ "$PLATFORM" = "macos" ]; then
        brew install ffmpeg
    else
        if command -v apt-get &>/dev/null; then
            sudo apt-get install -y -qq ffmpeg
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y ffmpeg
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm ffmpeg
        elif command -v zypper &>/dev/null; then
            sudo zypper install -y ffmpeg
        elif command -v apk &>/dev/null; then
            sudo apk add ffmpeg
        else
            printf "${YELLOW}      WARN: No se pudo instalar ffmpeg. Instalalo manualmente para voz.${NC}\n"
        fi
    fi
fi

# ── Step 3: Install Rain Assistant ─────────────────────────────────────────────
printf "${CYAN}  [3/4] Instalando Rain Assistant...${NC}\n"

mkdir -p "$RAIN_DIR/bin"

# Create or reuse virtual environment
if [ ! -d "$RAIN_DIR/venv" ]; then
    printf "${GRAY}      Creando entorno virtual...${NC}\n"
    $PYTHON -m venv "$RAIN_DIR/venv"
fi

# Upgrade pip first
"$RAIN_DIR/venv/bin/pip" install --upgrade pip --quiet 2>/dev/null

# Install package
printf "${GRAY}      Instalando paquete (puede tardar)...${NC}\n"
"$RAIN_DIR/venv/bin/pip" install --upgrade "$PACKAGE_SOURCE" 2>&1 | \
    grep -i "successfully installed" | while IFS= read -r line; do
        printf "${GRAY}      $line${NC}\n"
    done

printf "${GRAY}      Rain Assistant instalado${NC}\n"

# ── Step 4: Create launcher & PATH ─────────────────────────────────────────────
printf "${CYAN}  [4/4] Configurando comandos...${NC}\n"

# Create rain launcher script
cat > "$RAIN_DIR/bin/rain" << 'LAUNCHER'
#!/usr/bin/env bash
RAIN_DIR="$HOME/.rain"
exec "$RAIN_DIR/venv/bin/python" -m rain_assistant "$@"
LAUNCHER
chmod +x "$RAIN_DIR/bin/rain"

# Create alias
ln -sf "$RAIN_DIR/bin/rain" "$RAIN_DIR/bin/rain-assistant"

# Create uninstaller
cat > "$RAIN_DIR/uninstall.sh" << 'UNINSTALL'
#!/usr/bin/env bash
printf "\n  Desinstalando Rain Assistant...\n"
RAIN_DIR="$HOME/.rain"

# Remove PATH entries from shell configs
for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile"; do
    if [ -f "$rc" ]; then
        sed -i.bak '/.rain\/bin/d' "$rc" 2>/dev/null
        sed -i.bak '/# Rain Assistant/d' "$rc" 2>/dev/null
        rm -f "${rc}.bak"
    fi
done

# Remove installation
rm -rf "$RAIN_DIR"

printf "  Rain Assistant desinstalado.\n"
printf "  Nota: ~/.rain-assistant/ (config/datos) NO se elimino.\n\n"
UNINSTALL
chmod +x "$RAIN_DIR/uninstall.sh"

# Add to PATH in shell config
PATH_LINE='export PATH="$HOME/.rain/bin:$PATH"'
ADDED_TO=""

for rc_file in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
    if [ -f "$rc_file" ]; then
        if ! grep -q '.rain/bin' "$rc_file" 2>/dev/null; then
            printf "\n# Rain Assistant\n%s\n" "$PATH_LINE" >> "$rc_file"
            ADDED_TO="$rc_file"
        fi
        break
    fi
done

# Also create .zshrc if on macOS and it doesn't exist
if [ "$PLATFORM" = "macos" ] && [ ! -f "$HOME/.zshrc" ] && [ -z "$ADDED_TO" ]; then
    printf "# Rain Assistant\n%s\n" "$PATH_LINE" > "$HOME/.zshrc"
    ADDED_TO="$HOME/.zshrc"
fi

if [ -n "$ADDED_TO" ]; then
    printf "${GRAY}      Agregado a PATH en $ADDED_TO${NC}\n"
fi

# Make rain available in current session
export PATH="$RAIN_DIR/bin:$PATH"

# ── Done ───────────────────────────────────────────────────────────────────────
printf "\n${GREEN}  =================================${NC}\n"
printf "${GREEN}  Rain Assistant instalado!${NC}\n\n"
printf "  Abre una ${YELLOW}NUEVA${NC} terminal y ejecuta:\n\n"
printf "    ${YELLOW}rain${NC}\n\n"
printf "${GRAY}  Ubicacion:    $RAIN_DIR${NC}\n"
printf "${GRAY}  Desinstalar:  bash $RAIN_DIR/uninstall.sh${NC}\n\n"
