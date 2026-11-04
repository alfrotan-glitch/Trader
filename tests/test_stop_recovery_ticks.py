"""Synthetic read-only tests for the MQL5 stop-recovery observer output."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/stop_recovery"))
from analyze_tick_recovery import COLUMNS, analyze  # noqa: E402


def row(ticket="42", status="WINDOW_ELAPSED", tick_count="3", return_delta=600000,
        plus5_delta=720000, checkpoint_delta=900000):
    e = 1700000000000
    def hit(delta):
        return "" if delta is None else str(e + delta)
    return {
        "schema": "1", "ticket": ticket, "symbol": "XAUUSD@",
        "period": "PERIOD_M5", "direction": "BUY",
        "entry_time": "2026.01.02 10:00:00",
        "entry_price": "4500.0", "exit_price": "4480.0", "net_usd": "-20.00",
        "checkpoint_distance_price": "20.00",
        "exit_time_ms": str(e), "window_end_ms": str(e + 86400000),
        "first_observed_tick_ms": hit(1000) if int(tick_count) else "",
        "last_observed_tick_ms": hit(86390000) if int(tick_count) else "",
        "observed_ticks": tick_count,
        "first_return_to_entry_ms": hit(return_delta),
        "first_plus5_ms": hit(plus5_delta),
        "first_checkpoint_ms": hit(checkpoint_delta),
        "max_adverse_before_return_price": "25.00",
        "max_additional_adverse_after_exit_price": "5.00",
        "max_favorable_after_exit_price": "22.00",
        "status": status,
    }


def save(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rows)


class PostStopTickAnalyzerTests(unittest.TestCase):
    def test_valid_window_and_known_1h_hits(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "stops.csv"
            save(p, COLUMNS, [row()])
            result = analyze(p, expected_stops=1)
            self.assertEqual(result["verdict"], "RECONCILED_24H_OBSERVED")
            self.assertEqual(result["confirmed_hit_counts_minimum"]["first_return_to_entry_ms"]["1h"], 1)
            self.assertEqual(result["positions"][0]["checkpoint_after_sec"], 900)

    def test_censored_and_closed_market_are_not_fake_no_rebounds(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "stops.csv"
            zero = row(ticket="43", status="NO_TICKS_IN_WINDOW", tick_count="0",
                       return_delta=None, plus5_delta=None, checkpoint_delta=None)
            censored = row(ticket="44", status="CENSORED_TEST_END",
                           return_delta=None, plus5_delta=None, checkpoint_delta=None)
            save(p, COLUMNS, [zero, censored])
            report = analyze(p)
            self.assertEqual(report["verdict"], "RECONCILED_WITH_CENSORED_OR_GAPS")
            self.assertEqual(report["stop_count"], 2)
            self.assertEqual(report["confirmed_hit_counts_minimum"]["first_return_to_entry_ms"]["24h"], 0)

    def test_missing_or_duplicate_ticket_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "stops.csv"
            save(p, COLUMNS, [row(), row()])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                analyze(p)
            save(p, COLUMNS, [row()])
            with self.assertRaisesRegex(ValueError, "Expected 2"):
                analyze(p, expected_stops=2)

    def test_hits_must_be_observed_after_stop_and_before_24h(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "stops.csv"
            late = row()
            late["first_return_to_entry_ms"] = str(int(late["exit_time_ms"]) + 86400001)
            save(p, COLUMNS, [late])
            with self.assertRaisesRegex(ValueError, "not observed"):
                analyze(p)
            invalid = row()
            invalid["first_observed_tick_ms"] = ""
            save(p, COLUMNS, [invalid])
            with self.assertRaisesRegex(ValueError, "Tick"):
                analyze(p)

    def test_reconciliation_missing_stop_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "stops.csv"
            e = Path(t) / "entries.csv"
            save(p, COLUMNS, [row()])
            fields = ["ticket", "exit_reason_code", "net_profit_usd", "status"]
            save(e, fields, [
                {"ticket": "42", "exit_reason_code": "4", "net_profit_usd": "-20", "status": "CLOSED"},
                {"ticket": "43", "exit_reason_code": "4", "net_profit_usd": "-30", "status": "CLOSED"},
                {"ticket": "44", "exit_reason_code": "4", "net_profit_usd": "10", "status": "CLOSED"},
            ])
            report = analyze(p, e)
            self.assertEqual(report["verdict"], "INCOMPLETE_EVIDENCE")
            self.assertEqual(report["entry_reconciliation"]["missing_stop_watches"], ["43"])

    def test_no_execution_code_added_to_original_7_patch_diagnostic(self):
        base = (ROOT / "nyao_scalper.mq5").read_text(encoding="utf-8")
        variant = (ROOT / "research/diagnostics/nyao_scalper_diagnostic.mq5").read_text(encoding="utf-8")
        self.assertNotEqual(base, variant)
        self.assertIn("DxOnTick();", variant)
        module = (ROOT / "research/diagnostics/NYAO_Diagnostics.mqh").read_text(encoding="utf-8")
        self.assertNotIn("OrderSend(", module)
        self.assertNotIn("PositionClose(", module)
        self.assertIn("void DxObservePostStops(MqlTick &tick)", module)
        self.assertIn("totalNet >= -0.005", module)


if __name__ == "__main__":
    unittest.main()
