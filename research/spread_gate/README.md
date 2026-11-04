# Nyao — one-variable entry spread gate (RESEARCH ONLY)

**Status: newly implemented automation; Windows native A/B has NOT run. LIVE LOCKED.**

## Why this candidate

The user-supplied 2026-11-04 ZIP (709 native XAUUSD@ M5 deals, control=diagnostic) has 708 fully closed diagnostic entry rows and one end-of-test exit available in native MT5 HTML (+USD 36.95). Offline, using unchanged observed trades and attaching the final native closing deal, entries with \`entry_spread_points > 40\` account for **45 trades / net -USD 211.43**. All other 664 trades account for +USD 1302.87, compared with +USD 1091.44 overall. This is an *observational subset sum*, **NOT** a counterfactual strategy backtest: skipping an entry changes future trading opportunities and state.

The candidate is preselected once: reduce native \`MaxSpreadPoints=500\` to \`400\` with \`PointInputDigits=3\`. On two-decimal XAUUSD@, \`PointScale()=0.1\`, so its entry cap is 40 broker quote points; boundary at exactly 40 remains allowed. This same-year profile was chosen **after seeing its losses**, so any 2026 improvement is **not independent evidence**. Do not retry other thresholds until prospective data arrive.

## One-click native Strategy Tester paired replay

Windows PowerShell:

\`\`\`powershell
cd "$env:USERPROFILE\Trader"
git pull --ff-only origin main
.\RUN_NYAO_SPREAD_GATE.bat
\`\`\`

The runner verifies WMMarkets DEMO and zero open positions/orders; refuses a REAL account, unsafe terminal ambiguity or changed source/preset hashes; safely starts the terminal when needed. It compiles a **tester-only guarded copy of the unchanged original Nyao EA**, creates isolated run-unique .set profiles with exactly 172 inputs, executes two separate original-EA XAUUSD@ M5 Jan 1–Nov 2 2026 tests using **100% real ticks**, $3000 initial deposit, same tester environment, and verifies both native HTML input ledgers differ in exactly one field. Two native reports, compiler receipt, hashes, execution logs and comparison are packaged in **one ZIP** in \`Trader\`.

It never alters the canonical vendor source, current installed trading EA or normal preset. Private login/tester INI files stay outside the ZIP. MT5 native HTML *may contain a demo account number*. Auto-started MT5 is not reopened in normal chart mode. An existing DEMO terminal is reopened when possible.

Upload the \`NYAO_SPREAD_GATE_EVIDENCE_*.zip\` file. If baseline drifts from the most recent 709/+1091.44 control, its independent same-run A/B remains logged but cannot be compared to older CSVs. Any failure is fail-closed and retains a failure ZIP where feasible.

## Decision

We compare *native* net USD, PF, max equity DD, deal count, worst executed stop and month robustness, with only one input changed. Promote nothing on an in-sample gain. Approve for forward-shadow only after identical other inputs, successful A/B, no worsening of critical risk and a documented choice to freeze the candidate. Require untouched future DEMO data after Nov 4, 2026 with a defined monitoring interval before any live consideration. A drawdown worsened enough to exceed the risk budget rejects the candidate even if net USD increases.

**No promises of profitability. No real trading enabled.**
