"""Safety and native comparison contracts; no MetaTrader terminal needed."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import auto_nyao_entry_gate_folds as study


class ReentryGateFoldTests(unittest.TestCase):
    def test_frozen_profile_has_reentry_enabled_in_both_modes(self):
        self.assertTrue(study.TRIAL_SOURCE.is_file())
        self.assertIn(study.sha256(study.TRIAL_SOURCE),
                      study.TRIAL_SOURCE_ALLOWED_SHA)
        source = study.SOURCE_PRESET
        values = study.profile_inputs(source.read_text("utf-8-sig"))
        self.assertEqual(len(values), 172)
        self.assertEqual(values["EnableVirtualSLReentry"], "true")
        self.assertEqual(values["ReentryMinSignalPct"], "0.75")
        self.assertEqual(values["MaxSpreadPoints"], "500")
        self.assertEqual(values["RiskPerTradePct"], "0.0")

    def test_trial_and_control_config_use_exact_same_inputs(self):
        for fold in study.FOLDS:
            base = study.entry_fold_ini(1234567, "WMMarkets-Demo",
                 "NYAO_STOP_HIST_Q1_BASE_20261104123456789",
                 "Trader_HIST_ENTRY_GATE_20261104_123456_789.set", fold, False)
            trial = study.entry_fold_ini(1234567, "WMMarkets-Demo",
                 "NYAO_STOP_HIST_Q1_GATE_20261104123456789",
                 "Trader_HIST_ENTRY_GATE_20261104_123456_789.set", fold, True)
            self.assertIn("Expert=" + study.CONTROL_EXPERT, base)
            self.assertIn("Expert=" + study.TRIAL_EXPERT, trial)
            for txt in (base, trial):
                self.assertIn("AllowLiveTrading=0", txt)
                self.assertIn("Enabled=0", txt)
                self.assertIn("Model=4", txt)
                self.assertIn("Optimization=0", txt)
                self.assertIn("FromDate=" + fold[1], txt)
                self.assertIn("ToDate=" + fold[2], txt)
                self.assertIn("Deposit=3000", txt)
                self.assertIn("ExpertParameters=Trader_HIST_ENTRY_GATE_20261104_123456_789.set", txt)

    def test_comparison_fails_if_any_native_input_changes(self):
        fold = study.FOLDS[0]
        common = {f"Fake{i}": str(i) for i in range(170)}
        common["MaxSpreadPoints"] = "500"
        base = {"trades": 100, "deposit": 3000, "net": 140,
                "dd_pct": 7, "tested_range": "M5 (2026.01.01 - 2026.03.31)"}
        trial = dict(base, net=160, dd_pct=6)
        with patch.object(study, "validated_native_report",
                          side_effect=[(base, common), (trial, dict(common))]), \
             patch.object(study, "native_identity",
                          side_effect=[{"symbol":"XAUUSD@","period":base["tested_range"]}]*2), \
             patch.object(study, "native_deal_rows",
                          side_effect=[[('x',)]*200,[('x',)]*200]), \
             patch.object(study, "compare_reports",
                          return_value={"baseline": {}, "trial": {}}):
            out = study.compare_entry_fold(Path("a"), Path("b"), fold)
            self.assertEqual(out["net_gain_usd"], 20)
            self.assertTrue(out["native_identical_inputs"])
        trial_inputs = dict(common, MaxSpreadPoints="400")
        with patch.object(study, "validated_native_report",
                          side_effect=[(base, common), (trial, trial_inputs)]):
            with self.assertRaises(study.GuardFailure):
                study.compare_entry_fold(Path("a"), Path("b"), fold)

    def test_four_fold_decision_never_authorizes_real_trading(self):
        rows = []
        for fold in study.FOLDS:
            rows.append({
                "fold": {"id":fold[0]},
                "control": {"net": 100, "gross_profit": 200,
                            "gross_loss": -100},
                "trial": {"net": 120, "gross_profit": 220,
                          "gross_loss": -100},
                "net_gain_usd": 20, "dd_delta_pp": -1,
            })
        result = study.outcome_summary(rows)
        self.assertIn("RESEARCH_CANDIDATE_ONLY", result["verdict"])
        self.assertFalse(result["real_trading_approved"])
        rows[0]["net_gain_usd"] = -10
        rows[1]["net_gain_usd"] = -10
        self.assertEqual(study.outcome_summary(rows)["verdict"],
                         "HISTORICAL_ENTRY_GATE_NOT_PROVEN")
        with self.assertRaises(study.GuardFailure):
            study.outcome_summary(rows[:3])

    def test_cached_native_baselines_require_matching_shas(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            samples = {
                f"native/{fold[0]}_BASE/NYAO_STOP_HIST_{fold[0]}_BASE_20261104132228172.htm":
                f"data {fold[0]}".encode()
                for fold in study.FOLDS
            }
            hashes = {name: hashlib.sha256(raw).hexdigest()
                      for name, raw in samples.items()}
            manifest = {
                "verdict": "HISTORICAL_STRESS_NO_ROBUST_IMPROVEMENT__LIVE_LOCKED",
                "demo_account_verified": True,
                "source_sha256": "vendor",
                "guarded_control_ex5_sha256": "ex5",
                "preset_source_sha256": "set",
                "folds_preregistered": list(study.FOLDS),
                "fold_results": [
                    {"baseline":{"trades":30,"net":5}} for _ in study.FOLDS
                ],
                "files_sha256": hashes,
            }
            archive = root / "NYAO_HISTORICAL_STRESS_EVIDENCE_20261104_132228_172.zip"
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr("manifest.json",json.dumps(manifest))
                for name,raw in samples.items():
                    z.writestr(name,raw)
            metrics = {"trades":30,"net":5,"deposit":3000}
            fields = {f"Fake{i}":str(i) for i in range(170)}
            fields["MaxSpreadPoints"]="500"
            with patch.object(study,"ROOT",root), \
                 patch.object(study,"validated_native_report",
                     return_value=(metrics,fields)), \
                 patch.object(study,"native_identity",
                     side_effect=[
                         {"symbol":"XAUUSD@",
                          "period":f"M5 ({f[1]} - {f[2]})"}
                         for f in study.FOLDS
                     ]), \
                 patch.object(study,"native_deal_rows",
                     return_value=[("x",)]*60):
                result=study.try_cache_baselines(root/"output","vendor","ex5","set")
                self.assertEqual(set(result), {"Q1","Q2","Q3","Q4"})
            with patch.object(study,"ROOT",root):
                self.assertEqual(study.try_cache_baselines(
                    root/"other","vendor","changed ex5","set"),{})

if __name__ == "__main__":
    unittest.main()
