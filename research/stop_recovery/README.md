# Nyao v54 — stop timing and post-stop recovery audit (2026-11-04)


## Preferred: ONE-COMMAND Windows automatic research run

**MT5 may initially be closed.** The runner now auto-starts the selected
terminal under an isolated startup configuration with chart Expert Advisors
**disabled** (`[Experts] Enabled=0`, `AllowLiveTrading=0`, `AllowDllImport=0`).
It then verifies the connected broker account is WMMarkets DEMO and has **zero
open positions/pending orders** before doing any test work. If MT5 cannot
restore the saved DEMO login, sign into DEMO manually once and rerun; a REAL
login fails closed and the probe is shut down. An unrelated already-running
MT5 process also blocks auto-start to avoid affecting another terminal.
Then, in Windows PowerShell:

    cd "$env:USERPROFILE\Trader"
    git pull --ff-only origin main
    .\RUN_NYAO_STOP_RECOVERY.bat

The command automatically: verifies the broker connection is DEMO via the
MetaTrader5 Python API; compiles the tester-only instrumented EA; archives
older research CSV evidence; gracefully closes the flat DEMO terminal;
launches the official MT5 command-line Strategy Tester with the original
research preset, XAUUSD@ M5, 2026-01-01 to 2026-11-02, USD 3000, 1:100,
real ticks, optimization OFF; waits for the native HTML report; checks the
frozen 718 trades / +USD 1212.42 parity and 100% real-tick history;
reconciles both CSV files and produces analysis JSON; captures filtered
journal, hashes, report images and compiler evidence; then packages
everything as a single ZIP.

Expected output in the Trader folder:

    NYAO_STOP_RECOVERY_EVIDENCE_YYYYMMDD_HHMMSS_mmm.zip

Upload only that ZIP. There is no manual need to open MT5 Strategy Tester or
copy CSVs. The launcher preserves an existing CSV by archiving it locally.
Previous demo MT5 is reopened where possible.

Preconditions that cannot be bypassed safely: one discoverable MT5
installation, a saved/verified WMMarkets DEMO login (the terminal may be
closed), zero open positions/pending orders, and installed Python 3 plus the
MetaTrader5 package. A REAL/unknown account, missing demo login, open order,
ambiguous terminal or missing data will FAIL CLOSED. No real orders are sent by the runner. The tester-only
research Expert itself refuses to run outside Strategy Tester.

Failure to compile, launch, complete or reconcile produces a FAILURE ZIP
with receipt/logs where possible instead of inventing a valid result.
The package excludes private tester.ini and saved login credentials, though
the native MT5 HTML report may include a DEMO account identifier.
The main vendor EA and 172-input frozen preset are unchanged; LIVE LOCKED.
Github CI validates Python and Windows scripts without opening a live broker.


**Research only. No EA source/config changed. LIVE LOCKED.**
Source: user-supplied WMMarkets-Demo Build 6230 HTML Strategy Tester reports `ReportTester-20282400.html` (0% risk target, 0.01 lot control) and `ReportTester-20282400(3).html` (5% target, 5% tolerance, all 0.02 lot), XAUUSD@ M5 2026-01-01 through 2026-11-02, 100% real ticks, same 68,054,566 underlying test ticks, $3,000 initial deposit, 1:100 leverage.

## Exact source / entry-order facts

- `EnableRiskReward=false`: `RiskRewardRatio=1.5` is **not applied**.
- `SLInputType=2`, `SLValue=20000`: **every one** of the 718 control and 674 5%-trial entry orders has an initial broker SL exactly **20.00 XAUUSD quote-price units** from actual fill, regardless of buy/sell or volume. Confirmed by joining entry deal `order` IDs to order-register `S/L` and calculating direction-aware distance.
- `TPInputType=2`, `TPValue=20000`, `EnableTakeProfit=true`, `EnableCheckpointExit=true`: first **virtual** profit checkpoint also 20 XAUUSD price units; **all** 718/674 initial broker T/P fields are blank. Nominal target-to-stop distance is 1:1, but **effective realized R:R is variable**, due to moved SL, checkpoint hold, early trend-flip close and gaps.
- Typical planned full stop: ~USD 20 at 0.01 lot; ~USD 40 at 0.02 lot, before slippage. April 13 fill at the stop was much worse.

## Loss-making SL exits vs misleading `sl` label

| Measure | Baseline 0.01 lot | 5%-target 0.02 lot trial |
| --- | ---: | ---: |
| Total trades | 718 | 674 |
| All exits labelled `sl` | 672 | 653 |
| True negative-net `sl` exits | **371** | **366** |
| Positive-net `sl` exits due to moved stops | 293 | 279 |
| Near-zero `sl` exits | 8 | 8 |
| Median holding time, negative `sl` exits | 45m 10s | **45m 37s** |
| Negative `sl` exits under 5 minutes | 27 | 25 |
| Negative `sl` exits under 15 minutes | 80 | 78 |
| Negative `sl` exits under 30 minutes | 136 | 131 |
| Negative `sl` exits under 60 minutes | 217 | 209 |

