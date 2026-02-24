# Rain Assistant - Zero-Dependency Installer (Windows)
# Usage: irm https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant-installer/main/install.ps1 | iex
#
# Installs Rain Assistant without requiring Python, Node, or any other dependency.
# Downloads portable Python + ffmpeg and installs everything in ~/.rain/

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ── Configuration ──────────────────────────────────────────────────────────────
$RAIN_DIR       = "$env:USERPROFILE\.rain"
$PY_VERSION     = "3.12.8"
$PY_URL         = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-embed-amd64.zip"
$GETPIP_URL     = "https://bootstrap.pypa.io/get-pip.py"
$FFMPEG_URL     = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$PACKAGE_NAME   = "rain-assistant"

# Install from PyPI (published package)
$PACKAGE_SOURCE = $PACKAGE_NAME

# ── Banner ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Rain Assistant - Installer" -ForegroundColor Cyan
Write-Host "  =================================" -ForegroundColor Cyan
Write-Host "  Zero-dependency installation" -ForegroundColor DarkGray
Write-Host ""

# ── Pre-flight checks ─────────────────────────────────────────────────────────
if ([Environment]::Is64BitOperatingSystem -eq $false) {
    Write-Host "  ERROR: Se requiere Windows 64-bit." -ForegroundColor Red
    exit 1
}

# Check if already installed
if (Test-Path "$RAIN_DIR\python\python.exe") {
    Write-Host "  Rain ya esta instalado en $RAIN_DIR" -ForegroundColor Yellow
    $resp = Read-Host "  Actualizar/reinstalar? (s/n)"
    if ($resp -notmatch '^[sSyY]') { exit 0 }
}

# ── Helper ─────────────────────────────────────────────────────────────────────
function Download-File {
    param([string]$Url, [string]$Dest, [string]$Label)
    Write-Host "      Descargando $Label..." -ForegroundColor DarkGray
    $prevPref = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    } catch {
        Write-Host "      ERROR descargando $Label" -ForegroundColor Red
        Write-Host "      URL: $Url" -ForegroundColor DarkGray
        throw
    } finally {
        $ProgressPreference = $prevPref
    }
}

# ── Create directories ─────────────────────────────────────────────────────────
foreach ($dir in @("$RAIN_DIR", "$RAIN_DIR\python", "$RAIN_DIR\ffmpeg", "$RAIN_DIR\bin")) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

# ── Step 1: Python Embedded ────────────────────────────────────────────────────
Write-Host "  [1/5] Python $PY_VERSION (portable)..." -ForegroundColor Cyan

if (-not (Test-Path "$RAIN_DIR\python\python.exe")) {
    $pyZip = "$env:TEMP\rain-python-embed.zip"
    Download-File $PY_URL $pyZip "Python $PY_VERSION"

    Write-Host "      Extrayendo..." -ForegroundColor DarkGray
    Expand-Archive -Path $pyZip -DestinationPath "$RAIN_DIR\python" -Force
    Remove-Item $pyZip -ErrorAction SilentlyContinue
    Write-Host "      Python extraido" -ForegroundColor DarkGray
} else {
    Write-Host "      Python ya existe, reutilizando" -ForegroundColor DarkGray
}

# ── Step 2: Configure pip ──────────────────────────────────────────────────────
Write-Host "  [2/5] Configurando pip..." -ForegroundColor Cyan

# Enable import site in _pth file (required for pip/packages to work)
$pthFile = Get-ChildItem "$RAIN_DIR\python" -Filter "python*._pth" | Select-Object -First 1
if ($pthFile) {
    $pthContent = Get-Content $pthFile.FullName -Raw
    # Uncomment import site
    $pthContent = $pthContent -replace '#\s*import site', 'import site'
    # Ensure Lib\site-packages is on the path
    if ($pthContent -notmatch 'Lib\\site-packages') {
        $pthContent = $pthContent.TrimEnd() + "`r`nLib\site-packages`r`n"
    }
    Set-Content $pthFile.FullName $pthContent -NoNewline
    Write-Host "      _pth configurado" -ForegroundColor DarkGray
}

# Install pip if not present
if (-not (Test-Path "$RAIN_DIR\python\Scripts\pip.exe")) {
    $getPip = "$env:TEMP\rain-get-pip.py"
    Download-File $GETPIP_URL $getPip "pip installer"
    & "$RAIN_DIR\python\python.exe" $getPip --no-warn-script-location 2>&1 | Out-Null
    Remove-Item $getPip -ErrorAction SilentlyContinue
}
Write-Host "      pip listo" -ForegroundColor DarkGray

# ── Step 3: ffmpeg ─────────────────────────────────────────────────────────────
Write-Host "  [3/5] ffmpeg..." -ForegroundColor Cyan

