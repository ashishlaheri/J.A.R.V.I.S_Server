@echo off
title J.A.R.V.I.S. Shutdown
echo ================================================
echo   SHUTTING DOWN J.A.R.V.I.S.
echo ================================================
echo.

:: Kill by window title (most reliable)
echo Stopping Local Agent...
taskkill /FI "WINDOWTITLE eq JARVIS-LocalAgent*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq JARVIS-Desktop*" /F >nul 2>&1

:: Also kill any python processes running our specific scripts
echo Stopping any remaining Jarvis processes...
for /f "tokens=2 delims=," %%i in ('tasklist /FO CSV /NH ^| findstr /i "python"') do (
    wmic process where "ProcessId=%%~i" get CommandLine 2>nul | findstr /i "local_agent.py jarvis.py" >nul 2>&1 && taskkill /F /PID %%~i >nul 2>&1
)

echo.
echo All J.A.R.V.I.S. systems safely shut down.
echo Your laptop is now running light.
echo.
pause
