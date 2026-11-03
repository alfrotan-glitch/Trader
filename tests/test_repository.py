"""Offline source/package checks. They do NOT certify MQL5 compilation or profit."""
from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MQL5_SHA256 = "91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837"


class TraderPackageTests(unittest.TestCase):
    def test_original_main_source_is_unmodified(self):
        path = ROOT / "nyao_scalper.mq5"
        self.assertTrue(path.is_file())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), EXPECTED_MQL5_SHA256)

    def test_original_license_and_attribution_retained(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("BSD 3-Clause License", license_text)
        self.assertIn("Elriz Wiraswara", license_text)
        self.assertIn("Neither the name of the copyright holder", license_text)

    def test_research_profile_has_required_keys(self):
        profile = (ROOT / "settings" / "xauusd-default.set").read_text(encoding="utf-8")
        for name in (
            "EnableHedgeChain", "EnableStopLoss", "EnableMaxSpreadFilter",
            "RiskPerTradePct", "MaxRiskPerTradePct", "MaxOpenOrders", "MaxLotSize"
        ):
            self.assertEqual(len(re.findall(r"^" + re.escape(name) + r"=", profile, re.M)), 1)
        self.assertIn("EnableHedgeChain=false", profile)
        self.assertIn("EnableStopLoss=true", profile)

    def test_one_click_launcher_has_no_broker_execution(self):
        batch = (ROOT / "ONE_CLICK_SETUP.bat").read_text(encoding="utf-8")
        ps = (ROOT / "tools" / "setup_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("setup_windows.ps1", batch)
        self.assertNotIn("-LaunchTester", batch)
        self.assertIn("Get-FileHash", ps)
        self.assertIn("metaeditor64.exe", ps)
        self.assertIn("MQL5", ps)
        self.assertIn("Experts", ps)
        self.assertIn("Trader_XAUUSD_M5_RESEARCH.set", ps)
        self.assertIn("Get-Process -Name terminal64", ps)
        self.assertIn("No automation enabling real trading", ps)
        self.assertNotIn("OrderSend(", ps)
        self.assertNotIn("EnableAlgoTrading", ps)

    def test_tester_requires_explicit_demo_acknowledgement(self):
        launcher = (ROOT / "RUN_TESTER.bat").read_text(encoding="utf-8")
        ps = (ROOT / "tools" / "setup_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("-LaunchTester", launcher)
        self.assertIn("Read-Host", ps)
        self.assertIn("if ($confirm -ne 'DEMO')", ps)
        for required in ("Model=4", "Optimization=0", "UseCloud=0", "Deposit=3000", "ShutdownTerminal=1"):
            self.assertIn(required, ps)

    def test_research_changes_explicitly_fail_closed(self):
        ps = (ROOT / "tools" / "setup_windows.ps1").read_text(encoding="utf-8")
        for setting in (
            "'EnableHedgeChain' = 'false'",
            "'EnableStopLoss' = 'true'",
            "'RiskPerTradePct' = '1.0'",
            "'MaxRiskPerTradePct' = '1.0'",
            "'MaxOpenOrders' = '1'"
        ):
            self.assertIn(setting, ps)
        self.assertIn("Pinned upstream MQL5 SHA-256 mismatch", ps)
        self.assertIn("Multiple MT5 installations detected", ps)
        self.assertIn("Source copy checksum mismatch", ps)


if __name__ == "__main__":
    unittest.main()
