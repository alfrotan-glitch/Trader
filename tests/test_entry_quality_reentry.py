"""A/B isolation contract for Nyao's entry-quality virtual SL re-entry experiment.

Proves source equivalence EXCEPT the intended gate and tester diagnostics.
This is NOT a MetaEditor compilation or trading-profit test.
"""
from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "nyao_scalper.mq5"
TRIAL = ROOT / "research" / "entry_quality" / "nyao_scalper_entry_gate.mq5"
PRESET = ROOT / "research" / "entry_quality" / "Trader_ENTRY_GATE_FIXED001.set"
VENDOR_PRESET = ROOT / "settings" / "xauusd-default.set"

REJECT_GATE = """    // ENTRY-QUALITY RESEARCH VARIANT (not a claim of profitable edge):
    // A virtual-stop re-entry must meet the same closed-bar, direction-specific
    // adjusted minimum signal score as a NEW entry. The original 75% of initial
    // score condition still applies below; this adds one independent veto.
    // No additional changes to fresh entries, exits, SL/TP or position sizing.
    EntryScore freshReentry;
    ComputeEntryScore(posType == POSITION_TYPE_BUY, freshReentry);
    if(freshReentry.strength.deadMarket || freshReentry.score < freshReentry.threshold)
    {
        if(MQLInfoInteger(MQL_TESTER))
            PrintFormat("[ENTRY_GATE_REJECT] %s closed_score=%.3f need=%.3f current=%.3f original=%.3f",
                        posType == POSITION_TYPE_BUY ? "BUY" : "SELL",
                        freshReentry.score, freshReentry.threshold,
                        strength.finalScore, initialScore);
        return;
    }

"""
PASS_LOG = """        if(MQLInfoInteger(MQL_TESTER))
            PrintFormat("[ENTRY_GATE_PASS] %s closed_score=%.3f need=%.3f current=%.3f initial=%.3f",
                        posType == POSITION_TYPE_BUY ? "BUY" : "SELL",
                        freshReentry.score, freshReentry.threshold,
                        strength.finalScore, initialScore);

"""


def parse_profile(data: str) -> dict[str, str]:
    pairs = re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)=([^\r\n]*)$", data)
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise AssertionError("Duplicate profile keys")
    return dict(pairs)


class TestEntryQualityReentry(unittest.TestCase):
    def test_main_nyao_is_still_the_exact_upstream_file(self):
        self.assertEqual(
            hashlib.sha256(BASE.read_bytes()).hexdigest(),
            "91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837",
        )

    def test_research_variant_does_not_modify_any_other_trading_logic(self):
        base = BASE.read_text(encoding="utf-8")
        variant = TRIAL.read_text(encoding="utf-8")
        self.assertEqual(
            hashlib.sha256(TRIAL.read_bytes()).hexdigest(),
            "ebda1ba5954d9ea6b0ffcd6f73d734adba13b140cb61bcc28e65e5591c221305",
        )
        self.assertEqual(variant.count(REJECT_GATE), 1)
        self.assertEqual(variant.count(PASS_LOG), 1)
        self.assertEqual(variant.replace(REJECT_GATE, "").replace(PASS_LOG, ""), base)

    def test_guard_is_on_only_for_virtual_reentries(self):
        trial = TRIAL.read_text(encoding="utf-8")
        start = trial.index("void TryVirtualSLReentry(")
        end = trial.index("\nint CountLosingPositions()", start)
        body = trial[start:end]
        self.assertIn("ComputeEntryScore(posType == POSITION_TYPE_BUY, freshReentry);", body)
        self.assertIn("freshReentry.score < freshReentry.threshold", body)
        self.assertIn("strength.finalScore >= minReentryScore", body)
        self.assertLess(body.index("freshReentry.score < freshReentry.threshold"), body.index("OpenPosition(orderType, strength.finalScore)"))
        self.assertIn("if(MQLInfoInteger(MQL_TESTER))", body)

    def test_preset_is_user_report_not_vendor_default(self):
        baseline = parse_profile(VENDOR_PRESET.read_text(encoding="utf-8"))
        trial = parse_profile(PRESET.read_text(encoding="utf-8"))
        self.assertEqual(len(baseline), 172)
        self.assertEqual(len(trial), 172)
        self.assertEqual(set(baseline), set(trial))
        diff = {k: (baseline[k], trial[k]) for k in baseline if baseline[k] != trial[k]}
        self.assertEqual(diff, {
            "MaxOpenOrders": ("2", "1"),
            "RiskPerTradePct": ("1.25", "0.0"),
            "MaxRiskPerTradePct": ("5.0", "1.0"),
            "MaxLotSize": ("0.05", "0.02"),
        })
        self.assertEqual(trial["EnableHedgeChain"], "false")
        self.assertEqual(trial["EnableDynamicLots"], "false")
        self.assertEqual(trial["BaseLotSize"], "0.01")
        self.assertEqual(trial["EnableVirtualSLReentry"], "true")
        self.assertEqual(trial["ReentryRespectsNewBarGate"], "false")

    def test_trial_compiler_script_is_safe_and_independent(self):
        launcher = (ROOT / "INSTALL_ENTRY_QUALITY_TRIAL.bat").read_text(encoding="utf-8")
        install = (ROOT / "tools" / "install_entry_quality_trial.ps1").read_text(encoding="utf-8")
        self.assertIn("install_entry_quality_trial.ps1", launcher)
        self.assertIn("-File", launcher)
        self.assertIn("[switch]$VerifyOnly", install)
        self.assertIn("Assert-Hash $variant 'variant'", install)
        self.assertIn("Assert-Hash $original 'original'", install)
        self.assertIn("Assert-Hash $preset 'preset'", install)
        self.assertIn("metaeditor64.exe", install)
        self.assertIn("Start-Process -FilePath $terminal.Editor", install)
        self.assertNotIn("Start-Process -FilePath $terminal.Terminal", install)
        self.assertNotIn("OrderSend(", install)
        self.assertNotIn("Stop-Process", install)
        self.assertNotIn("-LaunchTester", launcher)
        self.assertNotIn("AlgoTrading = true", install)


if __name__ == "__main__":
    unittest.main()
