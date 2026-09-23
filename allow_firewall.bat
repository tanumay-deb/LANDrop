@echo off
title Configure Windows Firewall for LANDrop
cd /d "%~dp0"

:: Check for administrative rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges to configure Windows Firewall...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo Adding permanent Windows Firewall rules for LANDrop (Port 5000 ^& mDNS)...
netsh advfirewall firewall delete rule name="LANDrop Wi-Fi File Transfer" >nul 2>&1
netsh advfirewall firewall delete rule name="LANDrop Wi-Fi File Transfer UDP" >nul 2>&1
netsh advfirewall firewall delete rule name="LANDrop mDNS Discovery" >nul 2>&1

netsh advfirewall firewall add rule name="LANDrop Wi-Fi File Transfer" dir=in action=allow protocol=TCP localport=5000 profile=any
netsh advfirewall firewall add rule name="LANDrop Wi-Fi File Transfer UDP" dir=in action=allow protocol=UDP localport=5000 profile=any
netsh advfirewall firewall add rule name="LANDrop mDNS Discovery" dir=in action=allow protocol=UDP localport=5353 profile=any

echo.
echo ========================================================
echo  SUCCESS! Windows Firewall rules added permanently.
echo  You will never see the firewall pop-up again!
echo ========================================================
echo.
timeout /t 3 >nul
exit
