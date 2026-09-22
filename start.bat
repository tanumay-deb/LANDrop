@echo off
cd /d "%~dp0"
where.exe pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" pythonw main.py
) else (
    start "" python main.py
)
exit
