@echo off
rem ============================================================
rem  LocalAssitent Web UI - launcher (uvicorn + websocket open)
rem  Usage: run_ui.bat [port] [--no-browser]
rem  Default: 127.0.0.1:8080, browser opens automatically
rem  Port 8000 is in use -> switched default to 8080
rem ============================================================
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    py run_ui.py
) else (
    py run_ui.py --port %~1 %~2 %~3
)

if errorlevel 1 (
    echo.
    echo [ERROR] Web UI failed to start (code %errorlevel%).
    pause
)
endlocal