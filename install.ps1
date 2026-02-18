# Rain Assistant - Instalador (Windows)
# Uso: irm https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Rain Assistant - Instalador" -ForegroundColor Cyan
Write-Host "  ============================" -ForegroundColor Cyan
Write-Host ""

# ---- Python ----
try {
    $pyVer = & python --version 2>&1
    if ($pyVer -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -ge 3 -and $minor -ge 11) {
            Write-Host "  Python: $pyVer" -ForegroundColor Green
        } else {
            Write-Host "  Se requiere Python 3.11+. Tienes $pyVer" -ForegroundColor Red
            Write-Host "  https://www.python.org/downloads/" -ForegroundColor Yellow
            Read-Host "  Presiona Enter para salir"
            exit 1
        }
    }
} catch {
    Write-Host "  Python no encontrado." -ForegroundColor Red
    Write-Host "  Descargalo de: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  IMPORTANTE: Marca 'Add Python to PATH'" -ForegroundColor Yellow
    Write-Host ""
    $resp = Read-Host "  Instalar con winget? (s/n)"
    if ($resp -eq "s") {
        & winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        Write-Host "  Python instalado. Cierra esta ventana, abre una nueva y ejecuta de nuevo." -ForegroundColor Yellow
        Read-Host "  Presiona Enter para salir"
        exit 0
    }
    exit 1
}

# ---- Install ----
Write-Host ""
Write-Host "  Instalando Rain Assistant..." -ForegroundColor Cyan
& python -m pip install --upgrade rain-assistant

Write-Host ""
Write-Host "  ============================" -ForegroundColor Green
Write-Host "  Listo! Ejecuta:" -ForegroundColor Green
Write-Host "    rain" -ForegroundColor White
Write-Host ""
Read-Host "  Presiona Enter para salir"
