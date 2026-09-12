@echo off
setlocal
cd /d "%~dp0"

set "COMFY_LAUNCHER=%~dp0ComfyUI\run_nvidia_gpu_fast_fp16_accumulation.bat"
if not exist "%COMFY_LAUNCHER%" (
    echo [ERROR] ComfyUI launcher was not found:
    echo         %COMFY_LAUNCHER%
    pause
    exit /b 1
)

call "%COMFY_LAUNCHER%"
exit /b %ERRORLEVEL%
