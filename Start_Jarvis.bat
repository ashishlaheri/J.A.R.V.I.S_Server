@echo off
echo ==============================================
echo  J.A.R.V.I.S. DUAL SYSTEM LAUNCHER
echo ==============================================
echo.

:: Get current directory
set "SCRIPT_DIR=%~dp0"

echo [1/2] Starting Local Web Agent (Background)...
start "JARVIS Local Agent" /min cmd /c "cd /d "%SCRIPT_DIR%agent" && python local_agent.py"

echo [2/2] Starting Desktop Voice Assistant (Foreground)...
start "JARVIS Desktop" cmd /k "cd /d "%SCRIPT_DIR%" && python jarvis.py"

echo.
echo Both systems are now online!
echo You can use your phone/web UI, AND speak to Jarvis on your PC.
echo.
echo To safely close everything, run Stop_Jarvis.bat
echo.
pause
