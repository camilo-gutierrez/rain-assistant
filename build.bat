@echo off
echo ============================================
echo   Rain Assistant - Build Installer
echo ============================================
echo.

echo [1/3] Checking PyInstaller...
python -m PyInstaller --version >nul 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)
echo.

echo [2/3] Building RainAssistant.exe...
echo This may take several minutes...
echo.
python -m PyInstaller rain_assistant.spec --noconfirm
echo.

if exist "dist\RainAssistant\RainAssistant.exe" (
    echo ============================================
    echo   Build successful!
    echo   Output: dist\RainAssistant\RainAssistant.exe
    echo ============================================
    echo.
    echo To run: dist\RainAssistant\RainAssistant.exe
) else (
    echo ============================================
    echo   Build FAILED. Check the errors above.
    echo ============================================
)
echo.
pause
