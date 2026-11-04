# NYAO Gold — run historical robustness immediately

**NO wait for future data. Research-only, no broker orders. LIVE LOCKED.**

## Single command on Windows

From the existing Trader research branch:

    cd "$env:USERPROFILE\Trader"
    git pull --ff-only origin research/spread-gate-ab-20261104
    .\RUN_NYAO_HISTORICAL_STRESS.bat

This automatically verifies a connected and flat WMMarkets DEMO account, compiles the tester-only guarded ORIGINAL vendor source, uses the exact frozen 172-input preset and a candidate changing only MaxSpreadPoints 500 -> 400, then executes **eight isolated MT5 native 100%-real-tick backtests**, organized as four matched periods:

| Fold | Dates | Runs |
| --- | --- | --- |
| Q1 | 2026-01-01 – 2026-03-31 | baseline and candidate |
| Q2 | 2026-04-01 – 2026-06-30 | baseline and candidate |
| Q3 | 2026-07-01 – 2026-08-31 | baseline and candidate |
| Q4 | 2026-09-01 – 2026-11-02 | baseline and candidate |

Each fold must pass native 171-field input parity (only spread differs), identical period/deposit/symbol/timeframe and 100%-real-tick quality. Exit slippage is audited on actual MT5 deal fills, not invented prices. Partial and completed results are packaged into **one ZIP**, even on a fail-closed test if possible.

## Expert decision rules

Compare net USD, PF, DD, stop-fill gaps and stability in each period, not only total net or win rate. The preset study predeclares a strict DESCRIPTIVE rule: candidate must beat net P&L in at least 3/4 periods, avoid worse equity drawdown in at least 3/4, avoid worse worst execution gap in 3/4, improve pooled PF, improve sum of net P&L on reset-account folds, and avoid >1 percentage point of DD worsening in any fold. A run passing this rule is a **DEMO-chart review candidate only**, never automatic production/live activation.

**Critical limitations:** The candidate was selected after inspecting 2026 trading data; these periods are NOT genuinely unseen. Each fold starts its own USD3000 account and resets strategy state, so summed fold P&L is NOT a realistic continuous account return. No test can prove future profitability, and arbitrarily expanding lot size to raise backtest profits is not an improvement. At least one separate execution evaluation on the current DEMO is needed before any funded deployment. A USD100–200 standard trading account can exceed its entire intended 2% risk budget at the broker minimum 0.01 lot and a 20 quote-unit gold SL; real stop slippage can be worse than planned.

### Previous paths

The future-only retrospective replay script remains in the repo as optional separate evidence. **Do not run RUN_NYAO_FUTURE_REPLAY.bat now.** It legitimately refuses to run before 30+ full days have elapsed. The historical robustness runner has no such time guard.

Research changes do not alter the canonical EA, and the script fails closed on REAL account, open orders, changed source hashes, missing history, report/inputs mismatch or incomplete native reports. Terminal startup is safe and control EA refuses non-tester chart trading.
