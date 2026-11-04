@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ===============================================================
echo    NYAO STOP RECOVERY - ONE-CLICK DEMO MT5 RESEARCH
echo    Auto compile ^> 100%% real-tick backtest ^> verify ^> ZIP
echo ===============================================================
echo REAL TRADING IS NOT ENABLED. Original EA is unchanged.
echo.
where py >nul 2>&1
if errorlevel 1 (
    echo STOP: Python launcher not found. Install Python 3 and try again.
    exit /b 2
)
py -3 "%~dp0tools\auto_nyao_stop_recovery.py" %*
set "EXITCODE=%ERRORLEVEL%"
echo.
if "%EXITCODE%"=="0" (
    echo PASS: Evidence ZIP created and reconciled. Upload it to ChatGPT.
) else (
    echo ATTENTION: Run failed or evidence incomplete.
    echo A failure ZIP is normally created too - upload it for diagnosis.
)
echo.
exit /b %EXITCODE%
