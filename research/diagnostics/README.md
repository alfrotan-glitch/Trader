# Task 04 — Nyao Entry/Exit Forensics: tester-only instrumented EA

**Scope locked:** diagnostics and data quality only. Do not change strategies, thresholds, lots, stops, exit rules or optimization inputs. This is **not a new profitable strategy** and **LIVE IS LOCKED**.

## Why this exists

The validated historical research preset (`MinEfficiencyToTrade=0.15`, 0.01 fixed lot, 718 trades, +$1,212.42, PF 1.24, 14.71% max equity DD) uses M5 XAUUSD@ on WMMarkets-Demo, Jan 1–Nov 2 2026. Previous full MT5 reports did not include signal strength and spread at the moment of each order, nor tick-sampled MFE/MAE. A severe 2026-04-13 stop fill gap also warrants investigating execution quality before changing strategies.

This separate EA **copies the original Nyao code without changing any of its existing lines** and adds only seven instrumentation insertions. Original `nyao_scalper.mq5` remains hash-pinned and unchanged. Module `NYAO_Diagnostics.mqh` defines the observer, and `analyze_nyao_diagnostics.py` reads the CSV.

## Safety rules and acceptance gates

- Diagnostic EA **refuses initialization outside Strategy Tester** and in optimization. Never attach to any DEMO or REAL chart.
- Diagnostic EA **refuses unsupported settings**: pending limit entries, hedging chain and loss-management must be off; `MinEfficiencyToTrade=0.15`, `RiskPerTradePct=0`, `BaseLotSize=0.01`, `MaxOpenOrders=1` are required.
- This is still the original trading strategy inside an **isolated Strategy Tester**: it simulates orders during manual historical backtests; it never enables live trading or submits broker orders outside the tester.
- The installer **does not launch the terminal**, enable Algo Trading, or send orders; it only copies the source/header/profile, invokes `metaeditor64.exe` and records a compilation receipt.
- File writes use MQL5 `FILE_COMMON` and explicitly **refuse to overwrite either `NYAO_ENTRY_DIAGNOSTICS.csv` or `NYAO_STOP_RECOVERY_TICKS.csv`**. Archive both before another test.
- On missing CSV permissions the diagnostic EA will not initialize. On missing runtime rows or log failures, the analyzer reports **INCOMPLETE_EVIDENCE**, never an invented explanation.
- Original Nyao source: SHA-256 `91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837` (LF Git checkout); Windows CRLF is checked by the installer.
- **Required independent acceptance:** local MetaEditor compilation must succeed, and a manual historical A/A parity test must return exactly **718 completed trades and net +USD 1,212.42** with the frozen 172-input `.set`. Static tests passing alone do **NOT** establish parity.
- No further threshold optimization using already-seen 2026 data is allowed. Forward DEMO dates, source and preset hashes must be frozen before the next prospectively unseen test.

## One-click installation and exact test steps (Windows)

