@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ============================================================
echo       TRADER - ENTRY QUALITY RE-ENTRY GATE EXPERIMENT
echo       INSTALL AND COMPILE ONLY / NO TERMINAL LAUNCH
echo ============================================================
echo Original Nyao Scalper source and EA will NOT be modified.
echo This experimental variant has NO validated profit improvement.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_entry_quality_trial.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo.
    echo STOP: trial installation failed; review diagnostics.
) else (
    echo.
    echo Trial compiled. Open DEMO MT5 MANUALLY for research testing.
)
echo.
pause
exit /b %CODE%