Of 366 negative SL exits in the 5%-target trial, **209 (57.1%)** happened under 60 min and **78 (21.3%)** under 15 min. Approximately **182/366** closed at adverse 19–21 price units, near the original full stop; other stops closed after less adverse movement due to profit-protection/stop-management logic. Labels alone do not reveal complete sequence of stop modifications.

## Post-stop reversal: confirmed LOWER BOUND from later executed deal-price observations

The HTML/Excel reports contain deals but **do not contain continuous tick-by-tick prices after closure**. We therefore extracted all timestamped later `XAUUSD@` executed deal prices (not chart line coordinates), and for each negative `sl` exit sampled only the **correct executable quote side**: later `sell` deal price (BID) for a former BUY, and later `buy` deal price (ASK) for a former SELL. Starting strictly **after** stop-exit time, check for observations on the profit side of the **original entry fill**: 0 = break-even level, +5 = 5 gold-price-unit favorable move, +20 = original checkpoint. Exclude commission/swap from target price definitions; a +5 quote may not equal net +$5 after costs. Identify the **earliest observed qualifying deal print**, which is **not** the unknown exact first tick that crossed the threshold. Count only positive evidence: absence of later matching deal prints does **not** prove absence of a real market rebound.

**5% trial / 366 true loss-making SL exits:**

| Minimum confirmed return observed after exit | Within 1 hour | Within 4 hours | Within 24 hours |
| --- | ---: | ---: | ---: |
| To original entry price or beyond | **28** | **109** | **215** |
| To 5 quote-price units past entry | 25 | 94 | 198 |
| To 20 quote-price units past entry (virtual checkpoint) | **12** | **53** | **156** |

Observation coverage is sparse and not equally distributed across periods; do not extrapolate these lower bounds to actual probabilities of reversals. Do not extrapolate to the market's actual probability of reversals. The corresponding 0.01-lot control, 371 negative `sl` exits, yielded a **lower bound** of 35/117/223 returns to original entry and 14/57/157 returns to +20 within 1h/4h/24h.

**Selected first OBSERVED (not necessarily first actual) rebound examples, in broker-server time:**

1. **2026-04-13 SELL:** entry 4686.34 at 01:00:01; exited 4757.26 at 01:00:06 (**5 sec**, trial -USD 141.84). Later **BUY deal ASK 4660.21 at 01:50:05** (**49m59s after exit**), i.e. below original SELL entry by 26.13 quote-price units. Extreme stop slippage; simply widening a stop is not established as safe or profitable.
2. **2026-03-19 SELL:** entry 4557.98 14:50:00, exited 4577.99 14:55:32 (**5m32s**, -USD 40.02). Later BUY deal ASK **4524.00** at 15:03:38 (**8m06s after stop**), 33.98 quote-price units beyond old entry in favorable direction.
3. **2026-03-23 SELL:** entry 4205.88 at 08:50:00, exited 4225.88 at 08:51:40 (**1m40s**, -USD 40.00). Later BUY deal ASK **4153.12** at 09:09:31 (**17m51s after stop**), 52.76 favorable price units beyond the old entry.
4. **2026-02-03 BUY:** entry 4812.47 at 03:05:00, exited 4792.13 at 03:06:02 (**1m02s**, -USD 40.68). Later SELL deal BID **4835.47** at 03:38:23 (**32m21s after stop**), 23.00 units favorable beyond old entry.

These are measured subsequent executable-price observations, NOT backtested hypothetical holds. A wider stop changes drawdown, margin, trade availability, and checkpoint exits, so it is unsound to claim all such stopped trades would have become profitable if allowed to hold.

## What is still not identifiable from these reports

For each stop, the first actual tick crossing back through entry, maximum favorable excursion within a specified window after the stop, maximum adverse excursion before rebound, full bid/ask spread chronology, or whether a wider stop would have been filled / caused margin issues **cannot** be reconstructed exactly from MT5 deal HTML reports. A **separate read-only tick replay / historical broker tick export with server-time mapping** is required to make per-position `first_return_entry_timestamp`, `first_plus5_timestamp`, `first_plus20_timestamp` and `max_adverse_before_return` reliable. The already built `NYAO_ENTRY_DIAGNOSTICS.csv` samples in-position MFE/MAE but does **not** monitor ticks **after** an exit; it is insufficient for this after-stop question.

