@echo off
title Build LANDrop Executable
cd /d "%~dp0"
echo ========================================================
echo   Building LANDrop Standalone Executable (PyInstaller)
echo ========================================================
echo.
python -m PyInstaller --onefile --noconsole --name "LANDrop" --add-data "templates;templates" --add-data "static;static" main.py
echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo   BUILD SUCCESSFUL!
    echo   Executable is ready at: dist\LANDrop.exe
    echo ========================================================
) else (
    echo [ERROR] Build failed! Check the output above.
)
echo.
pause
