@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ===============================================================
echo   NYAO GOLD - VIRTUAL STOP RE-ENTRY QUALITY A/B
echo   Baseline vs one entry threshold consistency fix
echo   4 historical windows, native MT5 real ticks, DEMO ONLY
echo ===============================================================
echo Original NYAO unchanged. No live chart trading or real orders.
echo Cached baseline reports must pass pinned SHA and native validation.
echo If cache is absent, all 8 native reports are generated fresh.
echo.
py -3 "%~dp0tools\auto_nyao_entry_gate_folds.py" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo Research did not reconcile. Inspect evidence ZIP.
) else (
  echo.
  echo Research completed. Profitability NOT approved for live trading.
)
echo.
pause
exit /b %CODE%
