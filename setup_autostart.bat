@echo off
REM ═══════════════════════════════════════════════════════════
REM  J.A.R.V.I.S. Local Agent — Auto-Start Setup for Windows
REM  Run this script once to add the local agent to Windows startup
REM ═══════════════════════════════════════════════════════════

echo.
echo   J.A.R.V.I.S. Local Agent — Startup Setup
echo   ==========================================
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "AGENT_DIR=%SCRIPT_DIR%agent"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

REM Create the startup batch file
echo Creating startup shortcut...
(
echo @echo off
echo cd /d "%AGENT_DIR%"
echo start "JARVIS Agent" /min python local_agent.py
) > "%STARTUP_DIR%\jarvis_agent.bat"

echo.
echo   Done! The local agent will now start automatically with Windows.
echo.
echo   Startup script: %STARTUP_DIR%\jarvis_agent.bat
echo.
echo   To remove: delete the file from your Startup folder
echo   To open Startup folder: press Win+R and type "shell:startup"
echo.
echo   Press any key to test the agent now...
pause > nul
cd /d "%AGENT_DIR%"
python local_agent.py
