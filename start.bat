@echo off
title LANDrop - Wi-Fi File Transfer
cd /d "%~dp0"
echo Starting LANDrop...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Running in headless mode...
    python main.py --headless
)
pause
