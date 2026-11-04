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

## Completed 5%-target MT5 native real-tick test — 2026-11-04

**Supplied evidence:** `ReportTester-20282400(3).html`, original `nyao_scalper`, WMMarkets-Demo build 6230, XAUUSD@ M5, Jan 1–Nov 2 2026, 68,054,566 real ticks/59,124 M5 bars, initial USD 3000, 1:100. Frozen control: `ReportTester-20282400.html` with RiskPerTradePct=0, checkpoint on, ER=0.15. Inspected all 172 input values: the only two differences are the coupled `RiskPerTradePct: 0.0 -> 5.0` and `MaxRiskPerTradePct: 1.0 -> 5.0`. All signal, checkpoint and SL settings remain the same.

| Metric | Frozen 0% target / fixed lot control | 5% target / 5% tolerance trial |
| --- | ---: | ---: |
| Completed positions | 718 | 674 |
| **Actual lots across ALL entries** | **0.01** | **0.02** |
| **Actual initial broker stop distance across ALL entries** | **20.00 gold-price units** | **20.00 gold-price units** |
| Net profit USD | +1212.42 | +1493.73 |
| Gross profit USD | +6371.21 | +11732.02 |
| Gross loss USD | -5158.79 | -10238.29 |
| Profit factor | **1.24** | 1.15 |
| Win rate incl break-even trades (MT5) | 42.48% | 42.88% |
| Max equity DD | **USD 544.70 / 14.71%** | USD 1305.66 / 31.00% |
| Worst loss | -70.92 | -141.84 |
| Recovery factor | **2.23** | 1.14 |
| Top-ten winning exits | +916.04 | +1767.83 |
| Net excluding top ten winning exits | **+296.38** | **-274.10** |

The nominal 5% parameter **did not increase SL breathing room at all**. It selected the EA's **0.02 lot maximum on each of 674 entries**. At the fixed 20-gold-unit SL, the planned initial loss is approximately **USD 40 per entry** (roughly 1.33% of USD 3000 start equity), not USD 150/5%. Actual market gaps can exceed this: the identical 2026-04-13 bad exit realized -141.84 at 0.02 vs -70.92 at 0.01. The 5% label is therefore **not** proof of a strict 5% realized loss cap or even actual 5% use.

**Ledger/path comparison:** 594 exact (entry timestamp, direction, fill price) positions are shared between the control and 5% trial; among them, 590 have realized net profit almost exactly 2x due to doubled volume, and four have different exit trajectories. The trial contains 674 vs 718 completed positions due to path-dependent effects. Only 5%-trial top ten winners already exceed total net: **USD 1767.83 of USD 1493.73 (118.35%)**; excluding them produces **-USD 274.10** compared with **+USD 296.38** for the control. This is a concentration/tail-risk warning, **not** proof of a forward result.

**Selected months:** February USD -646.12 trial vs -247.01 control; April -351.28 vs -149.10; October -92.61 vs +107.93. All monthly P&L values based on deal closing times.

**Decision:** `RISK5_HISTORICAL_RISK_ADJUSTED_REJECT__NO_EXTRA_STOP_ROOM__LIVE_LOCKED`. Do NOT promote 5% preset or increase MaxLotSize/SL blindly. Preserve control Checkpoint+ER0.15 and original source. For additional breathing room, quantify stop-out reversals and test an ATR/structure-defined *wider SL combined with reduced lot* at a constant monetary risk, but broker minimum 0.01 lot makes this infeasible on a USD 100–200 account under ordinary 20-unit XAUUSD stops. Also fix the existing symbol-metadata `ApplyRiskSizing` fail-open separately before considering live trading; this audit did not implement code changes. Any improvement needs a prospective frozen DEMO holdout.

## Separate user-requested 5% sizing trial — DEMO ONLY, TESTED HISTORICALLY

Research-only preset: `Trader_RISK5_CAP5_ER015_DEMO_ONLY.set`.

Compared with the existing 0.5%-target research preset, **two coupled inputs** change: `RiskPerTradePct=5.0` and `MaxRiskPerTradePct=5.0`; the latter avoids retaining an inconsistent 1% minimum-lot tolerance. The other **170 inputs** are unchanged. In particular, `SLInputType=2`, `SLValue=20000`, `MinEfficiencyToTrade=0.15`, `EnableCheckpointExit=true`, and `MaxLotSize=0.02` are all **unchanged**. The main EA, previous profiles and tested baseline are untouched.

**This does NOT grant more room before a stop.** Initial stop distance is identical. The chosen 5% target changes the size calculation, subject to the broker minimum `0.01` and EA maximum `0.02` lots. With the observed approx. USD 20 initial stop for 0.01 lots, a USD 200 account has a USD 10 loss budget at 5%; because 0.01 lot already risks roughly USD 20 at the stop, the expected behavior with valid broker metadata is **reject the entry**, not widen the stop. On a USD 3000 account, 5% is USD 150, but the 0.02-lot ceiling limits intended actual volume; 5% is not a promise that every trade risks exactly 5%.

**Do not use this profile on a REAL account.** Five-percent risk per position is aggressive: 10 successive 5% losses compound equity to `(0.95)^10 ≈ 59.9%`, or **40.1% drawdown**, before any slippage. Stop execution can exceed modeled loss (historic USD -70.92 on 0.01 lots); the original code still contains the known fail-open behavior if symbol tick-value metadata is missing. The completed MT5 5% report above shows higher absolute net but much worse drawdown, profit factor, recovery factor and concentration; not approved for live.

To make an entry survive normal market noise requires a separately justified **wider SL based on market volatility or structure**, paired with a **smaller lot** so monetary risk stays constant. On broker minimum 0.01 lot and a USD 100–200 account, these requirements may be impossible simultaneously; using 5% does not cure that constraint.

For manual DEMO research, load the new `.set` into the **original** Nyao EA in Strategy Tester, preserving the same XAUUSD@ M5 real-tick environment. Compare with the frozen baseline. If evaluating USD 200, record both whether entries are blocked and any `[RISK SIZING]` Journal messages. The 5% result is **not** a substitute for the unresolved strict risk-metadata safety fix and unseen forward DEMO test.

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
