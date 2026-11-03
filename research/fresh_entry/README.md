# Task 02 — Fresh-Entry Directional Efficiency (one variable, no EA edits)

**Status:** Research preset created and CI static checks provided. **NO MT5 backtest has yet been performed on this trial. NO LIVE APPROVAL.**

## Why this hypothesis was selected

Prior Nov 3 2026 analysis showed that the experimental virtual-stop re-entry gate was dormant because `EnableLossManagement=false`. The correct next target is the **actually executed fresh-entry path**.

The original source implements the complete active route:

`CheckForTradingSignal -> BuySignal / SellSignal -> DirectionSignal -> CheckEntryConditions -> EntryConditionsBlock`.

Inside `EntryConditionsBlock`, the **existing** short-term directional-efficiency filter executes only if `MinEfficiencyToTrade > 0`. It calculates:

```
DirectionalEfficiency = max(0, direction * (close[1] - close[21])) /
                       sum(abs(close[k] - close[k+1])) for k=1..20
```

The code fetches **closed bars only** (`CopyClose(..., 1, n+1, ...)`). A value near 0 means the 20-bar net displacement is small or points the wrong way relative to the whole traveled path; near 1 means directional movement is efficient. This is a **fresh-entry gate**, unlike the dormant virtual-stop branch.

The current user's baseline has `MinEfficiencyToTrade=0.0`, so no directional-efficiency filter. This can admit apparent high-score trend signals when the last 20 M5 bars are choppy or have moved in the opposite direction. That is a hypothesis about trade quality, **not** proven from the trade report alone.

## One registered change — not parameter optimization

**Control:** `research/entry_quality/Trader_ENTRY_GATE_FIXED001.set`

**Experiment:** `research/fresh_entry/Trader_FRESH_ER015_FIXED001.set`

Both have 172 input values. **The only difference is**:

| Input | Control | Experiment |
| --- | --- | --- |
| `MinEfficiencyToTrade` | `0.0` | `0.15` |

`RangeFilterPeriod=20` stays unchanged. `0.15` is an **a priori research threshold**, not an optimized or known-to-be-profitable number. No grid search over thresholds is part of this task. This experiment **reuses the original**, unchanged `nyao_scalper.mq5 / nyao_scalper.ex5`, **NOT** `nyao_scalper_entry_gate`.

Frozen common inputs include `RiskPerTradePct=0.0`, `BaseLotSize=0.01`, `EnableDynamicLots=false`, `MaxOpenOrders=1`, `MaxLotSize=0.02`, `DrawdownScope=1`, `EnableLossManagement=false`, `EnableHTFTrendFilter=true`, and all the remaining matching inputs. The experiment's only change is fresh-entry filtering. In this setup the default loss-based 1% sizing is OFF; do not treat 0.01 lots as a 1% risk cap for a small live account.

## Controlled real-tick A/B on Windows (manual; no auto-launch)

1. Pull the repository's current `main`; neither preset compiles nor starts MT5.
2. Open the **WMMarkets DEMO MT5** application manually, choose Strategy Tester (`Ctrl+R`).
3. Select original `Trader\\nyao_scalper`, *not* `TraderResearch\\nyao_scalper_entry_gate`.
4. Set `XAUUSD@` / M5 / Jan 1 to Nov 2, 2026 / Every tick based on real ticks / USD 3000 / leverage 1:100 / Optimization Off / Forward No.
5. In **Inputs > Load**, load **control** `C:\\Users\\Forotan\\Trader\\research\\entry_quality\\Trader_ENTRY_GATE_FIXED001.set`, verify `MinEfficiencyToTrade=0.0`, run; save full report + Journal as `NYAO_FRESH_CONTROL`.
6. In the **same Expert and tester** only, choose **Inputs > Load** and load `C:\\Users\\Forotan\\Trader\\research\\fresh_entry\\Trader_FRESH_ER015_FIXED001.set`; verify `MinEfficiencyToTrade=0.15` and fixed lot, run; save full report + Journal as `NYAO_FRESH_ER015`.
7. Send both reports for a ledger-level comparison. The tester Journal is helpful if enabled, but `EnableLogging=false` means ordinary `LogPrint` filter diagnostics are intentionally muted; **do not change EnableLogging only in one variant**, as that would break the one-variable protocol.

Baseline previously observed: **940 trades, net +$981.55, Profit Factor 1.14, maximum equity drawdown 17.87%, win rate 43.30%**. Those are historical numbers, not an approved forward result.

## Acceptance criteria and what a change would mean

- Required: trial profile is confirmed from the report; 172/172 values align except `MinEfficiencyToTrade`.
- Compare monthly P&L (especially Aug–Oct), long/short, gross winners/losses, count of trades, realized average payoff, PF, recovery factor, equity DD, losing streaks, and profit concentration in the biggest ten winning trades.
- A reduction in trade count alone is **not** proof of better quality. Higher win rate alone is **not** proof of better risk-adjusted profit.
- A trial with materially worse PF and/or DD **fails** the historical screening. An apparent improvement is only **research evidence** because the same history was reviewed before selecting this hypothesis; do not tune 0.15 to maximize it.
- Trades and exits are path dependent: filtering a trade can alter later cooldowns and entry state. Do not claim every difference is a simple sum of rejected baseline trades.
- Only an **unseen future** DEMO test with inputs, exact source version, compile and broker environment preregistered can support a generalization claim. Do not trade REAL.

## Verification

`tests/test_fresh_entry_efficiency.py` asserts: vendor main source unchanged; only one input different; actual fresh-entry call chain contains the filter; and efficiency is calculated on the last 20 **closed** M5 candles.

The presence of code and green CI proves integrity only. It does **not** prove a profitable filter. This task requires the user's native MetaTrader real-tick test to evaluate the hypothesis.
