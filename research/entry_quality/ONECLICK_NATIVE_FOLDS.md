# One-click Nyao virtual-SL re-entry quality experiment

One specific source-level hypothesis: virtual-stop reentry can reopen at 75% of original score without satisfying regular adjusted minimum entry threshold. Research source adds exactly one veto to virtual re-entries. Ordinary entries, exits, stop placement, lot size and input values stay frozen.

## What runs

1. Confirms WMMarkets DEMO and zero positions/orders. Verifies original vendor source SHA and approved one-change research source SHA and original frozen 172-input research preset.
2. Compiles two isolated **tester-only guarded** Expert variants. Neither can trade on a normal chart. Original EA source/EX5 never replaced.
3. Attempts to reuse previous historical four-period native BASE reports only when the ZIP manifest, original vendor SHA, compiled control EX5 SHA, preset SHA, reports, periods, input count and native trades all reconcile. Otherwise runs both sides fresh.
4. Executes four Q1–Q4 candidate real-tick tests, or all eight if baseline evidence cannot be reused. For each same-date pair, checks exactly the same 171 native EA inputs, XAUUSD@ M5 period, 100% native real tick history quality, 3000 USD initial deposit and complete deal ledgers.
5. Compares native net USD, profit factor, equity drawdown, and executed stop-price slippage across all four windows. No optimizer or parameter grid.

Previous spread-400 experiment FAILED robustness; both variants here retain spread 500 and use fixed 0.01 lots. This studies the known virtual re-entry code inconsistency; no assumption that it increases profits.

## Windows command, ready now

    cd "$env:USERPROFILE\Trader"
    git pull --ff-only origin research/spread-gate-ab-20261104
    .\RUN_NYAO_ENTRY_GATE_TEST.bat

Upload the one NYAO_ENTRY_GATE_EVIDENCE_*.zip file. Keep the prior NYAO_HISTORICAL_STRESS_EVIDENCE ZIP in the Trader folder so its valid baseline reports can be reused.

A historical multi-fold pass is only a candidate for DEMO-chart review, not proof of a live edge or authorization for real money. Each fold resets the trading account and signals. LIVE LOCKED.
