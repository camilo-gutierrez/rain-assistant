# =============================================
#   Rain Assistant - Instalador (Windows)
#   irm <GIST_URL>/install.ps1 | iex
# =============================================

$ErrorActionPreference = "Stop"

$DOWNLOAD_URL = "https://github.com/camilo-gutierrez/rain-releases/releases/download/v1.0/rain-assistant.zip"

$DIR = "rain-assistant"

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "     Rain Assistant - Instalador          " -ForegroundColor Cyan
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""

function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  [X]  $msg" -ForegroundColor Red; Read-Host "  Presiona Enter para salir"; exit 1 }
function Write-Warn($msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }

# ---- Validar URL ----
if ($DOWNLOAD_URL -like "*PEGA-TU-URL-AQUI*") {
    Write-Fail "La URL de descarga no esta configurada. Contacta a quien te compartio este enlace."
}

# ---- 1. Verificar Python ----
Write-Host "[1/4] Verificando Python 3.10+..."
$py = $null
try {
    $pyVer = & python --version 2>&1
    if ($pyVer -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -ge 3 -and $minor -ge 10) {
            $py = "python"
            Write-Ok "Python encontrado: $pyVer"
        } else {
            Write-Fail "Se requiere Python 3.10+. Tienes $pyVer. Descargalo de: https://www.python.org/downloads/"
        }
    }
} catch {
    Write-Host ""
    Write-Host "  Python no esta instalado." -ForegroundColor Red
    Write-Host "  Descargalo de: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  IMPORTANTE: Marca 'Add Python to PATH' al instalarlo" -ForegroundColor Yellow
    Write-Host ""
    $resp = Read-Host "  Intentar instalar automaticamente con winget? (s/n)"
    if ($resp -eq "s") {
        try {
            & winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            Write-Warn "Python instalado. CIERRA esta ventana, abre una nueva y ejecuta el instalador de nuevo."
            Read-Host "  Presiona Enter para salir"
            exit 0
        } catch {
            Write-Fail "No se pudo instalar. Descargalo manualmente de python.org"
        }
    } else {
        Write-Fail "Instala Python y ejecuta esto de nuevo."
    }
}

# ---- 2. Verificar ffmpeg ----
Write-Host "[2/4] Verificando ffmpeg..."
$ffmpegOk = $false
try {
    & ffmpeg -version 2>&1 | Out-Null
    $ffmpegOk = $true
    Write-Ok "ffmpeg encontrado"
} catch {
    Write-Warn "ffmpeg no encontrado. Intentando instalar..."
    try {
        & winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        Write-Warn "ffmpeg instalado. Si hay problemas, reinicia la terminal."
    } catch {
        Write-Warn "No se pudo instalar ffmpeg automaticamente."
        Write-Host "  Descargalo de: https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Yellow
    }
}

# ---- 3. Descargar y descomprimir ----
Write-Host "[3/4] Descargando Rain Assistant..."
$zipFile = "$env:TEMP\rain-assistant-$(Get-Random).zip"

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $DOWNLOAD_URL -OutFile $zipFile -UseBasicParsing
    Write-Ok "Descarga completada"
} catch {
    Write-Fail "No se pudo descargar. Verifica tu conexion a internet y que la URL sea correcta."
}

if (Test-Path $DIR) {
    Write-Warn "La carpeta '$DIR' ya existe. Reemplazando..."
    Remove-Item -Recurse -Force $DIR
}

try {
    Expand-Archive -Path $zipFile -DestinationPath . -Force
    Remove-Item $zipFile -Force
    Write-Ok "Proyecto extraido en .\$DIR"
} catch {
    Write-Fail "Error al descomprimir. El archivo zip puede estar corrupto."
}

Set-Location $DIR

# ---- 4. Instalar dependencias ----
Write-Host "[4/4] Instalando dependencias de Python (esto puede tardar unos minutos)..."
& $py -m pip install --quiet --upgrade pip 2>$null
& $py -m pip install --quiet -r requirements.txt
Write-Ok "Dependencias instaladas"

# ---- Verificacion ----
Write-Host ""
Write-Host "  Verificando..." -ForegroundColor Cyan
try { & $py -c "import faster_whisper" 2>$null; Write-Ok "faster-whisper" } catch { Write-Warn "faster-whisper (se descargara al primer uso)" }
try { & $py -c "import sounddevice"    2>$null; Write-Ok "sounddevice"    } catch { Write-Warn "sounddevice" }
try { & $py -c "import fastapi"        2>$null; Write-Ok "fastapi"        } catch { Write-Warn "fastapi" }

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Green
Write-Host "     Instalacion completada!              " -ForegroundColor Green
Write-Host "  ========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Para iniciar Rain Assistant:" -ForegroundColor Cyan
Write-Host "    python server.py" -ForegroundColor White
Write-Host ""
Write-Host "  Luego abre en tu navegador:" -ForegroundColor Cyan
Write-Host "    http://localhost:8000" -ForegroundColor White
Write-Host ""
Read-Host "  Presiona Enter para salir"
