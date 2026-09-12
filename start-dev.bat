@echo off
setlocal
title MiniMax H3 Short Drama Factory V2 DEV
cd /d "%~dp0"

echo ================================================================
echo   MiniMax H3 Short Drama Factory V2 DEV
echo   Web  : http://127.0.0.1:7861
echo   Comfy: http://127.0.0.1:8190
echo   Qwen : http://127.0.0.1:8085 (started on demand)
echo ================================================================
echo.

REM Never compete with the stable GPU services.
netstat -ano -p tcp | findstr /R /C:"127.0.0.1:8189 .*LISTENING" >nul
if not errorlevel 1 goto :stable_busy
netstat -ano -p tcp | findstr /R /C:"127.0.0.1:8084 .*LISTENING" >nul
if not errorlevel 1 goto :stable_busy

curl -s -m 3 http://127.0.0.1:7861/ >nul 2>&1
if not errorlevel 1 (
    echo [OK] V2 development web is already online. Opening it now...
    start "" http://127.0.0.1:7861/
    exit /b 0
)

set "PYTHON=%~dp0ComfyUI\python_embeded\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] Development embedded Python was not found.
    pause
    exit /b 1
)

curl -s -m 3 http://127.0.0.1:8190/system_stats >nul 2>&1
if errorlevel 1 (
    echo [INFO] Starting development ComfyUI on port 8190...
    start "MiniMax H3 V2 DEV ComfyUI" /min "ComfyUI\run_nvidia_gpu_fast_fp16_accumulation.bat"
) else (
    echo [OK] Development ComfyUI is already online.
)

echo [INFO] Starting V2 development web at http://127.0.0.1:7861
"%PYTHON%" app.py
pause
exit /b %ERRORLEVEL%

:stable_busy
echo [BLOCKED] Stable GPU service is running on port 8189 or 8084.
echo           The V2 environment will not stop it or compete for VRAM.
echo           Wait for the stable job to finish, close its GPU services,
echo           then run start-dev.bat again.
pause
exit /b 2
