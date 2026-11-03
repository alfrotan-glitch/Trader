"""Single-variable Fresh Entry directional-efficiency experiment.

Behavior under test: the already-existing, exercised CheckForTradingSignal ->
DirectionSignal -> EntryConditionsBlock path. These tests do NOT certify a
trading edge or replace a real-tick MetaTrader Strategy Tester run.
"""

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "nyao_scalper.mq5"
BASELINE = ROOT / "research" / "entry_quality" / "Trader_ENTRY_GATE_FIXED001.set"
TRIAL = ROOT / "research" / "fresh_entry" / "Trader_FRESH_ER015_FIXED001.set"


def read_inputs(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    values = re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)=([^\r\n]*)$", content)
    assert len(values) == len(set(k for k, _ in values)), "Duplicate .set inputs"
    return dict(values)


class FreshEntryEfficiencyExperiment(unittest.TestCase):
    def test_original_source_unmodified(self):
        self.assertEqual(
            hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837",
        )

    def test_one_input_diff_only(self):
        baseline, trial = read_inputs(BASELINE), read_inputs(TRIAL)
        self.assertEqual(len(baseline), 172)
        self.assertEqual(len(trial), 172)
        self.assertEqual(set(baseline), set(trial))
        changed = {key: (baseline[key], trial[key])
                   for key in baseline if baseline[key] != trial[key]}
        self.assertEqual(changed, {"MinEfficiencyToTrade": ("0.0", "0.15")})

    def test_trial_exercises_active_fresh_entry_path(self):
        source = SOURCE.read_text(encoding="utf-8")
        score_start = source.index("void CheckForTradingSignal()")
        score_end = source.index("// | Entry score vs. threshold", score_start)
        signal_path = source[score_start:score_end]
        self.assertIn("BuySignal()", signal_path)
        self.assertIn("SellSignal()", signal_path)
        self.assertIn("OpenPosition(ORDER_TYPE_BUY", signal_path)
        self.assertIn("OpenPosition(ORDER_TYPE_SELL", signal_path)

        direction = source[source.index("double DirectionSignal(bool isBuy)"):
                           source.index("double BuySignal()")]
        self.assertIn("CheckEntryConditions(", direction)
        self.assertIn("ComputeEntryScore(", direction)
        self.assertIn("e.score >= e.threshold", direction)

        condition = source[source.index("string EntryConditionsBlock("):
                           source.index("// | Directional Efficiency Ratio", source.index("string EntryConditionsBlock("))]
        self.assertIn("if(MinEfficiencyToTrade > 0)", condition)
        self.assertIn("DirectionalEfficiency(isBuy, RangeFilterPeriod)", condition)
        self.assertIn("if(er < MinEfficiencyToTrade)", condition)

        efficiency = source[source.index("double DirectionalEfficiency("):
                            source.index("// | Higher-Timeframe Trend Filter", source.index("double DirectionalEfficiency("))]
        self.assertIn("CopyClose(_Symbol, _Period, 1, n + 1, closes)", efficiency)
        self.assertIn("return MathMax(0.0, net) / path;", efficiency)

    def test_hypothesis_is_20_bar_closed_candles_with_no_other_feature_change(self):
        baseline, trial = read_inputs(BASELINE), read_inputs(TRIAL)
        for key, val in {
            "RangeFilterPeriod": "20",
            "RiskPerTradePct": "0.0",
            "MaxRiskPerTradePct": "1.0",
            "EnableDynamicLots": "false",
            "BaseLotSize": "0.01",
            "MaxLotSize": "0.02",
            "MaxOpenOrders": "1",
            "EnableNewBarEntryOnly": "true",
            "EnableHTFTrendFilter": "true",
            "DrawdownScope": "1",
            "EnableHedgeChain": "false",
            "EnableLossManagement": "false",
            "EnableVirtualSLReentry": "true",
            "EnableLogging": "false",
        }.items():
            self.assertEqual(baseline[key], val, key)
            self.assertEqual(trial[key], val, key)

    def test_no_auto_start_or_live_permissions_added_by_experiment(self):
        trial = TRIAL.read_text(encoding="utf-8")
        self.assertNotIn("RiskPerTradePct=1.25", trial)
        self.assertNotIn("MaxOpenOrders=2", trial)
        self.assertNotIn("EnableTradingHours=true", trial)
        self.assertIn("FRESH ENTRY RESEARCH ONLY", trial)


if __name__ == "__main__":
    unittest.main()
