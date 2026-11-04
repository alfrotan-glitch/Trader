#!/usr/bin/env python3
"""Verify exact post-stop tick evidence from the tester-only Nyao diagnostic.

Read-only. The observer never opens real orders and this analyzer does not
estimate missing ticks. Broker-server timestamps stay as integer milliseconds.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

COLUMNS = (
    "schema", "ticket", "symbol", "period", "direction",
    "entry_time", "entry_price", "exit_price", "net_usd",
    "checkpoint_distance_price", "exit_time_ms", "window_end_ms",
    "first_observed_tick_ms", "last_observed_tick_ms", "observed_ticks",
    "first_return_to_entry_ms", "first_plus5_ms", "first_checkpoint_ms",
    "max_adverse_before_return_price", "max_additional_adverse_after_exit_price",
    "max_favorable_after_exit_price", "status",
)
WINDOWS = {"1h": 3600000, "4h": 14400000, "24h": 86400000}
STATUSES = {"WINDOW_ELAPSED", "NO_TICKS_IN_WINDOW", "CENSORED_TEST_END"}


def read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or tuple(reader.fieldnames) != columns:
            raise ValueError(
                f"Schema mismatch: expected {columns}, got {reader.fieldnames}"
            )
        rows = list(reader)
    if not rows:
        raise ValueError(f"No evidence rows in {path}")
    if any(None in row for row in rows):
        raise ValueError("Extra CSV fields detected")
    return rows


def parse_ms(value: str) -> int | None:
    if value == "":
        return None
    result = int(value)
    if result <= 0:
        raise ValueError(f"Bad millisecond timestamp: {value}")
    return result


def analyze(
    stop_csv: Path,
    entry_csv: Path | None = None,
    expected_stops: int | None = None,
) -> dict:
    rows = read_csv(stop_csv, COLUMNS)
    tickets: set[str] = set()
    details = []
    counts = Counter()
    hits = {threshold: {w: 0 for w in WINDOWS} for threshold in
            ("first_return_to_entry_ms", "first_plus5_ms", "first_checkpoint_ms")}
    observations = 0
    for r in rows:
        ticket = r["ticket"]
        if not ticket or ticket in tickets:
            raise ValueError(f"Empty or duplicate stop ticket: {ticket!r}")
        tickets.add(ticket)
        if r["schema"] != "1" or r["direction"] not in ("BUY", "SELL"):
            raise ValueError(f"Invalid row schema or direction: {ticket}")
        if r["symbol"] != "XAUUSD@" or r["period"] != "PERIOD_M5":
            raise ValueError(f"Unexpected symbol/timeframe for ticket {ticket}")
        if float(r["net_usd"]) >= -0.005:
            raise ValueError(f"Not a losing SL-close: {ticket}")
        if float(r["checkpoint_distance_price"]) <= 0:
            raise ValueError(f"Missing checkpoint distance: {ticket}")
        for field in ("max_adverse_before_return_price",
                      "max_additional_adverse_after_exit_price",
                      "max_favorable_after_exit_price"):
            if float(r[field]) < 0:
                raise ValueError(f"Negative price excursion for {ticket}/{field}")
        status = r["status"]
        if status not in STATUSES:
            raise ValueError(f"Invalid window status for {ticket}: {status}")
        counts[status] += 1
        exit_ms = parse_ms(r["exit_time_ms"])
        end_ms = parse_ms(r["window_end_ms"])
        if exit_ms is None or end_ms != exit_ms + WINDOWS["24h"]:
            raise ValueError(f"Wrong exit timestamp or window for {ticket}")
        first = parse_ms(r["first_observed_tick_ms"])
        last = parse_ms(r["last_observed_tick_ms"])
        ticks = int(r["observed_ticks"])
        if ticks < 0 or (ticks == 0) != (first is None or last is None):
            raise ValueError(f"Tick coverage fields contradict for {ticket}")
        if ticks > 0 and not (exit_ms < first <= last <= end_ms):
            raise ValueError(f"Tick times out of 24h post-exit window for {ticket}")
        if ticks == 0 and status == "WINDOW_ELAPSED":
            raise ValueError(f"Window elapsed but no ticks for {ticket}")
        observations += ticks
        times = {}
        for field in hits:
            t = parse_ms(r[field])
            if t is not None:
                if ticks == 0 or first is None or last is None or not (first <= t <= last):
                    raise ValueError(f"Threshold tick is not observed for {ticket}/{field}")
                for label, length in WINDOWS.items():
                    if 0 < t - exit_ms <= length:
                        hits[field][label] += 1
            times[field] = t
        if times["first_plus5_ms"] is not None and (
            times["first_return_to_entry_ms"] is None or
            times["first_plus5_ms"] < times["first_return_to_entry_ms"]
        ):
            raise ValueError(f"+5 happened before returning to entry: {ticket}")
        if times["first_checkpoint_ms"] is not None and (
            times["first_return_to_entry_ms"] is None or
            times["first_checkpoint_ms"] < times["first_return_to_entry_ms"]
        ):
            raise ValueError(f"Checkpoint happened before entry return: {ticket}")
        details.append({
            "ticket": ticket, "side": r["direction"],
            "entry_price": float(r["entry_price"]),
            "exit_price": float(r["exit_price"]),
            "stop_loss_usd": float(r["net_usd"]),
            "exit_time_ms_broker": exit_ms,
            "status": status, "ticks_observed": ticks,
            "return_to_entry_after_sec": None if times["first_return_to_entry_ms"] is None
                else round((times["first_return_to_entry_ms"] - exit_ms) / 1000, 3),
            "plus5_after_sec": None if times["first_plus5_ms"] is None
                else round((times["first_plus5_ms"] - exit_ms) / 1000, 3),
            "checkpoint_after_sec": None if times["first_checkpoint_ms"] is None
                else round((times["first_checkpoint_ms"] - exit_ms) / 1000, 3),
            "max_adverse_before_entry_return_price":
                float(r["max_adverse_before_return_price"]),
            "max_additional_adverse_after_exit_price":
                float(r["max_additional_adverse_after_exit_price"]),
            "max_favorable_after_exit_price":
                float(r["max_favorable_after_exit_price"]),
        })

    match = None
    if entry_csv:
        # This comparison prevents silently treating an incomplete watch list
        # as a measured 24h reversal rate for all losses.
        with entry_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"ticket", "exit_reason_code", "net_profit_usd", "status"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("Missing entry-diagnostic columns")
            entry_rows = list(reader)
        if any(r.get("status") != "CLOSED" for r in entry_rows):
            raise ValueError("Incomplete entry evidence; cannot reconcile")
        targets = {r["ticket"] for r in entry_rows
                   if r["exit_reason_code"] == "4" and
                   float(r["net_profit_usd"]) < -0.005}  # MQL5 DEAL_REASON_SL
        match = {
            "eligible_negative_broker_sl": len(targets),
            "missing_stop_watches": sorted(targets - tickets),
            "unexpected_stop_watches": sorted(tickets - targets),
        }
    if expected_stops is not None and len(tickets) != expected_stops:
        raise ValueError(
            f"Expected {expected_stops} negative broker SL records, found {len(tickets)}"
        )
    reconciled = (match is None or (
        not match["missing_stop_watches"] and not match["unexpected_stop_watches"]
    ))
    full = all(r["status"] == "WINDOW_ELAPSED" for r in rows)
    verdict = ("RECONCILED_24H_OBSERVED" if reconciled and full
               else "RECONCILED_WITH_CENSORED_OR_GAPS" if reconciled
               else "INCOMPLETE_EVIDENCE")
    return {
        "verdict": verdict,
        "scope": "historical tester-side BID/ASK observations after confirmed losing SL",
        "data_warning": "Missing post-stop ticks or censored windows cannot prove no rebound.",
        "stop_count": len(rows),
        "status_counts": dict(counts),
        "total_observed_tick_samples": observations,
        "confirmed_hit_counts_minimum": hits,
        "entry_reconciliation": match,
        "positions": details,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", type=Path, help="NYAO_STOP_RECOVERY_TICKS.csv")
    p.add_argument("--entry-csv", type=Path, help="NYAO_ENTRY_DIAGNOSTICS.csv")
    p.add_argument("--expected-stops", type=int, help="Optional expected eligible stop count")
    p.add_argument("--output", type=Path, help="Optional full JSON report path")
    args = p.parse_args()
    try:
        result = analyze(args.csv, args.entry_csv, args.expected_stops)
    except (ValueError, OSError, TypeError) as exc:
        print(f"INCOMPLETE_EVIDENCE: {exc}")
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "positions"},
                     indent=2, ensure_ascii=False))
    return 0 if result["verdict"] != "INCOMPLETE_EVIDENCE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
