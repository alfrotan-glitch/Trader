@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo =====================================================
echo    TRADER - OPTIONAL MT5 STRATEGY TESTER (DEMO ONLY)
echo =====================================================
echo This tool NEVER turns on trading itself.
echo Terminal launch may restore previously saved EAs.
echo Make sure your selected WMMarkets terminal is DEMO ONLY.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup_windows.ps1" -LaunchTester %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo STOPPED - check warnings above.
pause
exit /b %RESULT%
