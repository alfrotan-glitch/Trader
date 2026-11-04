"""Offline regression tests for one-click auto packaging of Nyao historical evidence.

Never launches MetaTrader, terminates a process, or sends broker orders.
"""
from __future__ import annotations
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from auto_nyao_stop_recovery import (
    make_tester_ini, pack_evidence, archive_previous_csvs, check_report,
    find_mt5, GuardFailure, SYMBOL, PERIOD, EXPECTED_NET, EXPECTED_TRADES,
)


class OneClickEvidenceTests(unittest.TestCase):
    def test_config_is_demo_tester_only_and_real_tick_locked(self):
        s = make_tester_ini(12345678, "WMMarkets-Demo", "NYAO_STOP_202611040841")
        self.assertIn("Expert=TraderResearch\\nyao_scalper_diagnostic", s)
        self.assertIn("ExpertParameters=Trader_FRESH_ER015_FIXED001.set", s)
        for fragment in (
            "Model=4", "Optimization=0", "ForwardMode=0", "Visual=0",
            "UseCloud=0", "UseRemote=0", "ShutdownTerminal=1",
            "Symbol=XAUUSD@", "Period=M5", "Deposit=3000",
            "FromDate=2026.01.01", "ToDate=2026.11.02",
            "Server=WMMarkets-Demo",
        ):
            self.assertIn(fragment, s)
        self.assertNotIn("Expert=nyao_scalper.mq5", s)
        self.assertNotIn("[StartUp]", s)
        with self.assertRaises(GuardFailure):
            make_tester_ini(0, "WMMarkets-Demo", "NYAO_STOP_202611040841")
        with self.assertRaises(GuardFailure):
            make_tester_ini(1234, "server\n[StartUp]", "NYAO_STOP_202611040841")

    def test_zip_excludes_account_config_and_earlier_archives(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            run = base / "evidence"
            run.mkdir()
            (run / "manifest.json").write_text('{"verdict":"PASS"}', encoding="utf-8")
            (run / "private_tester.ini").write_text(
                "[Common]\nLogin=12345678\n", encoding="utf-8"
            )
            (run / "archive").mkdir()
            (run / "archive" / "old.csv").write_text("old", encoding="utf-8")
            (run / "NYAO_STOP_RECOVERY_TICKS.csv").write_text("new", encoding="utf-8")
            z = base / "evidence.zip"
            pack_evidence(run, z)
            import zipfile
            with zipfile.ZipFile(z) as archive:
                names = archive.namelist()
                self.assertIn("manifest.json", names)
                self.assertIn("NYAO_STOP_RECOVERY_TICKS.csv", names)
                self.assertNotIn("private_tester.ini", names)
                self.assertNotIn("archive/old.csv", names)

    def test_archives_previous_csv_files_without_deleting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            common = root / "common"
            common.mkdir()
            run = root / "run"
            run.mkdir()
            (common / "NYAO_ENTRY_DIAGNOSTICS.csv").write_text("old", encoding="utf-8")
            archive_previous_csvs(common, run)
            self.assertFalse((common / "NYAO_ENTRY_DIAGNOSTICS.csv").exists())
            self.assertEqual(
                (run / "archive" / "NYAO_ENTRY_DIAGNOSTICS.csv").read_text(encoding="utf-8"),
                "old"
            )

    def test_fail_closed_on_changed_trade_count_or_quality(self):
        good = {
            "trades": EXPECTED_TRADES,
            "net": EXPECTED_NET,
            "quality": "100% real ticks",
        }
        with patch("auto_nyao_stop_recovery.parse_report", return_value=good):
            self.assertEqual(check_report(Path("not-used.html")), good)
        with patch("auto_nyao_stop_recovery.parse_report",
                   return_value={**good, "trades": 717}):
            with self.assertRaisesRegex(GuardFailure, "parity FAIL"):
                check_report(Path("not-used.html"))
        with patch("auto_nyao_stop_recovery.parse_report",
                   return_value={**good, "quality": "95% based on M1"}):
            with self.assertRaisesRegex(GuardFailure, "100% real ticks"):
                check_report(Path("not-used.html"))

    def test_no_return_from_finally_and_actionable_demo_preflight(self):
        path = ROOT / "tools" / "auto_nyao_stop_recovery.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for statement in ast.walk(tree):
            if isinstance(statement, ast.Try):
                for line in statement.finalbody:
                    self.assertFalse(
                        any(isinstance(n, ast.Return) for n in ast.walk(line)),
                        "A return in finally overrides the preflight failure exit code",
                    )
        self.assertIn("wait until connected", source)
        self.assertIn("RUN_NYAO_STOP_RECOVERY.bat", source)
        self.assertIn("auto-launch an unverified terminal", source)

    def test_only_explicit_oneclick_launcher_and_demo_gate(self):
        source = (ROOT / "tools" / "auto_nyao_stop_recovery.py").read_text(encoding="utf-8")
        bat = (ROOT / "RUN_NYAO_STOP_RECOVERY.bat").read_text(encoding="utf-8")
        self.assertIn("verify_running_demo(terminal, data)", source)
        self.assertIn("int(acct.trade_mode) != 0", source)
        self.assertIn("positions != 0 or orders != 0", source)
        self.assertIn("close_terminal(terminal", source)
        self.assertIn("install_nyao_diagnostics.ps1", source)
        self.assertIn("NYAO_STOP_RECOVERY_TICKS.csv", source)
        self.assertIn("archive_previous_csvs(common", source)
        self.assertIn("zipfile.ZipFile", source)
        self.assertIn("auto_nyao_stop_recovery.py", bat)
        self.assertNotIn("OrderSend(", source)


if __name__ == "__main__":
    unittest.main()
