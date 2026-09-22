@echo off
title Disable LANDrop from Windows Startup
cd /d "%~dp0"
echo Removing LANDrop from Windows startup...
python -c "from core.autostart import set_autostart; success = set_autostart(False); print('Success!' if success else 'Failed!')"
echo.
echo LANDrop will no longer start automatically with Windows.
echo.
pause
