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
3. Select original `Trader\nyao_scalper`, *not* `TraderResearch\nyao_scalper_entry_gate`.
4. Set `XAUUSD@` / M5 / Jan 1 to Nov 2, 2026 / Every tick based on real ticks / USD 3000 / leverage 1:100 / Optimization Off / Forward No.
5. In **Inputs > Load**, load **control** `C:\Users\Forotan\Trader\research\entry_quality\Trader_ENTRY_GATE_FIXED001.set`, verify `MinEfficiencyToTrade=0.0`, run; save full report + Journal as `NYAO_FRESH_CONTROL`.
6. In the **same Expert and tester** only, choose **Inputs > Load** and load `C:\Users\Forotan\Trader\research\fresh_entry\Trader_FRESH_ER015_FIXED001.set`; verify `MinEfficiencyToTrade=0.15` and fixed lot, run; save full report + Journal as `NYAO_FRESH_ER015`.
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


## Measured 2026 real-tick A/B result — Nov 3, 2026

User-provided native WMMarkets-Demo (MT5 Build 6230) full reports:
- Baseline: `Pasted text(20261103-082232).txt`, `MinEfficiencyToTrade=0.0`
- Experimental: `Pasted text(20261103-093939).txt`, `MinEfficiencyToTrade=0.15`

**Comparison validity:** checked all 172 settings from both reports; the **only difference** is `MinEfficiencyToTrade`. Both reports have XAUUSD@ M5, Jan 1 to Nov 2 2026, 100% real ticks, 59,124 bars, 68,054,566 ticks, $3,000 deposit, 1:100 leverage, exact 0.01 lot on all entries, no optimization.

| Metric | Baseline 0.00 | Trial 0.15 | Change |
| --- | ---: | ---: | ---: |
| Total trades | 940 | 718 | -222 net |
| Net P&L | +$981.55 | +$1,212.42 | +$230.87 |
| Profit factor | 1.14 | 1.24 | +0.10 (rounded) |
| Equity max drawdown | $656.55 / 17.87% | $544.70 / 14.71% | -$111.85 / -3.16 percentage points |
| MT5 winning trades (counts break-even as non-losing) | 407 / 43.30% | 305 / 42.48% | -0.82 percentage points |
| Strict positive trades | 397 | 297 | -100 |
| Strict break-even trades | 10 | 8 | -2 |
| Losing trades | 533 | 413 | -120 |
| Avg net P&L per trade | $1.04 | $1.69 | +$0.65 |
| Recovery factor | 1.50 | 2.23 | +0.73 |
| Sharpe (MT5 reported) | 2.69 | 4.30 | +1.61 |
| Largest loss | -$41.51 | -$70.92 | worse tail loss |
| Top ten winners total | +$927.24 | +$916.04 | -$11.20 |
| Net excluding top ten winners | +$54.31 | +$296.38 | +$242.07 |

Monthly net P&L is based on closing deal time, with swap/commissions included:

| Month 2026 | Base count | Base P&L | Trial count | Trial P&L |
| --- | ---: | ---: | ---: | ---: |
| Jan | 140 | +$542.72 | 92 | +$577.70 |
| Feb | 145 | -$259.41 | 105 | -$247.01 |
| Mar | 161 | +$192.62 | 117 | +$275.89 |
| Apr | 66 | -$69.57 | 60 | -$149.10 |
| May | 58 | +$94.02 | 50 | +$158.04 |
| Jun | 123 | +$424.86 | 93 | +$352.67 |
| Jul | 79 | +$66.87 | 41 | +$15.09 |
| Aug | 79 | +$20.50 | 60 | +$73.95 |
| Sep | 33 | +$9.35 | 44 | +$47.26 |
| Oct | 56 | -$40.41 | 56 | +$107.93 |

**Trade-path caveat:** an exact key of entry timestamp + direction + entry price matches only **275** trades across the variants; all 275 also have identical exit timestamps, exit prices and net profits. Baseline-only entries = 665; trial-only entries = 443. The filter does not merely remove a fixed subset of 222 baseline positions: blocked entries change open-position state, cooldown, subsequent entries, fills and P&L path. Do **not** attribute the $230.87 delta to an identifiable basket of 222 skipped losers.

**Direction breakdown:** trial BUY 300 / +$237.19; trial SELL 418 / +$975.23. Trial Aug–Oct +$229.14 versus baseline -$10.56, but these months were not held out in advance. Trial Apr is worse (-$149.10 versus -$69.57). Trial top ten winners account for 75.55% of total net profit versus baseline 94.47%; profit concentration is improved but still material.

**Transaction cost sensitivity:** the tester incorporates its modeled spread and reports zero commissions; extra *unmodeled* costs of $0.50 per trade would yield +$853.42 trial net, $1.00 per trade +$494.42, and $1.50 +$135.42. These are counterfactual sensitivities, not estimates of real broker costs; do not charge spread a second time.

**Decision:** `HISTORICAL_SCREEN_PASS__FORWARD_DEMO_REQUIRED__LIVE_LOCKED`. Stronger in-sample PF, expectancy, drawdown and profit concentration at the preregistered single 0.15 cutoff; win rate did not rise. These results are **not independent proof of an edge** because the filter was selected after observing the 2026 baseline. The one-parameter experiment should now be **frozen**, not tuned further on the same history. Freeze the `.set` SHA-256, original MQ5/EX5 hash, MT5 build and broker details before a genuinely future-dated demo-only test (e.g., from Nov 4 2026 broker-server time). Keep risk-based sizing disabled only for research; fixed 0.01 lot is NOT a 1% risk limit and is not validated for a $100–$200 account.

**No source changes, no live approval, no broker orders are made by this documentation.**
