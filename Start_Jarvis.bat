@echo off
title J.A.R.V.I.S. Launcher
echo ================================================
echo   J.A.R.V.I.S. DUAL SYSTEM LAUNCHER
echo ================================================
echo.

:: Get current directory (handles spaces in paths)
set "JARVIS_DIR=%~dp0"

:: Check Python is available
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Install Python from https://python.org
    pause
    exit /b 1
)

:: Check agent/.env exists
if not exist "%JARVIS_DIR%agent\.env" (
    echo [WARNING] agent\.env not found. Local agent may not connect.
    echo           Copy agent\.env.example to agent\.env and fill in your token.
    echo.
)

echo [1/2] Starting Local Web Agent (Background)...
start "JARVIS-LocalAgent" /min cmd /c "cd /d "%JARVIS_DIR%agent" & python local_agent.py"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to start Local Agent.
) else (
    echo       OK - Local Agent started.
)

:: Small delay so the two processes don't fight over resources
timeout /t 3 /nobreak >nul

echo [2/2] Starting Desktop Voice Assistant...
start "JARVIS-Desktop" cmd /k "cd /d "%JARVIS_DIR%" & python jarvis.py"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to start Desktop Jarvis.
) else (
    echo       OK - Desktop Jarvis started.
)

echo.
echo ================================================
echo   Both systems are now online!
echo   - Phone/Web UI: control your PC remotely
echo   - Desktop: say "Hey Jarvis" to talk
echo.
echo   To stop everything: run Stop_Jarvis.bat
echo ================================================
echo.
pause
