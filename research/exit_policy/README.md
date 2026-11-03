# Exit-policy audit — checkpoint vs broker take profit (single-variable A/B)

**Status: original diagnostic report PASS at 718 / +USD 1,212.42; fixed-TP alternative REGISTERED, not yet tested. LIVE LOCKED.**

## Evidence from user-supplied real-tick Strategy Tester report

Full source: `ReportTester-20282400.html` and matching `ReportTester-20282400.xlsx`, WMMarkets-Demo build 6230, XAUUSD@ M5, Jan 1 to Nov 2 2026, 100% real ticks, 68,054,566 ticks, initial USD 3000, leverage 1:100, risk sizing off, fixed 0.01 lots.

- **718** positions, **1,436** entry/exit deals, **+USD 1,212.42**, PF **1.24**, equity max DD **14.71%**, win rate **42.48%**.
- Original diagnostic EA has exact historical parity with the previous `MinEfficiencyToTrade=0.15` control: 718 / +USD 1,212.42.
- `EnableTakeProfit=true` + `TPInputType=2` + `TPValue=20000` + `EnableCheckpointExit=true` + `EnableRiskReward=false` + `EnableTrailing=false`.
- In **all 718 entry orders**, the broker-side `T/P` field was blank. This is intentional: `OpenPosition()` explicitly sends `request.tp` only with `!EnableCheckpointExit`. `InitCheckpoint` uses the **20,000-point TP distance as a virtual checkpoint**.
- Of **718 closing deals**, **672** comments begin `sl` (**293 positive-net, 371 negative-net, 8 zero-net; together +USD 1,539.83**), **45** comments are blank (**3 positive, 42 negative; together -USD 364.36**), and **one** is `end of test` (**+USD 36.95**). Broker-side `tp` exits = **zero by design**.
- Out of 672 `sl` exits, 293 were profitable because the SL could have been moved to a profit-locking price; the label `sl` is **not an indicator of loss**.
- **96** exits made at least **+USD 20**, aggregating **+USD 4,257.89**. This is **66.83% of gross winning trades' USD 6,371.21**; such runners represent **13.37% of all positions**. If hypothetically *only those realized wins* had been capped at USD 20, their contribution would fall by about **USD 2,337.89**. That arithmetic is **NOT a counterfactual backtest**: other previously losing trades may have touched +USD 20 before reversing, and earlier TP exits modify all later entry timings. Do not claim this arithmetic proves fixed TP unprofitable.
- The balance graph ends at about USD 4,212.42, but equity drawdowns and short-lived stop slippage are not visible from balance-only chart.
- April 13 01:00:01 SELL stopped five seconds later at a realized -USD 70.92, despite an `sl` comment at a less adverse level. This is a separate tick-execution anomaly; a TP experiment does not cure stop slippage.

## How checkpoint actually works (source audit)

The original root `nyao_scalper.mq5` calculates `GetTPPoints` from TP input. Under `EnableCheckpointExit=true`, it leaves broker TP at zero but arms `cpPrice = entry +/- TP points`. On a favorable checkpoint touch, `ManageCheckpoints` tests `CheckpointHoldMode`: if the score/trend no longer supports holding, market-closes; otherwise advances the next checkpoint and raises a broker SL to lock `CheckpointLockPct` of reached distance. With the observed values, the first favorable checkpoint is approximately 20 gold-price units from entry, and lock at 50% means a theoretical +10 gold-price-unit stop (subject to market price, valid stop levels and slip). The checkpoint trailing rule activates after 50% of checkpoint distance, and break-even lock at 75%. These paths can close winners by the **broker SL**.

Turning checkpoint mode off is not simply \"add TP\" while keeping all existing checkpoint exits. It replaces the complete virtual checkpoint/lock/trailing scheme with a **broker-side fixed TP** (and still retains other unchanged exits such as trend-flip checks). Do not turn both into a purported hybrid without separately specifying precedence and proving deterministic behavior.

## Controlled experiment — exactly one changed input

- **Control (observed)**: `research/fresh_entry/Trader_FRESH_ER015_FIXED001.set` (`EnableCheckpointExit=true`)
- **Trial (new, UNTESTED)**: `research/exit_policy/Trader_EXIT_FIXED_TP20_ER015_FIXED001.set` (`EnableCheckpointExit=false`)
- Both have **172** input values, same EMA/RSI/ATR, `MinEfficiencyToTrade=0.15`, 0.01 fixed lots, exact SL/TP price distance, `MaxOpenOrders=1`, no manual Risk:Reward, and **all other 171 inputs identical**.

This is **a single fixed scientific contrast**, not a search for the most profitable TP or SL. It is in-sample on the historical data previously reviewed, and cannot validate a future edge.

### Windows manual MT5 Strategy Tester instructions

1. In the local `Trader` checkout, `git pull --ff-only origin main`.
2. Open **WMMarkets DEMO** MT5 and press Ctrl+R. Select the **original** `Trader\\nyao_scalper`, **not** the instrumented `TraderResearch\\nyao_scalper_diagnostic` (this compares exit behavior under the original source).
3. Use `XAUUSD@`, M5, dates Jan 1–Nov 2 2026, **Every tick based on real ticks**, deposit USD 3000, leverage 1:100, optimization off, forward off. Ensure same installed original EX5 build as prior control.
4. Under Inputs → Load: `Trader_EXIT_FIXED_TP20_ER015_FIXED001.set` in `Trader\research\exit_policy\`. Verify `EnableCheckpointExit=false`, `MinEfficiencyToTrade=0.15`, `EnableTakeProfit=true`, `TPValue=20000`, `EnableRiskReward=false`, and fixed 0.01 lots.
5. Run the trial manually. Save **full HTML report** and **Journal**. No code is compiled or any broker live orders sent by this `.set` itself.
6. Stop and **reject the comparison** if the report has missing/changed inputs beyond that one switch or a materially different broker tick/MT5 environment.

### Comparison rubric (do not optimize)

Compare net USD, PF, maximum equity DD, max adverse stop execution, win rate, total entries, distributions by time/direction/month, top-10 profit concentration, realized gain/loss ratio, and confirmed count of broker `tp` exits. **A higher win rate alone is not an advantage.** Trading earlier at fixed TP changes sequential entry opportunities; direct cumulative net P&L and risk comparisons are the primary historical answers.

**Decision now: do NOT remove CheckpointExit from trading configuration.** The new fixed-TP `.set` is a separate read-only research profile with no claim of better results. Keep LIVE LOCKED, and require future pre-registered DEMO evidence for generalization. Obtain the separate `NYAO_ENTRY_DIAGNOSTICS.csv` when available for actual per-entry score/MFE/MAE analyses; HTML and Excel alone do not contain all diagnostic fields.
