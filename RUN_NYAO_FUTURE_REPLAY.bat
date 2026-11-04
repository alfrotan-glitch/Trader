@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ==========================================================
echo     NYAO - PREREGISTERED FUTURE-PERIOD COMPARISON
echo     Nov 05 2026 onward. BASE spread 500 vs TRIAL 400.
echo ==========================================================
echo DEMO ONLY - Tester-only original EA; LIVE LOCKED.
echo This is HISTORICAL REPLAY of unseen future data, NOT
echo real-time DEMO forward order execution.
echo It refuses to run until 30 full UTC days plus 2 buffer days
echo have elapsed. No source changes or real orders.
echo.
py -3 "%~dp0tools\auto_nyao_spread_gate.py" --forward %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo Not yet ready, insufficient sample, or a guard failed.
  echo Any available evidence ZIP is in the Trader folder.
) else (
  echo.
  echo Read the evidence ZIP. LIVE remains LOCKED.
)
echo.
pause
exit /b %CODE%
