@echo off
title Enable LANDrop on Windows Startup
cd /d "%~dp0"
echo Registering LANDrop to start with Windows...
python -c "from core.autostart import set_autostart; success = set_autostart(True); print('Success!' if success else 'Failed!')"
echo.
echo LANDrop will now start silently in the background when you log into Windows.
echo You can disable it anytime from the LANDrop app or by running uninstall_startup.bat.
echo.
pause
