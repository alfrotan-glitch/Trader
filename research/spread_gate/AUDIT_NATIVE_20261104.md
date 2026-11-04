# 2026-11-04 Native Spread-Cap A/B Audit

**Historical improvement observed, but NOT approved for live or promotion.** LIVE LOCKED.

Evidence: uploaded NYAO_SPREAD_GATE_EVIDENCE_20261104_112021_994.zip. Archive CRC verified, all 14 recorded SHA-256 hashes match, and both native MT5 HTML reports parsed independently. WMMarkets Demo XAUUSD@ M5, 2026-01-01 to 2026-11-02, 100% real ticks, USD 3000 starting balance. Native 171 input fields differ ONLY in MaxSpreadPoints (500 baseline vs 400 trial); both run the same tester-only guarded original EA. Baseline replays 709 / +USD1091.44.

| Metric | Baseline 500 | Trial 400 |
|---|---:|---:|
| Trades | 709 | 705 |
| Net P&L (USD) | +1091.44 | +1148.56 |
| Gross profit | +6295.47 | +6280.17 |
| Gross loss | -5204.03 | -5131.61 |
| Profit factor | 1.21 | 1.22 |
| Equity max DD | 652.83 / 17.63% | 678.10 / 18.33% |
| Balance max DD | 628.09 / 17.06% | 653.36 / 17.76% |
| Winning positions (native) | 304 | 300 |
| Losing positions | 405 | 405 |
| Longest loss streak | 7 | 10 |
| Worst position | -70.92 | -40.27 |

Net gain +57.12 (+5.23% relative to baseline net profit); equity DD is **worse** by USD25.27 / 0.70 percentage points. Profit factor improvement is small and longest loss streak worsens. The gain does NOT validate future profitability.

## Outlier and sequence sensitivity

On Apr 13, 2026, baseline SELL at 01:00:01 closed 01:00:06 for -USD70.92 at executed 4757.26. Trial SELL at 01:01:36 closed 01:02:29 for -USD20.03 at executed 4687.57. This replacement accounts for +USD50.89, **89.09% of the observed +57.12 total net difference**. Excluding the April month, nine-month difference is only +USD6.23. Observed replacement is not a controlled per-trade causal effect.

Matching entries using timestamp, direction and fill shows 647 identical complete trades, 62 baseline-only and 58 trial-only/shifted entries, all shared entries with identical exits and P&L. It is wrong to imply only four trades changed; the sequence changed much more.

| 2026 month | Baseline USD | Trial USD | Difference USD |
|---|---:|---:|---:|
| Jan | 577.70 | 574.79 | -2.91 |
| Feb | -284.02 | -283.88 | +0.14 |
| Mar | 255.62 | 250.36 | -5.26 |
| Apr | -175.65 | -124.76 | +50.89 |
| May | 63.83 | 63.83 | 0 |
| Jun | 408.95 | 391.60 | -17.35 |
| Jul | -49.34 | -29.05 | +20.29 |
| Aug | 139.06 | 150.47 | +11.41 |
| Sep | 67.87 | 67.87 | 0 |
| Oct | 87.42 | 87.33 | -0.09 |

Trial wins 4 months, loses 4, ties 2; performance is not broadly improved.

## Decision and next evidence

Reject automatic promotion of spread 400. Keep baseline as canonical; preserve trial as a preregistered DEMO forward candidate from Nov 4, 2026 broker time onward. No further in-sample parameter sweep or invented counterfactual. Require future independent after-cost equity/DD, profit factor, slip/gap stress and stable risk before discussing any live deployment. A USD 3000 simulation does not validate 0.01 lot risk on a USD 100-200 account.

Post-audit source change removes a Python return-from-finally warning and adds a drawdown risk note to the branch runner. It has NOT been natively rerun after this source-only update.
