"""Pure-unit tests: no MetaTrader process or broker orders."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import auto_nyao_historical_robustness as hist

class HistoricalRegimeTests(unittest.TestCase):
    def test_frozen_disjoint_periods_end_before_future_boundary(self):
        hist.assert_folds()
        self.assertEqual(len(hist.FOLDS), 4)
        self.assertEqual(hist.FOLDS[0][1], "2026.01.01")
        self.assertEqual(hist.FOLDS[-1][2], "2026.11.02")
        self.assertTrue(all(int(f[1][:4]) == 2026 for f in hist.FOLDS))

    def test_historical_config_is_8_real_tick_demo_tester_passes(self):
        for fold in hist.FOLDS:
            for profile in ("Trader_HIST_BASE_test.set",
                            "Trader_HIST_TRIAL_test.set"):
                config = hist.historical_ini(
                    1234567, "WMMarkets-Demo",
                    "NYAO_STOP_HIST_Q1_BASE_20261104", profile, fold)
                self.assertIn("FromDate=" + fold[1], config)
                self.assertIn("ToDate=" + fold[2], config)
                self.assertIn("AllowLiveTrading=0", config)
                self.assertIn("Expert=TraderResearch\\nyao_scalper_control", config)
                self.assertIn("Model=4", config)
                self.assertIn("Deposit=3000", config)
        with self.assertRaises(hist.GuardFailure):
            hist.historical_ini(
                1234567, "WMMarkets-Demo", "NYAO_STOP_BAD",
                "not_pinned.set", hist.FOLDS[0])
        with self.assertRaises(hist.GuardFailure):
            hist.historical_ini(
                1234567, "WMMarkets-Demo", "NYAO_STOP_BAD",
                "Trader_HIST_BASE_x.set", ("RANDOM", "2020.01.01", "2020.02.01"))

    @staticmethod
    def fake_rows(delta=(20, 20, 20, -5), dd=(0, 0, -.2, 0)):
        rows = []
        for i, fold in enumerate(hist.FOLDS):
            rows.append({
                "fold": {"id": fold[0], "start": fold[1], "end": fold[2]},
                "baseline": {"net": 100, "gross_profit": 200, "gross_loss": -100,
                             "dd_pct": 4.0},
                "trial": {"net": 100 + delta[i],
                          "gross_profit": 200 + delta[i], "gross_loss": -100,
                          "dd_pct": 4 + dd[i]},
                "trial_net_gain": delta[i] > 0,
                "trial_drawdown_delta_pp": dd[i],
                "trial_drawdown_not_worse": dd[i] <= .01,
                "trial_gap_not_worse": True,
            })
        return rows

    def test_strict_multifold_gate_only_demo_candidate_not_live(self):
        result = hist.assess_regime_stability(self.fake_rows())
        self.assertIn("CANDIDATE_FOR_DEMO_CHART_REVIEW_ONLY", result["verdict"])
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["trial_outperformed_net_in_windows"], 3)
        self.assertEqual(result["fold_net_sum_usd_baseline"], 400)
        self.assertEqual(result["fold_net_sum_usd_trial"], 455)

    def test_positive_net_not_enough_if_equity_drawdown_worsens(self):
        rows = self.fake_rows(dd=(.5, .5, .5, -.1))
        result = hist.assess_regime_stability(rows)
        self.assertEqual(result["verdict"], "HISTORICAL_STRESS_NO_ROBUST_IMPROVEMENT")
        self.assertFalse(result["live_trading_approved"])

    def test_missing_or_reordered_folds_are_rejected(self):
        rows = self.fake_rows()
        with self.assertRaises(hist.GuardFailure):
            hist.assess_regime_stability(rows[:3])
        with self.assertRaises(hist.GuardFailure):
            hist.assess_regime_stability(rows[::-1])

    def test_exact_native_fold_range_required(self):
        fold = hist.FOLDS[0]
        comparison = {
            "baseline": {"tested_range": "XAUUSD@,M5 (2026.01.01 - 2026.11.02)",
                         "net": 100, "trades": 100, "dd_pct": 10},
            "trial": {"tested_range": "XAUUSD@,M5 (2026.01.01 - 2026.11.02)",
                      "net": 110, "trades": 100, "dd_pct": 9.5},
            "delta_net_usd": 10,
        }
        with patch.object(hist, "validate_pair", return_value=comparison):
            with self.assertRaisesRegex(hist.GuardFailure, "exact historical fold"):
                hist.native_fold_metrics(Path("a.htm"), Path("b.htm"), fold)

    def test_stop_execution_influences_stress_report_not_only_pnl(self):
        fold = hist.FOLDS[0]
        comparison = {
            "baseline": {"tested_range": "XAUUSD@,M5 (2026.01.01 - 2026.03.31)",
                         "net": 100, "trades": 100, "dd_pct": 10},
            "trial": {"tested_range": "XAUUSD@,M5 (2026.01.01 - 2026.03.31)",
                      "net": 115, "trades": 95, "dd_pct": 10.3},
            "delta_net_usd": 15,
        }
        execution = {"baseline": {"worst_adverse_slippage_quote_units": 5},
                     "trial": {"worst_adverse_slippage_quote_units": 9}}
        with patch.object(hist, "validate_pair", return_value=comparison), \
             patch.object(hist, "compare_reports", return_value=execution):
            result = hist.native_fold_metrics(Path("a.htm"), Path("b.htm"), fold)
        self.assertTrue(result["trial_net_gain"])
        self.assertFalse(result["trial_drawdown_not_worse"])
        self.assertFalse(result["trial_gap_not_worse"])
        self.assertEqual(result["fold"]["id"], "Q1")


if __name__ == "__main__":
    unittest.main()
