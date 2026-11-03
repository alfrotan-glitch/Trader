# Task 01 — Entry Quality: Virtual Stop-Loss Re-entry Gate

**Scope: one hypothesis only.** Do not alter the main EA or optimize its thresholds. We are testing a previously identified entry-quality inconsistency in Nyao Scalper v54.0.

## Verified code issue

The normal fresh-entry path is `CheckForTradingSignal -> DirectionSignal -> ComputeEntryScore`; this enforces the direction-specific minimum signal score after consecutive-candle and drawdown threshold adjustments and losing-position score penalties.

The existing `TryVirtualSLReentry` path checks `currentScore >= initialEntryScore * ReentryMinSignalPct`, with a profile value of `0.75`. It checks the usual position, cooldown and trend filters, but **does not enforce `ComputeEntryScore`'s adjusted threshold**. For example, a previous 5.0 score can permit a 3.75 score at re-entry even when the direction requires 5.0.

This is a code-level inconsistency. It does **not** prove that virtual re-entries caused the 2026 historical drawdown.

## Controlled fix

The experimental source `research/entry_quality/nyao_scalper_entry_gate.mq5` adds **one veto** inside `TryVirtualSLReentry`:

```mql5
EntryScore freshReentry;
ComputeEntryScore(posType == POSITION_TYPE_BUY, freshReentry);
if(freshReentry.strength.deadMarket ||
   freshReentry.score < freshReentry.threshold)
    return;
```

The existing 75% re-entry rule remains mandatory too. It uses the existing closed-candle signal scoring when `EnableNewBarEntryOnly=true`. The experimental source prints tester-only `[ENTRY_GATE_REJECT]` or `[ENTRY_GATE_PASS]` lines for interpretation.

The original `nyao_scalper.mq5` is **byte-for-byte unchanged**. The experiment does not alter fresh entries, SL/TP, volume sizing, or exit logic; automated tests reconstruct the original by removing only this new gate and the tester logs.

## The fixed 0.01-lot trial inputs

`research/entry_quality/Trader_ENTRY_GATE_FIXED001.set` contains the same **172 input values** as the user's independently run fixed-lot Strategy Tester report (Jan 1–Nov 2, 2026, XAUUSD@ M5):

- `RiskPerTradePct=0.0`, `EnableDynamicLots=false`, `BaseLotSize=0.01`
- `MaxLotSize=0.02`, `MaxRiskPerTradePct=1.0`, `MaxOpenOrders=1`
- `EnableHedgeChain=false`, `EnableVirtualSLReentry=true`, `ReentryRespectsNewBarGate=false`
- Every other input is copied unmodified from the original vendor profile.

The last historical fixed-lot **baseline** had **940 trades, +$981.55 net, PF 1.14, 17.87% max Equity drawdown** on a $3,000 simulated deposit. These are historical, not prospective results.

## One-click compile only (no automatic MT5 startup)

1. Run the normal MT5 application manually once and verify the desired WMMarkets **DEMO** account is connected.
2. From an up-to-date copy of Trader, double-click `INSTALL_ENTRY_QUALITY_TRIAL.bat`.
3. It verifies SHA-256 of the unchanged original EA, experimental EA, and pinned `.set` profile; selects the one unambiguous installed MetaEditor + MT5 data folder; backs up any old experimental files; installs the trial in `MQL5/Experts/TraderResearch`; compiles the trial using MetaEditor; and writes a checksum receipt in `local_runs/entry_quality`.
4. It **does not launch MT5, attach an EA to a chart, run a test or send an order**. It never replaces `MQL5/Experts/Trader/nyao_scalper.ex5`.

If several terminals are registered and selection is ambiguous, it fails closed. Advanced command with an explicit terminal data folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\install_entry_quality_trial.ps1 -DataFolder "C:\Users\Forotan\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
```

## Compare baseline and trial in the *manual* Strategy Tester

Open the existing DEMO MT5 **manually**. Use `Ctrl+R` and configure exactly:

| Setting | Value |
| --- | --- |
| Expert (baseline) | `Trader\\nyao_scalper` |
| Expert (trial) | `TraderResearch\\nyao_scalper_entry_gate` |
| Symbol | `XAUUSD@` |
| Period | `M5` |
| Date | `2026.01.01` – `2026.11.02` |
| Modeling | Every tick based on real ticks |
| Deposit | USD 3,000 |
| Leverage | 1:100 |
| Forward | No |
| Optimization | Disabled |
| Inputs for BOTH | Load the identical `Trader_ENTRY_GATE_FIXED001.set` |

Save separate complete reports and Strategy Tester Journals. In the trial Journal, locate `[ENTRY_GATE_REJECT]` to count rejected marginal re-entry attempts and `[ENTRY_GATE_PASS]` to identify re-entries which still met the new gate. **A tester-only PASS log is not itself proof that OrderSend filled**.

Compare number of trades, matching entries, buy/sell breakdown, net return, PF, equity DD, monthly consistency and performance with the best ten winners removed. If the results are identical or there are no rejected re-entries, the hypothesis did not explain the 2026 result.

## Decision rules

- Any difference from the original 2026 report is **diagnostic** only because the hypothesis was selected after inspecting this very period.
- No optimization or parameter search is allowed in this task. Keep exactly one change.
- A higher historical Win Rate alone is insufficient; the primary goal is better after-cost expectancy and PF without worse drawdown, verified on future DEMO data.
- Do not trade REAL. The source is research-only until a genuinely unseen forward evaluation and broker execution audit succeed.

Original author/source: Elriz Wiraswara, BSD-3-Clause license, `nyao_scalper.mq5` at repository root.
