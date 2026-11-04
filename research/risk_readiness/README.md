# Task 06 — Minimal-risk readiness (ONE input; no new strategy or EA code)

**Decision: RESEARCH ONLY; LIVE LOCKED.** Keep the best historical Checkpoint configuration `MinEfficiencyToTrade=0.15`, `EnableCheckpointExit=true`. Fixed TP was rejected in a controlled historical A/B (net $708.90 vs Checkpoint $1,212.42); optimizing TP is not the task here.

## The reason for this one-variable experiment

The successful 718-trade backtest used fixed `BaseLotSize=0.01` on a **$3,000** hypothetical account with `RiskPerTradePct=0.0`. It therefore did **not** enforce a per-trade percent-risk budget. The typical initial broker SL is **20 gold-price units** and on WMMarkets this is approximately **$20 risk for 0.01 lots**, *before gaps or slippage*. The largest realized loss in the historical report was **$70.92** (2026-04-13).

| Account equity | $20 ordinary initial SL as % of equity | $70.92 observed adverse fill as % |
| ---: | ---: | ---: |
| $100 | 20.00% | 70.92% |
| $200 | 10.00% | 35.46% |
| $3,000 | 0.67% | 2.36% |

These figures are illustrative exposure ratios, not promises that losses will be confined to the SL. A small account is not trade-ready solely because a $3,000 backtest earned a net profit.

## One-variable trial: no additional feature and no code changes

**Control:** `research/fresh_entry/Trader_FRESH_ER015_FIXED001.set`

**Trial:** `research/risk_readiness/Trader_RISK05_CAP1_ER015_FIXED001.set`

The only changed `.set` input among all 172 is `RiskPerTradePct=0.0 -> 0.5`. The existing `MaxRiskPerTradePct=1.0` remains unchanged. All entry scoring, checkpoint, hard stops, signals and position count stay exactly as in the control.

The built-in `ApplyRiskSizing` is called **before OrderSend** even when `EnableDynamicLots=false` (separate lot multiplier logic). With functioning tick-value/contract metadata, it targets **0.5% of equity** at the initial SL and can allow the minimum lot to exceed 0.5% but **not** 1.0%; if even the broker min lot would exceed 1%, the entry is skipped. With a $20 normal SL the minimum hypothetical account size for 1% stop-distance budget is about **$2,000**. On a $3,000 starting balance, 0.01-lot exposure is approximately 0.67%, and the code allows that by its existing 1% overbudget tolerance. At $100 or $200 and a 20-unit SL, expected behavior is **no trade**, not tiny 0.01-lot positions pretending to be within budget.

**CRITICAL KNOWN LIMITATIONS:**
1. Stop losses can slip or gap, e.g. the observed -$70.92. The `MaxRiskPerTradePct=1.0` setting calculates *planned initial stop risk*, NOT a guaranteed realized loss.
2. The current upstream `ApplyRiskSizing` still contains a **fail-open path**: if tick value / tick size / metadata cannot be read, `RiskSizedLot` returns -1 and `ApplyRiskSizing` currently returns **true**, leaving the original lot in place. Thus this trial is **NOT fit for REAL trading** even if the expected normal-case gate works. This is a code safety defect to address as one separate single-task source edit after testing, with every hash pin and the diagnostic variant updated. Never describe this research preset as a hard, unconditional risk guarantee.
3. A percent-risk profile changes trade sizes if the deposit grows significantly; a historical 718 / +$1,212.42 replay must be checked for parity rather than assumed unchanged.
4. Profit factor improvement was **NOT** the goal of this risk safety trial and has not been shown.

## Two explicit manual research acceptance tests

First test on **WMMarkets-Demo MT5 Strategy Tester**, using the **original** `nyao_scalper` (not the diagnostic variant) with `XAUUSD@` M5, Jan 1–Nov 2 2026, 100% real ticks, USD 3,000, leverage 1:100, optimization off, and the new trial .set. Require exact `RiskPerTradePct=0.5`, `MaxRiskPerTradePct=1.0`, `MinEfficiencyToTrade=0.15`, and `EnableCheckpointExit=true` in report. Compare trade count, changing volume, net P&L, PF and equity DD with original control. A variance is a **test outcome**, not silently accepted.

Second, **independent and separate TESTER run**, initial deposit **$200** with identical symbol and broker conditions and the same .set, *without real broker orders*. With proper tick metadata and the usual 20-unit SL, entries should be blocked. Inspect MT5 Journal for `[RISK SIZING] No new trades`; if unexpected entries appear, **FAIL**. This diagnostic is not comparable to the $3,000 return figure.

Do not add hourly session filters: the 45 historical entries in the 01:00–01:59 hour yielded +$217.82 overall. Only four Monday entries occurred during 01:00–01:04, net -$67.26 dominated by a single -$70.92; imposing a session filter based on those four observations would be retrospective overfitting, not a demonstrated advantage. Keep the strategy unchanged.

## Outcome/acceptance

This task is complete as a **frozen, single-variable research proposal with CI static verification**. The native MT5 tests, the fail-open metadata fix, validation under prospective unseen broker time and real deployment decision remain OPEN; do **not** claim live readiness or any added profit.

There is no free or sure way to guarantee positive returns. Prioritize **sustained net expectancy and drawdown under unseen execution**, not increased leverage, parameter proliferation or optimized historical profit.
