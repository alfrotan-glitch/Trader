"""Single-input risk readiness preset: no EA changes, no new system.

This is static integrity verification; MetaTrader sizing, broker limits and fill
slippage require native DEMO testing. Real trading remains prohibited.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "research/fresh_entry/Trader_FRESH_ER015_FIXED001.set"
TRIAL = ROOT / "research/risk_readiness/Trader_RISK05_CAP1_ER015_FIXED001.set"
SOURCE = ROOT / "nyao_scalper.mq5"


def parse(path):
    raw = path.read_text(encoding="utf-8-sig")
    inputs = re.findall(r"(?m)^([A-Za-z_]\w*)=([^\r\n]*)\r?$", raw)
    if len(inputs) != len(dict(inputs)):
        raise ValueError("duplicate .set input")
    return dict(inputs)


class RiskReadinessExperiment(unittest.TestCase):
    def test_only_one_input_changed(self):
        a, b = parse(CONTROL), parse(TRIAL)
        self.assertEqual(len(a), 172)
        self.assertEqual(set(a), set(b))
        delta = {k:(a[k], b[k]) for k in a if a[k] != b[k]}
        self.assertEqual(delta, {"RiskPerTradePct": ("0.0", "0.5")})

    def test_frozen_trade_edge_and_max_risk(self):
        a, b = parse(CONTROL), parse(TRIAL)
        for key, val in {"MinEfficiencyToTrade": "0.15", "EnableCheckpointExit": "true",
                         "MaxRiskPerTradePct": "1.0", "EnableDynamicLots": "false",
                         "BaseLotSize": "0.01", "SLValue": "20000", "SLInputType": "2",
                         "TPValue": "20000", "EnableRiskReward": "false",
                         "MaxOpenOrders": "1", "EnableLossManagement": "false"}.items():
            self.assertEqual(a[key], val, key)
            self.assertEqual(b[key], val, key)

    def test_risk_gate_actually_precedes_original_order_send(self):
        code = SOURCE.read_text(encoding="utf-8")
        start = code.index("// Open Position\nvoid OpenPosition(")
        end = code.index("bool orderResult = OrderSend(request, result);", start)
        open_body = code[start:end]
        self.assertIn("if(!ApplyRiskSizing(currentLot, slPoints * (1 + cpSkips)))", open_body)
        self.assertIn("request.volume = currentLot;", open_body)
        # The request initially gets a provisional volume, then is overwritten
        # with the risk-adjusted volume after ApplyRiskSizing, before OrderSend.
        self.assertLess(open_body.index("if(!ApplyRiskSizing("),
                        open_body.rindex("request.volume = currentLot;"))
        self.assertIn("return (lossAtMinLot <= AccountInfoDouble(ACCOUNT_EQUITY) * MaxRiskPerTradePct / 100.0 + 1e-9) ? minLot : 0;", code)
        self.assertIn("if(sized == 0)", code)
        self.assertIn("return false;", code[code.index("if(sized == 0)"):code.index("if(lossAtMinLot > riskMoney)")])

    def test_no_false_promise_for_small_account(self):
        text = TRIAL.read_text(encoding="utf-8")
        self.assertIn("LIVE LOCKED", text)
        self.assertIn("Broker stop gaps CAN exceed modeled cap", text)
        self.assertNotIn("RiskPerTradePct=2.0", text)


if __name__ == "__main__":
    unittest.main()
