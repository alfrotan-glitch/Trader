@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ==================================================
echo       TRADER / NYAO SCALPER - ONE CLICK SETUP
echo       INSTALL + COMPILE + PREPARE RESEARCH ONLY
echo ==================================================
echo No live orders will be sent.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup_windows.ps1" %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo Setup stopped. Review the error above.
) else (
  echo.
  echo Setup verified. The EA and test preset are ready.
)
echo.
pause
exit /b %RESULT%
