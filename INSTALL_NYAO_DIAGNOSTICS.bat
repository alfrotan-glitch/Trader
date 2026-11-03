@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ===============================================================
echo   NYAO SCALPER - TESTER-ONLY DIAGNOSTIC INSTALL AND COMPILE
echo ===============================================================
echo The original EA will not be changed. NO live trading enabled.
echo The diagnostic Expert refuses to start outside Strategy Tester.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_nyao_diagnostics.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo STOP: Compilation or verification failed. Check above message.
) else (
  echo.
  echo Ready for MANUAL MT5 Strategy Tester on a DEMO account.
)
echo.
pause
exit /b %CODE%
