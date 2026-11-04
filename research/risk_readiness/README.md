# Task 06 — Minimal-risk readiness (ONE input; no new strategy or EA code)

**Decision: RESEARCH ONLY; LIVE LOCKED.** Keep the best historical Checkpoint configuration `MinEfficiencyToTrade=0.15`, `EnableCheckpointExit=true`. Fixed TP was rejected in a controlled historical A/B (net $708.90 vs Checkpoint $1,212.42); optimizing TP is not the task here.

## Completed MT5 backtest A/B audit — 2026-11-04

**User-provided files:** `ReportTester-20282400(2).html` and matching `ReportTester-20282400(1).xlsx`. Both are **RiskPerTradePct=0.5**, not independent baseline and trial reports. Historical control is the earlier uploaded `ReportTester-20282400.html` (`RiskPerTradePct=0.0`). Full raw reports inspected, not only MT5 summary graphs.

**Input validation:** all **172 inputs** match control except `RiskPerTradePct=0.0 -> 0.5`. Both are original `nyao_scalper`, XAUUSD@ M5, WMMarkets-Demo build 6230, USD 3000, 1:100, Jan 1–Nov 2 2026, 100% real ticks (68,054,566 ticks, 59,124 bars), checkpoint enabled and ER 0.15. All position entry orders in BOTH reports are **exactly 0.01 lot**; size did **not** drop in the 0.5% trial.

| Metric | Historical control, risk target OFF | Trial, target 0.5% |
| --- | ---: | ---: |
| Trades | 718 | **709** |
| Net USD | **+1212.42** | +1091.44 |
| Profit factor | **1.24** | 1.21 |
| Winners | 305 (42.48%) | 304 (42.88%) |
| Max equity drawdown | **544.70 / 14.71%** | 652.83 / 17.63% |
| Gross winner USD | **6371.21** | 6295.47 |
| Gross loser USD | **-5158.79** | -5204.03 |
| Expected payoff per trade | **1.69** | 1.54 |
| Largest realized loss | -70.92 | -70.92 |
| Top ten winning trades sum | +916.04 | +892.52 |
| Net excluding ten largest winners | **+296.38** | +198.92 |

The trial had **USD 120.98 less** net and **+2.92 percentage points** worse reported max equity drawdown. The 0.5% setting is **not a strict cap**: the -70.92 loss on Apr 13 remained, including adverse execution beyond the submitted stop. A cap on calculated initial SL loss cannot bound market gaps.

**Ledger identity and first divergence:** the first **142 positions** and their balance paths match exactly. The first mismatched position is the baseline BUY opened **2026-02-09 01:13:35** at 4975.49, closed **02:04:41**, +50.24 USD. The 0.5% trial did not take that entry; its next BUY was **01:30:00**. At the prior matched close, baseline balance was USD **3481.29**, so 1% of balance was about 34.81 USD against an ordinary 0.01-lot / 20-gold-unit planned stop of about USD 20. This suggests the **risk gate and/or broker metadata around that tick must be inspected**, but the HTML and XLSX do **NOT** record the actual sizing decision / tickValue / order rejection; do NOT state an unproven reason.

Across the whole history, **680 of 718** baseline entry keys (time, side, fill price) are identical to trial, with **38** control-only and **29** trial-only entries; four matching entries have different exits. Because exits and exposure alter later opportunities, this is a **path-dependent** difference, not merely nine filtered losing trades.

**Monthly closed-deal net P&L, USD**:

| Month | Control | Trial |
| --- | ---: | ---: |
| Jan | +577.70 | +577.70 |
| Feb | -247.01 | -323.06 |
| Mar | +275.89 | +294.66 |
| Apr | -149.10 | -175.65 |
| May | +158.04 | +63.83 |
| Jun | +352.67 | +408.95 |
| Jul | +15.09 | -17.54 |
| Aug | +73.95 | +107.36 |
| Sep | +47.26 | +47.26 |
| Oct | +107.93 | +107.93 |

**Decision:** `0.5%_LARGE_ACCOUNT_HISTORICAL_NO_IMPROVEMENT__SMALL_ACCOUNT_UNTESTED__LIVE_LOCKED`. Do not promote the risk research preset as a better-performing trading setup. Keep the original Checkpoint+ER0.15 trading *research* baseline unchanged. A trial $200 deposit + full Strategy Tester Journal is needed to test if minimum lot is actually blocked at risk cap. Before any live approval, fix the pre-existing fail-open path in `ApplyRiskSizing` when symbol tick metadata is unavailable; the next edit should be this **single safety issue**, not extra indicators, TP tuning, session gates or complexity. Add regression tests including missing metadata, minimum lot, weekend reopening, and frozen source behavior. Revalidate the baseline after any engine change and complete prospective DEMO testing.

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

This task has a completed **USD 3000 historical A/B**, showing no trading improvement and no lot-size reduction. The independent USD 200 native MT5 gate test, the fail-open metadata fix, validation on prospectively unseen data, and live authorization remain OPEN. Do **not** claim live readiness or added profit.

There is no free or sure way to guarantee positive returns. Prioritize **sustained net expectancy and drawdown under unseen execution**, not increased leverage, parameter proliferation or optimized historical profit.
