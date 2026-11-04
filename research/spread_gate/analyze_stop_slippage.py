#!/usr/bin/env python3
"""Read-only native MT5 exit-price vs stop-request forensics.

This measures slippage on *executed* stop exits, not stop-loss placement quality.
It does not guess counterfactual fills, spread or profit effects.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re

from backtest.nyao_backtest import read_text_any


def parse_executed_stops(path: Path) -> dict:
    source = read_text_any(path)
    entries: list[dict] = []
    native_exits = 0
    for block in re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", source):
        cells = [
            html.unescape(re.sub(r"(?is)<[^>]*>", "", c))
                .replace("\xa0", " ").strip()
            for c in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", block)
        ]
        if len(cells) != 13 or cells[4] != "out":
            continue
        native_exits += 1
        match = re.fullmatch(r"(?i)sl\s+(\d+(?:\.\d+)?)", cells[12])
        if not match:
            continue
        if cells[3] not in ("buy", "sell"):
            raise ValueError("Unexpected closing deal side")
        if cells[2] != "XAUUSD@":
            raise ValueError("Unexpected symbol in stop audit")
        stop_price = float(match.group(1))
        fill = float(cells[6].replace(" ", ""))
        net = float(cells[10].replace(" ", ""))
        volume = float(cells[5])
        if stop_price <= 0 or fill <= 0 or volume <= 0:
            raise ValueError("Invalid stop/exit price or deal volume")
        # A BUY closing deal exits an old SELL; ASK above stop is adverse.
        # A SELL closing deal exits an old BUY; BID below stop is adverse.
        adverse_delta = (fill-stop_price if cells[3] == "buy"
                         else stop_price-fill)
        entries.append({
            "closed_at_broker_time": cells[0], "deal_id": cells[1],
            "closing_side": cells[3], "lot": volume,
            "stop_price_in_comment": stop_price, "executed_price": fill,
            "adverse_slippage_quote_units": round(adverse_delta, 4),
            "net_profit_usd": round(net, 2),
        })
    if not native_exits or len(entries) < 1:
        raise ValueError("Native report exits / SL comments absent; no slippage claim")
    adverse = [e for e in entries if e["adverse_slippage_quote_units"] > .0001]
    worst = sorted(entries,
                   key=lambda e: e["adverse_slippage_quote_units"], reverse=True)
    return {
        "scope": "native executed closing deals tagged SL; comment stop versus deal fill",
        "limitations": "SL comments may be profitable from moved stops; price gap does not establish its cause; excludes fills not tagged SL",
        "all_native_exits": native_exits, "stop_tagged_exits": len(entries),
        "adverse_over_1_quote_unit": sum(e["adverse_slippage_quote_units"] > 1 for e in entries),
        "adverse_over_5_quote_units": sum(e["adverse_slippage_quote_units"] > 5 for e in entries),
        "adverse_over_10_quote_units": sum(e["adverse_slippage_quote_units"] > 10 for e in entries),
        "worst_adverse_slippage_quote_units": max(e["adverse_slippage_quote_units"] for e in entries),
        "largest_10_adverse_exits": worst[:10],
    }


def compare_reports(base: Path, trial: Path) -> dict:
    return {
        "baseline": parse_executed_stops(base),
        "trial": parse_executed_stops(trial),
        "interpretation": "Read-only diagnostics; neither spread gating nor stopping can guarantee execution at requested SL on market gaps",
        "live_approved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_html", type=Path)
    parser.add_argument("trial_html", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = compare_reports(args.baseline_html, args.trial_html)
    except (OSError, ValueError) as exc:
        print("INCOMPLETE_EVIDENCE: " + str(exc))
        return 2
    content = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content, encoding="utf-8")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
