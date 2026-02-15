@echo off
echo ============================================
echo   Rain Assistant - Instalacion automatica
echo ============================================
echo.

echo [1/3] Verificando ffmpeg...
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo ffmpeg no encontrado. Instalando con winget...
    winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
    echo.
    echo IMPORTANTE: Cierra y vuelve a abrir esta terminal para que ffmpeg este disponible.
    echo Luego ejecuta este script de nuevo.
    pause
    exit /b
) else (
    echo ffmpeg ya esta instalado. OK
)
echo.

echo [2/3] Instalando dependencias de Python...
pip install -r requirements.txt
echo.

echo [3/3] Verificando instalacion...
python -c "import sounddevice; print('sounddevice: OK')"
python -c "import faster_whisper; print('faster-whisper: OK')"
python -c "import numpy; print('numpy: OK')"
echo.

echo ============================================
echo   Instalacion completada!
echo   Ejecuta: python server.py
echo ============================================
pause
