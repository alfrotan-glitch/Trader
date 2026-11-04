# Preregistered NYAO future-period replay and stop-execution forensics

## Scope and frozen hypothesis

- **Preregistration:** committed before the first unseen day **2026-11-05**; the 2026 historical evidence used to choose this trial is **not** out-of-sample.
- **Population:** WMMarkets DEMO, XAUUSD@ M5, 100% real ticks, two isolated native MT5 Strategy Tester replays on same guarded-original EA, $3,000, 1:100, fixed lot 0.01.
- **Only trial input delta:** MaxSpreadPoints 500 (control) vs 400 (candidate); frozen source/vendor SHA and frozen original 172-input .set SHA remain enforced.
- **No changing input thresholds after seeing future results; no optimization loops.**
- **FromDate locked:** 2026.11.05. **ToDate automatic:** UTC today minus two complete days; must be >= 30 days from FromDate. Earliest eligible launch by the UTC-day rule: **2026-12-07**. Runs before this fail closed and can package a failure receipt.
- **Data quality:** broker M5 bar coverage checks on both edges, both MT5 native reports explicitly require 100% real-tick History Quality, and reports must show the same exact requested date range. No real broker orders are sent. This is an *unseen-period historical replay*, not a live DEMO forward execution stream.

## Native stop-execution review

The script `research/spread_gate/analyze_stop_slippage.py` reads native MT5 deal rows directly. It inspects SL-tagged **exit** deals, comparing the last requested stop price printed in the exit comment with the actual executed deal price. Directional adverse gap for a closing BUY is fill minus SL; for a closing SELL it is SL minus fill. The output records counts of adverse deviations exceeding 1, 5 and 10 quote-price units and the ten largest cases. It does **not** infer why the gap occurred, estimate counterfactual profit, or assume all SL-tagged closes lost money.

Recalculated on the 2026-11-04 supplied A/B historical ZIP:

| Native metric | Spread 500 | Spread 400 |
|---|---:|---:|
| Completed exits | 709 | 705 |
| SL-tagged exits | 668 | 664 |
| Adverse execution gap > 1 gold quote unit | 43 | 43 |
| Gap > 5 | 9 | 8 |
| Gap > 10 | 4 | 4 |
| Largest adverse gap | 50.92 | 19.90 |

Original 2026-04-13 SELL stopped at **4757.26** despite requested stop **4706.34**, an unfavorable difference of **50.92 XAUUSD quote-price units**. The candidate skipped/shifted this one anomalous trade, but both variants still show four SL-exit gaps above ten units. The historical net gain +USD57.12 and worse max equity drawdown 17.63% -> 18.33% mean **do not promote**.

## Minimum evidence before any trading decision

The first 30-day batch is **only an initial readout**. No auto promotion, even if profitable. For a stronger provisional result, require at least **8 complete future weeks**, >= **100 completed positions per variant**, positive after-cost edge, trial net P&L above baseline, stable profit factor, and *no material worsening* in equity drawdown or extreme stop execution. Review the results by subperiod and without the largest one or two trades. Overlapping cumulative reruns are **not independent tests**. Any performance comparison on a small sample is inconclusive, not approval.

A $3,000 demo fixed 0.01-lot result does not authorize trading a $100–200 real account: minimum lot size can produce excessive stop risk and broker gaps can multiply it. **LIVE LOCKED.**

## One-click Windows use

After **2026-12-07 UTC** (and only when enough broker history exists):

```powershell
cd "$env:USERPROFILE\Trader"
git fetch origin research/spread-gate-ab-20261104
git switch research/spread-gate-ab-20261104
git pull --ff-only origin research/spread-gate-ab-20261104
.\RUN_NYAO_FUTURE_REPLAY.bat
```

The two native HTMLs, source/preset hashes, dynamic period, out-of-sample comparison, stop execution forensics and limitations are included in one evidence ZIP; upload it for independent review. A REAL or unknown broker account, open positions/orders, unsafe terminal condition, changed source hash, bad native report, early date, insufficient broker history or mismatched input profile blocks execution.

**Note:** source-level tests and CI cannot substitute for the next Windows MT5 native replay, which cannot be run on future prices on Nov 4. The source fix that removed the old 'return in finally' warning was not independently natively rerun.
