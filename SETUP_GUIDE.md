# Trader — Windows one-click setup

This repository mirrors the original Nyao Scalper MT5 project (pinned revision `cf70e9e7f77a77d25554c60d66c44b1b39dbb396`) and adds a deliberately small, separate Windows installation wrapper.

The original BSD-3-Clause `LICENSE`, copyright notices, `nyao_scalper.mq5`, `nyao_straddle.mq5` and the vendor reports remain the upstream author's work, not original work by the Trader repository.

## What to click

1. Install and open the intended **WMMarkets MetaTrader 5** terminal once so its registered data folder is discoverable. No new broker login is created by these scripts.
2. Download this repository with **Code → Download ZIP** and extract it, or clone it with Git.
3. Double-click **`ONE_CLICK_SETUP.bat`** on Windows.
4. The launcher checks the exact vendor source SHA-256, identifies a single MT5 installation/data folder, backs up any previously installed Trader EA, copies the source into `MQL5/Experts/Trader`, compiles it using that terminal's `metaeditor64.exe`, checks the fresh `.ex5`, and writes a reproducible `M5` Strategy Tester preset, `tester.ini`, a source/EX5 checksum receipt and a local run folder.
5. The installer **does not open a trading chart, enable Algo Trading, send broker orders, or automatically attach the EA**.

If there are multiple MT5 installations and none can be selected unambiguously, the installer **fails closed** rather than choosing a random account. This is intentional. Advanced invocation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\setup_windows.ps1 -TerminalPath "C:\Path\To\terminal64.exe" -DataFolder "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\HASH"
```

## Optional simulated backtest

After setup, double-click `RUN_TESTER.bat` **only when the intended terminal is DEMO-only and no trading EAs could resume on launch**. It requires typing `DEMO` and refuses to start a second copy of an already running terminal.

The generated tester configuration uses `XAUUSD@`, `M5`, `Model=4` (real ticks), `Deposit=3000`, `Optimization=0`, `UseCloud=0`, a modified research profile with 1% maximum per-trade nominal risk, one open order, hedge-chain disabled, stops enabled, and max lot 0.02. The exact broker contract and a complete real-tick history must still be verified locally.

The test profile **differs from the vendor's original preset**. Do not compare its result directly to claimed original-vendor historical returns. A test without data or with zero trades does not prove an edge. Past backtests, even real-tick tests, cannot establish future profits.

**Important:** Opening a preconfigured MT5 terminal could also restore previously saved charts and EAs. That is why automatic terminal launch is intentionally an explicit, second-step DEMO action rather than part of unattended installation.

## Safety

- The Nyao Scalper MQL5 source itself can submit broker orders when manually attached and Algo Trading is enabled. The Trader installer never enables those capabilities.
- Never attach this EA to a REAL account without independent cost, slippage, contract-size, and forward validation. Neither this integration nor the vendor's reports constitute profitable-edge validation.
- This package does **not** include compiled EX5 files, broker passwords, or a remote execution service.
- Two EAs are present upstream; **only `nyao_scalper.mq5` is compiled by default**. `nyao_straddle.mq5` is left untouched.
- Under `local_runs/`, every run retains a separate configuration and receipt. This folder is ignored by Git.
- The one-click installer validates an exact SHA-256 for `nyao_scalper.mq5`. Replacing or editing the source needs a deliberate code review and checksum change.

Original project: https://github.com/elrizwiraswara/nyao_scalper_mt5

## Attribution

Copyright (c) 2026 Elriz Wiraswara. Source distributed under the upstream BSD-3-Clause license in `LICENSE`. No endorsement by the original author is implied.
