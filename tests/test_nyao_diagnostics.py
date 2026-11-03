"""Offline integrity and synthetic CSV tests for the isolated tester-only diagnostic.

These tests do not compile MQL5 or run a Strategy Tester. Real MetaEditor
compilation and full ledger equivalence remain independent acceptance gates.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "research" / "diagnostics"
sys.path.insert(0, str(DIAG))
from analyze_nyao_diagnostics import EXPECTED, analyze  # noqa: E402


def count_top_level_args(text: str, marker: str):
    result = []
    pos = 0
    while True:
        pos = text.find(marker, pos)
        if pos < 0:
            return result
        pos += len(marker)
        depth = 1
        quoted = False
        escaped = False
        arguments = 1
        for j in range(pos, len(text)):
            char = text[j]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    result.append(arguments)
                    pos = j + 1
                    break
            elif char == "," and depth == 1:
                arguments += 1
        else:
            raise AssertionError("Unterminated function call")


class DiagnosticIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_bytes = (ROOT / "nyao_scalper.mq5").read_bytes()
        cls.base = cls.base_bytes.decode("utf-8")
        cls.trial = (DIAG / "nyao_scalper_diagnostic.mq5").read_text(encoding="utf-8")
        cls.module = (DIAG / "NYAO_Diagnostics.mqh").read_text(encoding="utf-8")

    def test_upstream_untouched(self):
        self.assertEqual(hashlib.sha256(self.base_bytes).hexdigest(),
                         "91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837")

    def test_diagnostic_only_adds_seven_instrumentation_patches(self):
        old = self.base.splitlines(keepends=True)
        new = self.trial.splitlines(keepends=True)
        changes = list(difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes())
        removed = [tag for tag, _, _, _, _ in changes if tag not in ("insert", "equal")]
        self.assertEqual(removed, [], "Vendor source was mutated beyond diagnostic inserts")
        insertions = [("".join(new[j1:j2])) for tag, i1, i2, j1, j2 in changes
                      if tag == "insert"]
        self.assertEqual(len(insertions), 7)
        for marker in (
            "if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))",
            "if(!DxInit()) return INIT_FAILED;",
            "DxFinish();",
            "DxOnTick();",
            "DxOnClosedPosition(closedTicket, closedProfit);",
            '#include "NYAO_Diagnostics.mqh"',
            "DxSnapshotBeforeSend(orderType, signalScore, bid, ask, dxSnapshot);",
            "DxTrackFilledPosition(result.order, orderType, result.price > 0 ? result.price : price,",
        ):
            self.assertIn(marker, "".join(insertions))
        self.assertIn("EnableLimitEntry || EnableHedgeChain || EnableLossManagement",
                      "".join(insertions))

    def test_csv_contract_matches_reader_and_never_overwrites(self):
        writes = count_top_level_args(self.module, "FileWrite(")
        self.assertEqual(writes, [len(EXPECTED) + 1, len(EXPECTED) + 1])
        self.assertEqual(len(EXPECTED), 36)
        self.assertIn("FileIsExist(_dxPath, FILE_COMMON)", self.module)
        self.assertIn("FILE_CSV | FILE_ANSI", self.module)
        self.assertIn("FileFlush(_dxHandle)", self.module)
        self.assertIn("HistorySelectByPosition(positionTicket)", self.module)
        self.assertIn("HistoryDealGetInteger(lastDeal, DEAL_REASON)", self.module)

    def test_no_execution_in_diagnostic_module_or_installer(self):
        for prohibited in ("OrderSend(", "PositionClose(", "EnableAlgoTrading",
                           "TerminalTradeAllowed = true"):
            self.assertNotIn(prohibited, self.module)
        installer = (ROOT / "tools" / "install_nyao_diagnostics.ps1").read_text()
        launcher = (ROOT / "INSTALL_NYAO_DIAGNOSTICS.bat").read_text()
        self.assertIn("install_nyao_diagnostics.ps1", launcher)
        self.assertNotIn("-LaunchTester", launcher)
        self.assertIn("[switch]$VerifyOnly", installer)
        self.assertIn("Copy-Item -LiteralPath $header", installer)
        self.assertIn("Copy-Item -LiteralPath $source", installer)
        self.assertIn("Start-Process -FilePath $mt5.Editor", installer)
        self.assertNotIn("Start-Process -FilePath $mt5.Terminal", installer)
        self.assertNotIn("OrderSend(", installer)
        self.assertIn("Original Nyao source changed", installer)
        # MetaEditor build 6230+ can return exit code 1 after a clean one-file build.
        # A successful result requires fresh nonempty EX5 + 0 errors/0 warnings log.
        self.assertNotIn("$p.ExitCode -ne 0", installer)
        self.assertIn("$logClean", installer)
        self.assertIn("$codeGenerated", installer)
        self.assertIn("$binaryExists", installer)
        self.assertIn("$binaryFresh", installer)
        self.assertIn("$binarySize -le 0", installer)
        self.assertIn("0 errors", installer)
        self.assertIn("0 warnings", installer)
        self.assertIn("Remove-Item -LiteralPath $logPath -Force", installer)

    def test_strategy_preset_still_uses_same_one_input_change(self):
        from test_fresh_entry_efficiency import read_inputs, BASELINE, TRIAL
        baseline, trial = read_inputs(BASELINE), read_inputs(TRIAL)
        self.assertEqual({k for k in baseline if baseline[k] != trial[k]},
                         {"MinEfficiencyToTrade"})
        self.assertEqual(trial["MinEfficiencyToTrade"], "0.15")
        self.assertEqual(trial["RiskPerTradePct"], "0.0")


class DiagnosticsAnalyzerTests(unittest.TestCase):
    def make_row(self, ticket: str = "42", net: str = "-10.00", status: str = "CLOSED"):
        row = {key: "" for key in EXPECTED}
        row.update({
            "schema": "1", "ticket": ticket, "symbol": "XAUUSD@",
            "period": "PERIOD_M5", "direction": "BUY",
            "entry_time": "2026.11.04 10:00:00", "exit_time": "2026.11.04 10:20:00",
            "entry_price": "4000.00", "volume": "0.01",
            "entry_spread_points": "20.00", "score": "6.0", "threshold": "5.0",
            "efficiency_20": "0.30", "atr_closed": "20.0", "trend_range": "0.5",
            "trend_ema": "0.5", "trend_efficiency": "0.5", "trend_momentum": "0.5",
            "losing_penalty": "0.0", "drawdown_pct": "0.0",
            "signal_bar": "2026.11.04 09:55:00", "initial_sl": "3980.00",
            "initial_tp": "4020.00", "exit_price": "3990.00",
            "exit_reason_code": "4", "exit_comment": "sl",
            "net_profit_usd": net, "mfe_price": "2.00", "mae_price": "10.00",
            "mfe_points": "200", "mae_points": "1000", "observed_ticks": "40",
            "max_spread_points": "40", "last_observed_sl": "3980.00",
            "adverse_sl_gap_price": "0", "status": status,
        })
        return row

    def save_rows(self, rows, path: Path):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=EXPECTED)
            writer.writeheader()
            writer.writerows(rows)

    def test_synthetic_good_result_reconciles(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "diagnostics.csv"
            self.save_rows([self.make_row("42","-10"),self.make_row("43","30")], path)
            out = analyze(path, 2, 20)
            self.assertEqual(out["verdict"], "COMPLETE_READ_ONLY_RECONCILED")
            self.assertEqual(out["summary"]["profit_factor"], 3.0)
            self.assertEqual(out["summary"]["net_usd"], 20.0)
            self.assertEqual(out["by_category"]["direction"]["BUY"]["trades"], 2)

    def test_synthetic_duplicate_ticket_is_fatal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "diagnostics.csv"
            self.save_rows([self.make_row("42"),self.make_row("42")], path)
            with self.assertRaisesRegex(ValueError, "Duplicate ticket"):
                analyze(path)

    def test_synthetic_incomplete_position_is_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "diagnostics.csv"
            self.save_rows([self.make_row("42"),self.make_row("43",status="OPEN_AT_DEINIT_UNRESOLVED")], path)
            out = analyze(path,1,-10)
            self.assertEqual(out["verdict"], "INCOMPLETE_EVIDENCE")
            self.assertEqual(out["unresolved_positions"][0]["ticket"], "43")

    def test_synthetic_bad_net_reconciliation_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "diagnostics.csv"
            self.save_rows([self.make_row("42")], path)
            with self.assertRaisesRegex(ValueError, "Net mismatch"):
                analyze(path,1,-8)


if __name__ == "__main__":
    unittest.main()
