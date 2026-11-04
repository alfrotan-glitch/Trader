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
    find_mt5, make_safe_preflight_ini, launch_safe_preflight,
    verify_demo_after_autostart, GuardFailure, SYMBOL, PERIOD,
    EXPECTED_NET, EXPECTED_TRADES, CONTROL_EXPERT,
    guarded_control_source, native_deal_rows, compare_native_reports,
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

    def test_guarded_control_is_only_one_source_insertion(self):
        original = (ROOT / "nyao_scalper.mq5").read_text(encoding="utf-8")
        control = guarded_control_source(original)
        self.assertEqual(control.count("int OnInit()"), 1)
        self.assertIn("if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))", control)
        self.assertIn("return INIT_FAILED;", control)
        self.assertEqual(
            control.replace(
                "\n    // RESEARCH CONTROL: never run on a normal chart or in optimization.\n"
                "    if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))\n"
                "        return INIT_FAILED;", "", 1
            ), original
        )
        config = make_tester_ini(
            123456, "WMMarkets-Demo", "NYAO_STOP_CTRL_2026110401", CONTROL_EXPERT
        )
        self.assertIn("Expert=TraderResearch\\nyao_scalper_control", config)
        with self.assertRaisesRegex(GuardFailure, "Only pinned"):
            make_tester_ini(123456, "WMMarkets-Demo", "NYAO_STOP_BAD", "OtherExpert")

    def test_exact_deal_ledger_AA_detects_first_divergence(self):
        import html as html_module
        def report(path, entries):
            with path.open("w", encoding="utf-8") as out:
                out.write("<html><table><tr><td>Deal</td></tr>")
                for time, side, price in entries:
                    cols = [
                        time, "1", "XAUUSD@", side, "in", "0.01",
                        price, "1", "0.00", "0.00", "0.00", "3000.00", "open"
                    ]
                    out.write("<tr>" + "".join(
                        "<td>" + html_module.escape(value) + "</td>"
                        for value in cols
                    ) + "</tr>")
                    cols2 = [
                        time, "2", "XAUUSD@", "sell" if side=="buy" else "buy", "out",
                        "0.01", "4000.00", "2", "0.00", "0.00", "-10.00",
                        "2990.00", "sl"
                    ]
                    out.write("<tr>" + "".join(
                        "<td>" + html_module.escape(value) + "</td>"
                        for value in cols2
                    ) + "</tr>")
                out.write("</table></html>")
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "control.htm", Path(tmp) / "diag.htm"
            entries = [
                ("2026.01.01 01:10:00", "buy", "4000.00"),
                ("2026.01.01 02:10:00", "sell", "4001.00"),
            ]
            report(a, entries); report(b, entries)
            self.assertTrue(compare_native_reports(a, b)["exact_native_deal_parity"])
            report(b, [entries[0], (entries[1][0], entries[1][1], "4002.00")])
            comparison = compare_native_reports(a, b)
            self.assertFalse(comparison["exact_native_deal_parity"])
            self.assertEqual(comparison["first_different_deal_index"], 2)

    def test_safe_autostart_disables_all_chart_trading(self):
        ini = make_safe_preflight_ini()
        tester = make_tester_ini(12345678, "WMMarkets-Demo", "NYAO_STOP_20261104")
        for key in ("[Experts]", "Enabled=0", "AllowLiveTrading=0",
                    "AllowDllImport=0", "Account=1", "Profile=1"):
            self.assertIn(key, ini)
            self.assertIn(key, tester)
        self.assertNotIn("Expert=", ini)
        self.assertNotIn("[StartUp]", ini)
        self.assertNotIn("OrderSend(", (ROOT / "tools" / "auto_nyao_stop_recovery.py")
                         .read_text(encoding="utf-8"))

    def test_safe_autostart_does_not_start_when_other_terminal_is_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            terminal = Path(tmp) / "terminal64.exe"
            with patch("auto_nyao_stop_recovery.terminal_running", return_value=False), \
                 patch("auto_nyao_stop_recovery.detect_any_terminal_process", return_value=True), \
                 patch("auto_nyao_stop_recovery.subprocess.Popen") as popen:
                with self.assertRaisesRegex(GuardFailure, "already running"):
                    launch_safe_preflight(terminal, Path(tmp))
                popen.assert_not_called()

    def test_autostart_rejects_live_account_immediately(self):
        with patch("auto_nyao_stop_recovery.verify_running_demo",
                   side_effect=GuardFailure("Account is NOT verified DEMO; aborting automatic tester")), \
             patch("auto_nyao_stop_recovery.time.sleep") as wait:
            with self.assertRaisesRegex(GuardFailure, "NOT verified DEMO"):
                verify_demo_after_autostart(Path("terminal64.exe"), Path("demo-data"), True)
            wait.assert_not_called()

    def test_autostart_retries_only_not_ready_login(self):
        from unittest.mock import call
        with patch("auto_nyao_stop_recovery.verify_running_demo",
                   side_effect=[GuardFailure("MT5 login/account details unavailable"),
                                (1234, "WMMarkets-Demo")]) as verify, \
             patch("auto_nyao_stop_recovery.time.sleep") as wait:
            self.assertEqual(
                verify_demo_after_autostart(Path("terminal64.exe"), Path("demo-data"), True),
                (1234, "WMMarkets-Demo"),
            )
            self.assertEqual(verify.call_count, 2)
            wait.assert_called_once_with(5)

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
        self.assertIn("saved WMMarkets DEMO account once", source)
        self.assertIn("launch_safe_preflight(terminal, run_dir)", source)
        self.assertIn("verify_demo_after_autostart(", source)

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
