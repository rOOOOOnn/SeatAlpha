@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-SeatAlpha.ps1" -ForceUpdate
if errorlevel 1 pause
endlocal