1. Open your actual local `Trader` Git checkout folder and run `git pull --ff-only origin main`. If you do not have that checkout, download the repository ZIP from GitHub and unpack it: `https://github.com/alfrotan-glitch/Trader`.
2. Double-click **`INSTALL_NYAO_DIAGNOSTICS.bat`** in the repository root. This installs in `MQL5\Experts\TraderResearch\` and compiles the separate `nyao_scalper_diagnostic.ex5`.
3. If there is more than one MetaTrader installation, the installer will stop instead of picking one at random; use the `-DataFolder` option of `tools\install_nyao_diagnostics.ps1` to disambiguate.
4. On the desired WMMarkets **DEMO** MT5, open **Strategy Tester** (`Ctrl+R`). Select Expert **`TraderResearch\nyao_scalper_diagnostic`**, symbol **`XAUUSD@`**, period **M5**, dates **2026-01-01 through 2026-11-02**, model **Every tick based on real ticks**, deposit **USD 3000**, leverage **1:100**, **Optimization Off**, **Forward Off**.
5. In **Inputs → Load**, select **`Trader_FRESH_ER015_FIXED001.set`** from the installed Tester profile folder; confirm `MinEfficiencyToTrade=0.15`, `RiskPerTradePct=0.0`, `EnableLimitEntry=false`, `EnableHedgeChain=false`.
6. **Manually** press Start in Strategy Tester and save the full tester report plus Journal. **Do not** enable Algo Trading in a regular chart; this Expert is specifically blocked there.
7. After completion, MT5 menu **File → Open Shared Data Folder → Files**. Locate **`NYAO_ENTRY_DIAGNOSTICS.csv`**, and **archive it** so a subsequent test cannot overwrite it. This location is usually `%APPDATA%\MetaQuotes\Terminal\Common\Files\NYAO_ENTRY_DIAGNOSTICS.csv`. Use the actual common folder shown by MT5.
8. Analyze the downloaded/new CSV in PowerShell from the `Trader` repo root:

```powershell
py -3 .\research\diagnostics\analyze_nyao_diagnostics.py "$env:APPDATA\MetaQuotes\Terminal\Common\Files\NYAO_ENTRY_DIAGNOSTICS.csv" --expected-trades 718 --expected-net 1212.42 --out "$env:USERPROFILE\Downloads\NYAO_DIAGNOSTIC_REPORT.json"
```

If the result says `COMPLETE_READ_ONLY_RECONCILED`, save the 36-field entry CSV, the accompanying post-stop CSV, the full Strategy Tester report and JSON summary for review. Run the new `research/stop_recovery/analyze_tick_recovery.py` to reconcile post-stop watches (instructions in `research/stop_recovery/README.md`). If either result or the native 718-trade / +USD 1,212.42 A/A parity check differs, send the compile log and Tester Journal; do not claim recovered stops or improvements.

## Exact diagnostic fields

One CSV row per tracked closing position (or explicitly unresolved at deinitialization). The 36-column schema includes: ticket, symbol/timeframe, BUY/SELL, entry time and actual fill, volume, entry spread points, original adjusted entry score and threshold, 20-bar closed-candle directional efficiency, closed-bar ATR, four signal components, losing-position penalty and drawdown, last closed-bar time, original SL/TP, actual exit time/fill, **native MQL5 exit-deal reason code**, exit comment, net result including commission/swap from the original EA's position calculation, MFE/MAE in price/points, count of ticks observed, maximum spread during the position, last observed SL, estimated adverse gap versus that **last-observed** SL, and row status.

**MFE/MAE definition:** mark-to-liquidation quotes (BUY at Bid, SELL at Ask), sampled on ticks observed by the EA while the position is open; actual exit fill also considered. These are observational measurements, not an oracle. Interrupted ticks, order-event timing and gaps can affect accuracy. The last observed stop is **not guaranteed to equal the actual stop which triggered** the closing deal, so treat `adverse_sl_gap_price` only as a suspect flag for tick/Journal verification.

## What this does NOT prove

- The original diagnostic variant compiled successfully on the user's Windows MetaEditor (0 errors, 0 warnings, new EX5) on Nov 3. **The new post-stop observer header added Nov 4 has not yet been compiled and rerun locally**; Python/static CI cannot prove MQL5 runtime correctness.
- No actual diagnostic CSV, A/A parity report, signal-cohort evidence, or profitability improvement has yet been produced. The earlier full backtest was performed on the original EA.
- Hold-duration correlations do not show that delaying exits would improve returns.
- The original 36-column entry CSV still does not contain future ticks after a stop. The **new second `NYAO_STOP_RECOVERY_TICKS.csv`** observes such ticks in the very same manual Strategy Tester run, using actual executable Bid/Ask and a 24-hour window; this remains a post-mortem observer, **not a counterfactual widening-stop backtest**. See `research/stop_recovery/README.md`.
- This research should **not** be used to activate REAL trading or justify fixed 0.01 lot on a small $100–$200 account.

## Verification already in CI

`tests/test_nyao_diagnostics.py` checks the upstream SHA, exactly seven append-only code insertions, tester-only initialization/fail-closed settings, all 36 CSV columns, no order actions in the diagnostic module, checksum copy process, and synthetic analyzer reconciliation/failure cases. Windows CI parses the install script and runs `-VerifyOnly` without MetaTrader. This confirms *source and installer integrity*, not MQL5 runtime behavior.

Source author attribution and the original BSD 3-Clause license remain unchanged.
