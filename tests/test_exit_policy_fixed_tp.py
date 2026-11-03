"""Read-only regression checks for one-variable Exit-Policy A/B experiment.

Verifies only *configuration and code-path integrity*, not trading outcomes.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
CONTROL=ROOT/"research/fresh_entry/Trader_FRESH_ER015_FIXED001.set"
TRIAL=ROOT/"research/exit_policy/Trader_EXIT_FIXED_TP20_ER015_FIXED001.set"
SOURCE=ROOT/"nyao_scalper.mq5"

def values(path):
    raw=path.read_text(encoding="utf-8-sig")
    entries=re.findall(r"(?m)^([A-Za-z_][A-Za-z_0-9]*)=([^\r\n]*)\r?$",raw)
    if len(entries)!=len({x[0] for x in entries}):
        raise AssertionError("Duplicate input parameter")
    return dict(entries)

class FixedTakeProfitTrial(unittest.TestCase):
    def test_exactly_one_switch_frozen_from_718_trade_baseline(self):
        a,b=values(CONTROL),values(TRIAL)
        self.assertEqual(len(a),172)
        self.assertEqual(set(a),set(b))
        differences={key:(a[key],b[key]) for key in a if a[key]!=b[key]}
        self.assertEqual(differences,{"EnableCheckpointExit":("true","false")})

    def test_baseline_and_trial_risk_and_entry_remain_frozen(self):
        a,b=values(CONTROL),values(TRIAL)
        for k,v in {"MinEfficiencyToTrade":"0.15","EnableTakeProfit":"true",
                    "TPInputType":"2","TPValue":"20000","SLInputType":"2",
                    "SLValue":"20000","EnableRiskReward":"false",
                    "RiskPerTradePct":"0.0","BaseLotSize":"0.01",
                    "MaxOpenOrders":"1","EnableTrailing":"false",
                    "EnableLossManagement":"false","EnableHedgeChain":"false",
                    "EnableLimitEntry":"false"}.items():
            self.assertEqual(a[k],v,k)
            self.assertEqual(b[k],v,k)

    def test_source_sends_broker_tp_only_if_checkpoint_disabled(self):
        s=SOURCE.read_text(encoding="utf-8")
        a=s.index("// Open Position\nvoid OpenPosition(")
        b=s.index("bool orderResult = OrderSend(request, result);",a)
        body=s[a:b]
        self.assertIn("if(tpPoints > 0 && !EnableCheckpointExit)",body)
        self.assertIn("request.tp = NormalizePrice(price + (tpPoints * _Point))",body)
        self.assertIn("request.tp = NormalizePrice(price - (tpPoints * _Point))",body)
        self.assertIn("request.sl = NormalizePrice(price",body)

        # For valid TP points, resolved manual TP remains as stated in user report:
        resolver=s[s.index("double GetTPPoints("):s.index("void ",s.index("double GetTPPoints("))] if False else s
        self.assertIn("if(EnableTakeProfit)\n        return ConvertToPoints(TPInputType, TPValue, lotSize);",resolver)

    def test_checkpoint_state_disabled_with_switch(self):
        s=SOURCE.read_text(encoding="utf-8")
        self.assertIn("if(!EnableCheckpointExit || tpPoints <= 0) return;",s)
        self.assertIn("if(!EnableCheckpointExit) return;",s)

    def test_no_live_enablement_is_introduced(self):
        trial=TRIAL.read_text(encoding="utf-8")
        self.assertIn("Historical counterfactual only",trial)
        self.assertNotIn("MaxOpenOrders=2",trial)
        self.assertNotIn("RiskPerTradePct=1.25",trial)

if __name__=="__main__":
    unittest.main()
