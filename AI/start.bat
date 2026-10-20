@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Running install.bat first...
    call install.bat
    if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
)

echo [START] Starting VoiceNPC AI Server (Press Ctrl+C to stop)...
".venv\Scripts\python.exe" server.py
