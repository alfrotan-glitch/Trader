@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ==============================================================
echo     NYAO SPREAD GATE - SINGLE-VARIABLE MT5 A/B RESEARCH
echo     Baseline MaxSpreadPoints 500 vs Trial 400 (same EA)
echo ==============================================================
echo DEMO ONLY. No real trades. Original EA unchanged. LIVE LOCKED.
echo.
py -3 "%~dp0tools\auto_nyao_spread_gate.py" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo STOP: A/B did not validate. See failure evidence ZIP.
) else (
  echo.
  echo Research A/B completed. This DOES NOT approve live trading.
)
echo.
pause
exit /b %CODE%
