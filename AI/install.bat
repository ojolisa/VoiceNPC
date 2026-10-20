@echo off
cd /d "%~dp0"

echo [SETUP] Creating isolated Python virtual environment in .venv...
python -m venv .venv
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create virtual environment. Ensure Python is installed.
    pause
    exit /b 1
)

echo [SETUP] Installing required packages into .venv (LiveKit, Cartesia, Gemini)...
".venv\Scripts\pip.exe" install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

if not exist ".env" (
    copy .env.example .env >nul
    echo [SETUP] Created .env file. Please open AI\.env and verify your GEMINI_API_KEY and CARTESIA_API_KEY.
)

echo.
echo [SUCCESS] Virtual environment ready!
echo You can now run start.bat to launch the LiveKit Voice Agent server.
pause
