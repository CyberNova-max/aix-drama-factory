@echo off
setlocal
title Qwen3.5-4B CUDA LLM Server - V2 DEV
cd /d "%~dp0"

set "CTX=16384"
set "PREDICT=4096"
set "PORT=8085"
set "MODEL_DIR=%~dp0models"
set "SERVER=%~dp0llama\llama-server.exe"

if not exist "%MODEL_DIR%\Qwen3.5-4B-Q4_K_M.gguf" exit /b 11
if not exist "%MODEL_DIR%\mmproj-BF16.gguf" exit /b 12
if not exist "%SERVER%" exit /b 13

nvidia-smi >nul 2>&1
if errorlevel 1 exit /b 21
"%SERVER%" --list-devices 2>&1 | findstr /i "CUDA" >nul
if errorlevel 1 exit /b 22

"%SERVER%" ^
  --model "%MODEL_DIR%\Qwen3.5-4B-Q4_K_M.gguf" ^
  --mmproj "%MODEL_DIR%\mmproj-BF16.gguf" ^
  --host 127.0.0.1 ^
  --port %PORT% ^
  --ctx-size %CTX% ^
  --n-predict %PREDICT% ^
  --n-gpu-layers -1 ^
  --flash-attn on ^
  --reasoning-budget 0

exit /b %ERRORLEVEL%
