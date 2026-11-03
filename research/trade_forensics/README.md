# Task 03 — Fresh Entry Loss Forensics (read-only)

**Status:** historical diagnosis completed on the real-tick Nyao v54.0 2026 reports. NO strategy parameter change. NO LIVE permission.

## Input provenance and integrity

- Control report: `Pasted text(20261103-082232).txt`, 940 trades, +USD 981.55, 0.00 directional efficiency filter.
- Fresh-entry 0.15 trial: `Pasted text(20261103-093939).txt`, 718 trades, +USD 1,212.42, PF 1.24 and equity max DD 14.71%.
- Parsed every deal as an entry/exit pair and reconciled the trade counts and net P&L to the MT5 report.
- All 172 trial inputs match the control except `MinEfficiencyToTrade=0.15`. In both, entries used 0.01 lot, initial deposit USD 3,000, XAUUSD@ M5, identical real ticks, and WMMarkets-Demo build 6230.
- Exact match of (entry time, side, entry price) = **275** positions. The other trades are path-dependent; an entry filter changes subsequent position state, so do not treat the 222 net reduction as 222 proven avoided losing trades.

## Key results from all 718 completed positions

| Indicator | Observation |
| --- | --- |
| BUY positions | 300, +USD 237.19 |
| SELL positions | 418, +USD 975.23 |
| Completed in under 15 minutes | 114, **-USD 492.84** |
| Completed in 15–60 minutes | 238, **-USD 507.69** |
| Completed in 1–4 hours | 241, +USD 27.44 |
| Completed after 4+ hours | 125, +USD 2,185.51 |
| Exit comment begins `sl` | 672, **+USD 1,539.83** total |
| Exit comment blank or unspecified | 45, **-USD 364.36** total; 42 strictly losing |
| Worst losing streak by USD | 6 consecutive losses totaling **-USD 110.80** |
| Top ten winning exits | +USD 916.04 (75.55% of overall trial net) |
| Net excluding ten biggest winners | +USD 296.38 |

**Important:** The relationship between holding duration and realized returns is *not causal evidence* that forcing trades to stay open longer would raise profit. Profit-taking, stop exits and trade survival determine observed durations. A stop-comment exit can be profitable because trailing/checkpoint stops can move into profit.

## Severe execution anomaly to investigate

The trial's worst observed individual loss:

- **2026-04-13 01:00:01 to 01:00:06 (broker-server clock), SELL, 0.01 lot**.
- Entry at **4686.34**; exit comment is **`sl 4706.34`**.
- Actual exit deal price **4757.26**, **50.92 gold-quote price units** beyond the stop level.
- Realized **-USD 70.92** versus approximately -USD 20.00 if filled exactly at the reported stop.
- This is compatible with a large gap or stop execution slippage. It is **not proof of broker misconduct or a specific root cause** without tick-by-tick market data and Strategy Tester Journal.
- Among 672 exits with an `sl` price comment, 40 closed more than 1 gold-quote price unit beyond that stop in the adverse direction. The count alone does **not** imply unexpected live costs: the tester embeds modeled broker ticks and prices.

**Forensic priority:** inspect native real ticks around 2026-04-13 01:00:00–01:00:10 broker-server time; compare displayed Bid/Ask, actual stop, spread and exit Journal event. This is one testable execution-quality question; do not change SL, entry threshold, holding time or any other input until checked.

## Why the current text report cannot prove signal failure or price reversal

The report contains trade time, side, deal price, lot, realized P&L, and an often-ambiguous exit comment. It lacks entry signal score, actual spread at decision, ATR, 20-bar directional efficiency at entry, HTF EMA displacement, tick-level MFE/MAE, and the complete post-stop price trajectory. Thus it cannot distinguish a poor signal from a correctly identified trend with a badly timed entry or a spread/price jump.

To measure those factors, a **separate diagnostic-only Strategy Tester build** or an offline read of the same broker tick history is required. Never retrofit an assumed cause into a historical trade or tune parameters on 2026 in-sample data.

## Testing and decision

The local offline tool `NYAO_TRADE_FORENSICS.py` was exercised against the two full 2026 reports; it reproduces 718 trades / USD 1,212.42, recognizes exactly one changed input and reports 275 common entry keys. Four synthetic regression tests passed, including a fail-closed rule for overlapping/partial trades without reliable position identifiers. It does not access MT5 or send broker orders.

**Verdict:** `FORENSICALLY_AUDITED_IN_SAMPLE__EXECUTION_ANOMALY_DETECTED__FUTURE_DEMO_REQUIRED__LIVE_LOCKED`.

Keep `MinEfficiencyToTrade=0.15` frozen, rather than optimizing multiple thresholds against already-observed historical months. Protect the original 2026 reports and their setup provenance. A new prospective, preregistered DEMO window is needed to evaluate genuine expected returns and execution risk.
