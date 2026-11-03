@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo =====================================================
echo   TRADER - SAFE MT5 DIAGNOSTIC (NO AUTO-LAUNCH)
echo =====================================================
echo Previous automatic tester startup hung or exited on this terminal.
echo The test log reported: not synchronized with trade server,
echo cannot select symbol in market watch.
echo This command ONLY examines logs and Windows crash events.
echo It does not run any broker process or send orders.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\diagnose_mt5.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Diagnostic could not fully complete.
echo Before further tests manually open a DEMO MT5 terminal,
echo ensure the broker is connected and XAUUSD@ exists in Market Watch.
echo Use Ctrl+R to conduct a short manual Strategy Tester run.
echo Do NOT attach this EA to a trading chart.
echo.
pause
exit /b %RESULT%
