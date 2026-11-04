@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ================================================================
echo      NYAO GOLD - HISTORICAL ROBUSTNESS / ONE CLICK
echo      Four separate 2026 periods, 2 profiles, 8 real-tick tests
echo ================================================================
echo NO WAIT FOR FUTURE DATA. Only WMMarkets DEMO allowed.
echo Same original guarded tester EA. Live trading NOT enabled.
echo This is retrospective stability research, NOT future profit proof.
echo.
py -3 "%~dp0tools\auto_nyao_historical_robustness.py" --reuse-verified-q1 %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo FAILED CLOSED: see NYAO_HISTORICAL_STRESS_EVIDENCE ZIP.
) else (
  echo.
  echo Historical tests finished. Upload the evidence ZIP for review.
)
echo.
pause
exit /b %CODE%
