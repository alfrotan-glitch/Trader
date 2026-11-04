"""No broker connection: frozen future dates and native SL-gap parser contracts."""
from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "research" / "spread_gate"))
import auto_nyao_spread_gate as future
import analyze_stop_slippage as gap


def deal(date: str, side: str, price: str, comment: str, net: str) -> str:
    cells = [date, "683", "XAUUSD@", side, "out", "0.01", price,
             "683", "0.00", "0.00", net, "3 462.33", comment]
    return "<tr>" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>"


class FrozenForwardAndStopsTests(unittest.TestCase):
    def test_forward_is_not_available_immediately_or_backdated(self):
        with self.assertRaisesRegex(future.GuardFailure, "WAITING_FOR_FUTURE_DATA"):
            future.derive_forward_dates(dt.date(2026, 11, 4))
        with self.assertRaisesRegex(future.GuardFailure, "WAITING_FOR_FUTURE_DATA"):
            future.derive_forward_dates(dt.date(2026, 12, 6))
        dates = future.derive_forward_dates(dt.date(2026, 12, 8))
        self.assertEqual(dates, ("2026.11.05", "2026.12.06"))

    def test_config_uses_only_frozen_future_boundary(self):
        cfg = future.config_for(
            1234567, "WMMarkets-Demo", "NYAO_STOP_FIXED",
            "Trader_SPREAD_BASE_TEST.set", ("2026.11.05", "2026.12.06")
        )
        self.assertIn("FromDate=2026.11.05", cfg)
        self.assertIn("ToDate=2026.12.06", cfg)
        self.assertIn("AllowLiveTrading=0", cfg)
        self.assertIn("Expert=TraderResearch\\nyao_scalper_control", cfg)
        with self.assertRaises(future.GuardFailure):
            future.config_for(1234567, "WMMarkets-Demo", "NYAO_STOP_FIXED",
                              "Trader_SPREAD_BASE_TEST.set",
                              ("2026.01.01", "2026.12.06"))
        with self.assertRaises(future.GuardFailure):
            future.config_for(1234567, "WMMarkets-Demo", "NYAO_STOP_FIXED",
                              "Trader_SPREAD_BASE_TEST.set",
                              ("2026.11.05", "2026.11.16"))

    def test_native_report_future_range_must_match(self):
        params = {f"field{i}": str(i) for i in range(170)}
        b = dict(params, MaxSpreadPoints="500")
        t = dict(params, MaxSpreadPoints="400")
        base = {"trades": 1, "net": 12.0, "deposit": 3000,
                "tested_range": "XAUUSD@,M5 (2026.01.01 - 2026.11.02)"}
        trial = {"trades": 1, "net": 11.0, "deposit": 3000,
                 "tested_range": base["tested_range"]}
        with patch.object(future, "validated_native_report",
                          side_effect=[(base, b), (trial, t)]), \
             patch.object(future, "native_identity",
                          side_effect=[{"symbol": "XAUUSD@", "period": base["tested_range"]},
                                       {"symbol": "XAUUSD@", "period": base["tested_range"]}]):
            with self.assertRaisesRegex(future.GuardFailure, "preregistered future-only"):
                future.validate_pair(Path("base.htm"), Path("trial.htm"),
                                     ("2026.11.05", "2026.12.06"))

    def test_native_symbol_and_period_are_separate_html_fields(self):
        html_doc = (
            "<html><table>"
            '<tr><td colspan="3">Symbol:</td><td colspan="10"><b>XAUUSD@</b></td></tr>'
            '<tr><td colspan="3">Period:</td>'
            '<td colspan="10"><b>M5 (2026.01.01 - 2026.03.31)</b></td></tr>'
            "</table></html>"
        )
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "native_report.htm"
            file.write_text(html_doc, encoding="utf-8")
            identity = future.native_identity(file)
            self.assertEqual(identity, {
                "symbol": "XAUUSD@",
                "period": "M5 (2026.01.01 - 2026.03.31)",
            })
            file.write_text(html_doc.replace("XAUUSD@", "EURUSD"), encoding="utf-8")
            with self.assertRaisesRegex(future.GuardFailure, "Wrong native MT5 symbol"):
                future.native_identity(file)
            file.write_text(html_doc.replace("M5 (", "M1 ("), encoding="utf-8")
            with self.assertRaisesRegex(future.GuardFailure, "timeframe"):
                future.native_identity(file)
            file.write_text(html_doc.replace("Symbol:", "Period:"), encoding="utf-8")
            with self.assertRaises(future.GuardFailure):
                future.native_identity(file)

    def test_actual_SL_exit_gap_is_directional_and_not_just_stop_label(self):
        source = ("<html><table>"
                  + deal("2026.04.13 01:00:06", "buy", "4757.26",
                         "sl 4706.34", "-70.92")
                  + deal("2026.03.09 01:00:00", "sell", "5129.90",
                         "sl 5149.80", "-39.90")
                  + deal("2026.02.12 10:30:00", "buy", "5100",
                         "trend flip", "4.25") + "</table></html>")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.htm"
            path.write_text(source, encoding="utf-8")
            result = gap.parse_executed_stops(path)
        self.assertEqual(result["all_native_exits"], 3)
        self.assertEqual(result["stop_tagged_exits"], 2)
        self.assertEqual(result["adverse_over_10_quote_units"], 2)
        self.assertAlmostEqual(result["worst_adverse_slippage_quote_units"], 50.92)
        self.assertEqual(result["largest_10_adverse_exits"][0]["net_profit_usd"], -70.92)

    def test_no_native_exits_does_not_invent_slippage(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.htm"
            path.write_text("<html>No deals</html>", encoding="utf-8")
            with self.assertRaises(ValueError):
                gap.parse_executed_stops(path)


if __name__ == "__main__":
    unittest.main()
