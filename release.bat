@echo off
setlocal enabledelayedexpansion

:: Siempre trabajar desde el directorio del script
cd /d "%~dp0"

echo.
echo  ========================================
echo    Rain Assistant - Empaquetador
echo  ========================================
echo    Directorio: %CD%
echo  ========================================
echo.

set "ZIP_NAME=rain-assistant.zip"
set "TEMP_DIR=%TEMP%\rain-release"
set "GH_REPO=camilo-gutierrez/rain-releases"

:: Pedir version
set /p VERSION="  Version (ej: v1.1): "
if "%VERSION%"=="" (
    echo  Error: Debes ingresar una version
    pause
    exit /b
)

:: Limpiar temporales
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%\rain-assistant"

echo.
echo [1/4] Copiando archivos del proyecto...

:: Python files
for %%f in (server.py main.py claude_client.py computer_use.py database.py permission_classifier.py rate_limiter.py recorder.py synthesizer.py transcriber.py tunnel.py) do (
    if exist "%%f" (
        copy "%%f" "%TEMP_DIR%\rain-assistant\" >nul
        echo   + %%f
    )
)

:: Config files
copy "requirements.txt" "%TEMP_DIR%\rain-assistant\" >nul
echo   + requirements.txt
copy "setup.bat" "%TEMP_DIR%\rain-assistant\" >nul
echo   + setup.bat
copy "setup.sh" "%TEMP_DIR%\rain-assistant\" >nul
echo   + setup.sh

:: Static folder (built frontend)
echo   + static/ (frontend compilado)
xcopy "static" "%TEMP_DIR%\rain-assistant\static\" /e /q /y >nul

echo.
echo [2/4] Creando %ZIP_NAME%...

:: Borrar zip anterior si existe
if exist "%ZIP_NAME%" del "%ZIP_NAME%"

:: Crear zip con Python (forward slashes, compatible con macOS/Linux)
python -c "import zipfile,os;root='%TEMP_DIR%\\rain-assistant';z=zipfile.ZipFile('%ZIP_NAME%','w',zipfile.ZIP_DEFLATED);[z.write(os.path.join(r,f),'rain-assistant/'+os.path.relpath(os.path.join(r,f),root).replace(chr(92),'/')) for r,_,fs in os.walk(root) for f in fs];z.close();print('  ZIP creado')"

echo.
echo [3/4] Limpiando temporales...
rmdir /s /q "%TEMP_DIR%"

:: Mostrar resultado
for %%A in ("%ZIP_NAME%") do set "SIZE=%%~zA"
set /a SIZE_MB=!SIZE! / 1048576

echo.
echo  %ZIP_NAME% creado (!SIZE_MB! MB)
echo.

echo [4/4] Subiendo a GitHub Releases...
gh release create %VERSION% %ZIP_NAME% --repo %GH_REPO% --title "Rain Assistant %VERSION%" --notes "Rain Assistant %VERSION%"

if %errorlevel% equ 0 (
    echo.
    echo  ========================================
    echo    Release %VERSION% publicado!
    echo  ========================================
    echo.
    echo  URL de descarga:
    echo    https://github.com/%GH_REPO%/releases/download/%VERSION%/%ZIP_NAME%
    echo.
    echo  IMPORTANTE: Si cambiaste la version, actualiza el Gist:
    echo    gh gist edit 3695a4020ed75d6b4ea1fa25d7fcf782
    echo.
) else (
    echo.
    echo  Error al subir. Verifica que:
    echo    - gh este instalado (winget install GitHub.cli)
    echo    - Estes autenticado (gh auth login)
    echo    - La version %VERSION% no exista ya
    echo.
)

pause
