@echo off
setlocal
title Stop MiniMax H3 V2 DEV
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-dev.ps1"
echo.
pause
exit /b %ERRORLEVEL%
