@echo off
echo ==============================================
echo  SHUTTING DOWN J.A.R.V.I.S.
echo ==============================================
echo.

echo Terminating Local Web Agent (local_agent.py)...
taskkill /F /FI "WINDOWTITLE eq JARVIS Local Agent*" /T >nul 2>&1

echo Terminating Desktop Voice Assistant (jarvis.py)...
taskkill /F /FI "WINDOWTITLE eq JARVIS Desktop*" /T >nul 2>&1

:: Also kill any stray python instances running these specific scripts
for /f "tokens=2" %%i in ('wmic process where "name='python.exe' and commandline like '%%local_agent.py%%'" get processid ^| findstr [0-9]') do taskkill /F /PID %%i >nul 2>&1
for /f "tokens=2" %%i in ('wmic process where "name='python.exe' and commandline like '%%jarvis.py%%'" get processid ^| findstr [0-9]') do taskkill /F /PID %%i >nul 2>&1

echo.
echo All Jarvis systems have been safely shut down.
echo.
pause