**Decision:** keep baseline checkpoint/ER0.15 research setup; do not raise per-trade monetary risk, widen SL arbitrarily, disable stops or add new indicators on this historical sample. First validate after-stop paths on exact ticks and then preregister at most one change to stop placement with volume reduced to hold constant expected monetary risk. Existing symbol-metadata fail-open safety defect must be addressed before live approval.


## NEW: automatic 24-hour post-stop tick replay (research only)

An implementation now exists in the **existing, tester-only** diagnostic sidecar
(research/diagnostics/NYAO_Diagnostics.mqh). This does not change the original
nyao_scalper.mq5 or its 7 diagnostic insertion points. It never sends orders.
A separate post-stop observer watches **every subsequent Strategy Tester tick**
after an explicitly loss-making broker stop (DEAL_REASON_SL + negative net),
up to 24h. It uses liquidation-side Bid for an old BUY and Ask for an old SELL,
with millisecond server timestamps; the closing tick itself is excluded.

Its separate read-only output is NYAO_STOP_RECOVERY_TICKS.csv in MT5 Common/Files:
one row per loss-making broker stop; first tick back to entry, first tick +5
gold-price units in the original trade direction, first tick reaching the
first virtual Checkpoint (+20 with the frozen profile), additional adverse
movement beyond the fill, maximum adverse movement before returning to entry,
best favorable move, observed tick count and coverage status. CENSORED_TEST_END
and NO_TICKS_IN_WINDOW are never represented as 'price did not rebound'.

IMPORTANT: Source changes passed GitHub Python/static tests, but this new
MQL5 header has NOT been compiled in the user's local MetaEditor or
replayed in native MT5. No post-stop tick results exist yet. LIVE LOCKED.

### Windows steps (single manual tester run)

1. In PowerShell, update the repo:

    cd "$env:USERPROFILE\Trader"
    git pull --ff-only origin main

2. The diagnostic deliberately refuses overwriting either CSV. Archive older
   copies in MT5 Common/Files before running again:

    $common = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files"
    foreach ($name in @("NYAO_ENTRY_DIAGNOSTICS.csv", "NYAO_STOP_RECOVERY_TICKS.csv")) {
        $old = Join-Path $common $name
        if (Test-Path -LiteralPath $old) {
            Move-Item -LiteralPath $old -Destination (Join-Path $common ("ARCHIVE_" + (Get-Date -Format yyyyMMdd_HHmmss_fff) + "_" + $name))
        }
    }

3. Compile/install the existing research-only EA:

    .\INSTALL_NYAO_DIAGNOSTICS.bat

   Stop if the installer does not say "PASS: compiled research-only EA".
   It does not start MT5 or place real orders.

4. In WMMarkets DEMO MT5, press Ctrl+R. Select EXPERT:
   TraderResearch\nyao_scalper_diagnostic
   Symbol XAUUSD@; M5; 2026-01-01 through 2026-11-02;
   Every tick based on real ticks; USD 3000; 1:100;
   optimization OFF, forward OFF.
   Load existing tester preset Trader_FRESH_ER015_FIXED001.set:
   RiskPerTradePct=0.0, BaseLotSize=0.01, Checkpoint ON, ER=0.15.
   Do NOT select the previously tested 5% research profile because
   this diagnostic variant intentionally rejects it.

5. Run the Strategy Tester manually. Save full tester HTML report AND Journal.
   The required A/A parity gate is 718 completed positions and
   +USD 1,212.42 net; if it differs, do NOT infer stop recovery probabilities.

6. Analyze the two new CSV files in PowerShell:

    $common = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files"
    py -3 .\research\stop_recovery\analyze_tick_recovery.py (Join-Path $common "NYAO_STOP_RECOVERY_TICKS.csv") --entry-csv (Join-Path $common "NYAO_ENTRY_DIAGNOSTICS.csv") --expected-stops 371 --output ".\local_runs\stop_recovery_report.json"

   The expected count 371 comes from historical SL-comment losses; native
   deal-reason classification is independently verified, not assumed.
   The analyzer rejects duplicate/missing stop rows, malformed timestamps,
   invented crossings and incomplete entry-side diagnostic evidence.
   It reports confirmed returns for 1h/4h/24h and labels censored
   windows separately.

7. Send NYAO_STOP_RECOVERY_TICKS.csv, NYAO_ENTRY_DIAGNOSTICS.csv,
   full MT5 tester report and the JSON analyzer report (plus Journal if
   available) for scrutiny. Only then test ONE potential SL-placement
   improvement with a smaller lot to maintain constant monetary risk.

### Interpretation limits

Tick observation of the original trading strategy is NOT a counterfactual
simulation of keeping the stopped trades open. A wider stop can change
trailing decisions, margins and future entry opportunities. No stop change
is justified until native tick data and the 718-trade parity check pass.