if (-not (Test-Path "$RAIN_DIR\ffmpeg\ffmpeg.exe")) {
    $ffZip = "$env:TEMP\rain-ffmpeg.zip"
    Download-File $FFMPEG_URL $ffZip "ffmpeg"

    Write-Host "      Extrayendo (puede tardar)..." -ForegroundColor DarkGray
    $ffTemp = "$env:TEMP\rain-ffmpeg-extract"
    Expand-Archive -Path $ffZip -DestinationPath $ffTemp -Force

    # Find ffmpeg.exe in nested directories
    $ffBin = Get-ChildItem -Recurse -Path $ffTemp -Filter "ffmpeg.exe" | Select-Object -First 1
    if ($ffBin) {
        Copy-Item $ffBin.FullName "$RAIN_DIR\ffmpeg\ffmpeg.exe" -Force
        # Also grab ffprobe if available
        $ffProbe = Get-ChildItem -Recurse -Path $ffTemp -Filter "ffprobe.exe" | Select-Object -First 1
        if ($ffProbe) {
            Copy-Item $ffProbe.FullName "$RAIN_DIR\ffmpeg\ffprobe.exe" -Force
        }
        Write-Host "      ffmpeg instalado" -ForegroundColor DarkGray
    } else {
        Write-Host "      WARN: ffmpeg.exe no encontrado en el archivo" -ForegroundColor Yellow
    }

    Remove-Item $ffZip -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $ffTemp -ErrorAction SilentlyContinue
} else {
    Write-Host "      ffmpeg ya existe" -ForegroundColor DarkGray
}

# ── Step 4: Install Rain Assistant ─────────────────────────────────────────────
Write-Host "  [4/5] Instalando Rain Assistant..." -ForegroundColor Cyan

# Ensure ffmpeg and python are on PATH for the install process
$env:PATH = "$RAIN_DIR\ffmpeg;$RAIN_DIR\python;$RAIN_DIR\python\Scripts;$env:PATH"

& "$RAIN_DIR\python\python.exe" -m pip install --upgrade $PACKAGE_SOURCE --no-warn-script-location 2>&1 |
    ForEach-Object {
        $line = $_.ToString()
        if ($line -match "Successfully installed") {
            Write-Host "      $line" -ForegroundColor DarkGray
        }
    }

Write-Host "      Rain Assistant instalado" -ForegroundColor DarkGray

# ── Step 5: Create launchers & PATH ────────────────────────────────────────────
Write-Host "  [5/5] Configurando comandos..." -ForegroundColor Cyan

# rain.bat — CMD launcher
$batContent = @"
@echo off
set "RAIN_DIR=%USERPROFILE%\.rain"
set "PATH=%RAIN_DIR%\ffmpeg;%RAIN_DIR%\python;%RAIN_DIR%\python\Scripts;%PATH%"
"%RAIN_DIR%\python\python.exe" -m rain_assistant %*
"@
Set-Content "$RAIN_DIR\bin\rain.bat" $batContent -Encoding ASCII
Copy-Item "$RAIN_DIR\bin\rain.bat" "$RAIN_DIR\bin\rain-assistant.bat" -Force

# rain.ps1 — PowerShell launcher
$ps1Content = @"
`$env:PATH = "`$env:USERPROFILE\.rain\ffmpeg;`$env:USERPROFILE\.rain\python;`$env:USERPROFILE\.rain\python\Scripts;`$env:PATH"
& "`$env:USERPROFILE\.rain\python\python.exe" -m rain_assistant @args
"@
Set-Content "$RAIN_DIR\bin\rain.ps1" $ps1Content

# Uninstaller
$uninstallContent = @"
# Rain Assistant - Uninstaller
Write-Host ""
Write-Host "  Rain Assistant - Desinstalador" -ForegroundColor Cyan
Write-Host ""

`$rainDir = "`$env:USERPROFILE\.rain"
`$binPath = "`$rainDir\bin"

# Remove from PATH
`$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if (`$currentPath -like "*`$binPath*") {
    `$newPath = (`$currentPath -split ';' | Where-Object { `$_ -ne `$binPath -and `$_ -ne "" }) -join ';'
    [Environment]::SetEnvironmentVariable("PATH", `$newPath, "User")
    Write-Host "  Removido de PATH" -ForegroundColor DarkGray
}

# Remove installation
if (Test-Path `$rainDir) {
    Remove-Item -Recurse -Force `$rainDir
    Write-Host "  Archivos eliminados: `$rainDir" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  Rain Assistant desinstalado." -ForegroundColor Green
Write-Host "  Nota: ~/.rain-assistant/ (config/datos) NO se elimino." -ForegroundColor Yellow
Write-Host ""
"@
Set-Content "$RAIN_DIR\uninstall.ps1" $uninstallContent

# Add bin to user PATH
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$binPath = "$RAIN_DIR\bin"
if ($currentPath -notlike "*$binPath*") {
    [Environment]::SetEnvironmentVariable("PATH", "$binPath;$currentPath", "User")
    $env:PATH = "$binPath;$env:PATH"
    Write-Host "      Agregado a PATH del usuario" -ForegroundColor DarkGray
}

# ── Done ───────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  =================================" -ForegroundColor Green
Write-Host "  Rain Assistant instalado!" -ForegroundColor Green
Write-Host ""
Write-Host "  Abre una NUEVA terminal y ejecuta:" -ForegroundColor White
Write-Host ""
Write-Host "    rain" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Ubicacion:    $RAIN_DIR" -ForegroundColor DarkGray
Write-Host "  Desinstalar:  powershell $RAIN_DIR\uninstall.ps1" -ForegroundColor DarkGray
Write-Host ""
