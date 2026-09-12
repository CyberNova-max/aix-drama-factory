@echo off
setlocal
title AIX DramaFactory V2 Web
cd /d "%~dp0"

set "AIX_WEB_PYTHON="
if defined AIX_PYTHON if exist "%AIX_PYTHON%" set "AIX_WEB_PYTHON=%AIX_PYTHON%"
if not defined AIX_WEB_PYTHON if exist "%~dp0runtime\comfyui\python_embeded\python.exe" set "AIX_WEB_PYTHON=%~dp0runtime\comfyui\python_embeded\python.exe"
if not defined AIX_WEB_PYTHON if exist "%~dp0ComfyUI\python_embeded\python.exe" set "AIX_WEB_PYTHON=%~dp0ComfyUI\python_embeded\python.exe"
if not defined AIX_WEB_PYTHON if exist "%~dp0.venv\Scripts\python.exe" set "AIX_WEB_PYTHON=%~dp0.venv\Scripts\python.exe"

if defined AIX_WEB_PYTHON goto :run
where py >nul 2>&1
if not errorlevel 1 (
  set "AIX_WEB_PYTHON=py -3"
  goto :run
)
where python >nul 2>&1
if not errorlevel 1 (
  set "AIX_WEB_PYTHON=python"
  goto :run
)

echo [ERROR] Python was not found.
echo         Install AIX Runtime Core, create .venv, or set AIX_PYTHON.
pause
exit /b 1

:run
echo ================================================================
echo   AIX DramaFactory V2 Web
echo   http://127.0.0.1:7861
echo ================================================================
echo.
start "" http://127.0.0.1:7861/
%AIX_WEB_PYTHON% app.py
pause
exit /b %ERRORLEVEL%
