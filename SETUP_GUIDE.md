# Trader — Windows setup and MT5 incident safety

This repository contains the original BSD-3-Clause Nyao Scalper MQL5 code (pinned to upstream revision `cf70e9e7f77a77d25554c60d66c44b1b39dbb396`). The main code remains unchanged; attribution and license are retained in `LICENSE`.

## Installation

1. Install the intended MT5 terminal and open it once.
2. Clone this repository and double-click `ONE_CLICK_SETUP.bat`.
3. The setup checks source hashes, finds the MT5 data folder, backs up prior files, installs and compiles the main EA, and prepares a simulated testing preset.
4. This **does not** verify broker login, XAUUSD@ symbol availability or actual Strategy Tester execution. It does not authorize live trading.

If multiple MT5 installations are detected, setup stops rather than guessing. There is no automatic EA chart attachment or Algo Trading activation.

## November 3, 2026 MT5 incident

After a successful compile, the initial one-click auto tester launcher sent `terminal64.exe /config:...` and the user reported the GUI became **Not Responding** and exited. The test journal displayed:

- `not synchronized with trade server`
- `cannot select symbol in market watch`
- `"Trader\nyao_scalper.ex5" X64`

These messages establish failure to synchronize the trading server or select `XAUUSD@` before any confirmed test result. They **do not prove** why Windows displayed Not Responding or whether the process exited due to a crash, a startup failure, or a shutdown setting. Earlier QTS test entries in that journal are unrelated and must not be presented as Nyao results.

### Safety hotfix

- `RUN_TESTER.bat` now performs **read-only diagnostics only**. It does NOT start MT5.
- Direct use of `setup_windows.ps1 -LaunchTester` explicitly fails closed with `UNSAFE_AUTO_LAUNCH_DISABLED`.
- Repeated recompile/backup side effects of the old tester launcher have been removed.
- `tools/diagnose_mt5.ps1` reads current journals and Windows Application error events 1000/1001/1002; it neither starts nor kills MT5.
- The generated INI uses a relative report name and `ShutdownTerminal=0` for future manual use. This does not on its own repair broker synchronization or guarantee a working tester.

## Restore and verify MT5 manually (DEMO only)

1. Open the intended MetaTrader 5 normally (from the Start menu, not the Trader launcher).
2. Confirm it is a **DEMO** login, online and connected to the actual WMMarkets trade server.
3. Open Market Watch with Ctrl+M. Use Symbols to confirm the actual gold instrument name. `XAUUSD@` is assumed by the current research preset; if the connected account only offers a differently suffixed symbol, do **not** blindly replace it or start the existing preset.
4. Press Ctrl+R, choose `Expert Advisors -> Trader -> nyao_scalper`, `XAUUSD@`, M5, and a **short smoke-test window**. Start with 1-minute OHLC to verify the tester can start; once history is synchronized, conduct an independent real-tick run with modeling set to Every tick based on real ticks.
5. Do not attach the EA to a live chart. Do not enable AutoTrading for a real-money account.
6. If MT5 itself again hangs on a normal GUI startup, run `RUN_TESTER.bat` to collect Windows crash event data and investigate a broken installation/profile before retrying any EA.

For a manual diagnosis without any broker activity:

```powershell
cd "$env:USERPROFILE\Trader"
git pull --ff-only origin main
.\RUN_TESTER.bat
```

**No independent profitable edge or live trading authorization has been established.**

Original source: https://github.com/elrizwiraswara/nyao_scalper_mt5
