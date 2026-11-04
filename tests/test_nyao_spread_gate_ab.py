"""Pure safety/contract tests: never open MetaTrader or send orders."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import auto_nyao_spread_gate as experiment


class SpreadGateTests(unittest.TestCase):
    def test_profile_is_exactly_one_input(self):
        mandatory = {
            "RiskPerTradePct": "0.0", "EnableDynamicLots": "false",
            "BaseLotSize": "0.01", "MaxRiskPerTradePct": "1.0",
            "MinEfficiencyToTrade": "0.15", "EnableMaxSpreadFilter": "true",
            "EnableCheckpointExit": "true", "EnableRiskReward": "false",
            "MaxOpenOrders": "1", "PointInputDigits": "3",
            "MaxSpreadPoints": "500",
        }
        for i in range(172-len(mandatory)):
            mandatory[f"FakeField{i}"] = str(i)
        content = "; research preset\n" + "".join(f"{k}={v}\n" for k, v in mandatory.items())
        baseline, trial = experiment.frozen_profiles(content)
        self.assertEqual(baseline, content)
        b = experiment.profile_inputs(baseline)
        t = experiment.profile_inputs(trial)
        self.assertEqual({k for k in b if b[k] != t[k]}, {"MaxSpreadPoints"})
        self.assertEqual(t["MaxSpreadPoints"], "400")
        self.assertEqual(len(t), 172)

    def test_duplicate_or_wrong_baseline_fails_closed(self):
        with self.assertRaises(experiment.GuardFailure):
            experiment.profile_inputs("MaxSpreadPoints=500\nMaxSpreadPoints=500\n")
        with self.assertRaises(experiment.GuardFailure):
            experiment.frozen_profiles("MaxSpreadPoints=500\n")
        with self.assertRaises(experiment.GuardFailure):
            experiment.profile_inputs("Bad raw sentence\n")

    def test_unique_spread_config_uses_original_guarded_control(self):
        ini = experiment.config_for(
            1234567, "WMMarkets-Demo",
            "NYAO_STOP_TEST_SPREAD", "Trader_SPREAD_BASE_unique.set"
        )
        self.assertIn("Expert=TraderResearch\\nyao_scalper_control", ini)
        self.assertIn("ExpertParameters=Trader_SPREAD_BASE_unique.set", ini)
        self.assertIn("AllowLiveTrading=0", ini)
        self.assertIn("Model=4", ini)
        with self.assertRaises(experiment.GuardFailure):
            experiment.config_for(1234567, "WMMarkets-Demo",
                                  "NYAO_STOP_TEST_SPREAD", "unverified.set")

    def test_paired_native_inputs_reject_any_extra_delta(self):
        common = {f"FakeField{i}": str(i) for i in range(171)}
        first = dict(common, MaxSpreadPoints="500")
        second = dict(common, MaxSpreadPoints="400")
        base_metrics = {"trades": 709, "net": 1091.44,
                        "tested_range": "M5 (2026.01.01 - 2026.11.02)"}
        trial_metrics = {"trades": 708, "net": 1110.00,
                         "tested_range": "M5 (2026.01.01 - 2026.11.02)"}
        with patch.object(experiment, "validated_native_report",
                          side_effect=[(base_metrics, first), (trial_metrics, second)]), \
             patch.object(experiment, "native_deal_rows",
                          side_effect=[[("a",)] * 1418, [("b",)] * 1416]):
            out = experiment.validate_pair(Path("base.htm"), Path("trial.htm"))
        self.assertEqual(out["delta_net_usd"], 18.56)
        self.assertEqual(set(out["only_native_input_difference"]), {"MaxSpreadPoints"})
        self.assertTrue(out["previous_709_reference_reproduced"])

        broken = dict(second, FakeField0="CHANGED")
        with patch.object(experiment, "validated_native_report",
                          side_effect=[(base_metrics, first), (trial_metrics, broken)]):
            with self.assertRaises(experiment.GuardFailure):
                experiment.validate_pair(Path("base.htm"), Path("trial.htm"))


if __name__ == "__main__":
    unittest.main()
