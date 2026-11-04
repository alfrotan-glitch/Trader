#!/usr/bin/env python3
"""Single-variable historical MT5 spread-cap A/B. Tester-only; LIVE LOCKED."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import traceback
from auto_nyao_stop_recovery import (
    ROOT, CONTROL_EXPERT, PRESET, REQUIRED_ORIGINAL_SHA, GuardFailure, sha256,
    find_mt5, launch_safe_preflight, verify_demo_after_autostart,
    compile_tester_control, make_tester_ini, run_tester_pass, copy_report,
    validated_native_report, native_deal_rows, write_utf16, close_terminal,
    reopen_terminal, capture_filtered_logs, pack_evidence,
)

OUT = ROOT / "local_runs" / "spread_gate"
SOURCE_PRESET = ROOT / "research" / "fresh_entry" / PRESET
BASE_SHA256 = "01ff7552131c2601e08718d5ec6a3223578a69c33f67d59cfd76d10effe79089"
INPUT = "MaxSpreadPoints"
FORWARD_START = dt.date(2026, 11, 5)  # First FULL UTC day after freeze, never tune on it
MIN_FORWARD_DAYS = 30


def derive_forward_dates(today_utc: dt.date | None = None) -> tuple[str, str]:
    """Prospective boundary fixed at design time; use only settled UTC days.

    UTC-2-day end is conservative with an unverified broker-server timezone.
    Native report period and local price-history coverage are checked later.
    """
    today_utc = today_utc or dt.datetime.now(dt.timezone.utc).date()
    last_settled = today_utc - dt.timedelta(days=2)
    days = (last_settled - FORWARD_START).days
    if days < MIN_FORWARD_DAYS:
        raise GuardFailure(
            f"WAITING_FOR_FUTURE_DATA: need >= {MIN_FORWARD_DAYS} elapsed "
            f"settled days from {FORWARD_START.isoformat()}; "
            f"latest safe UTC end is {last_settled.isoformat()}. "
            "Do not backfill dates from the inspected 2026 sample."
        )
    return FORWARD_START.strftime("%Y.%m.%d"), last_settled.strftime("%Y.%m.%d")




def profile_inputs(content: str) -> dict[str, str]:
    result = {}
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if not re.fullmatch(r"[A-Za-z_]\w*=.*", line):
            raise GuardFailure("Nonstandard .set line: " + line[:80])
        name, value = line.split("=", 1)
        if name in result:
            raise GuardFailure("Duplicate setting: " + name)
        result[name] = value
    return result


def frozen_profiles(content: str) -> tuple[str, str]:
    values = profile_inputs(content)
    required = {
        "RiskPerTradePct": "0.0", "EnableDynamicLots": "false",
        "BaseLotSize": "0.01", "MaxRiskPerTradePct": "1.0",
        "MinEfficiencyToTrade": "0.15", "EnableMaxSpreadFilter": "true",
        "EnableCheckpointExit": "true", "EnableRiskReward": "false",
        "MaxOpenOrders": "1", "PointInputDigits": "3",
        INPUT: "500",
    }
    if len(values) != 172 or any(values.get(k) != v for k, v in required.items()):
        raise GuardFailure("Frozen 172-input fixed-lot baseline did not match")
    trial = re.sub(r"(?m)^MaxSpreadPoints=500\s*$", "MaxSpreadPoints=400", content)
    new = profile_inputs(trial)
    if len(new) != 172 or {k for k in values if values[k] != new[k]} != {INPUT}:
        raise GuardFailure("Trial changed more than the one spread input")
    return content, trial


def config_for(login: int, server: str, label: str, name: str,
               dates: tuple[str, str] | None = None) -> str:
    config = make_tester_ini(login, server, label, CONTROL_EXPERT)
    expected = f"ExpertParameters={PRESET}"
    if config.count(expected) != 1 or not name.startswith("Trader_SPREAD_"):
        raise GuardFailure("Could not pin trial .set name")
    config = config.replace(expected, f"ExpertParameters={name}")
    if dates is not None:
        start, end = dates
        if start != FORWARD_START.strftime("%Y.%m.%d"):
            raise GuardFailure("Out-of-sample start cannot be moved into inspected history")
        if not re.fullmatch(r"\d{4}\.\d\d\.\d\d", end):
            raise GuardFailure("Invalid forward end date")
        if (dt.datetime.strptime(end, "%Y.%m.%d").date() - FORWARD_START).days < MIN_FORWARD_DAYS:
            raise GuardFailure("Insufficient forward data duration")
        for name, value in (("FromDate", start), ("ToDate", end)):
            original = re.search(rf"(?m)^{name}=\d{{4}}\.\d\d\.\d\d$", config)
            if original is None:
                raise GuardFailure("Missing or ambiguous tester date: " + name)
            config = config.replace(original.group(0), f"{name}={value}", 1)
    return config


def verify_future_history_coverage(terminal: Path, dates: tuple[str, str]) -> dict:
    """Check that broker M5 history covers both edges before replays."""
    import MetaTrader5 as mt5
    if not mt5.initialize(path=str(terminal), timeout=30000):
        raise GuardFailure("MT5 API cannot inspect future-period tick/bar availability")
    try:
        begin = dt.datetime.strptime(dates[0], "%Y.%m.%d").replace(tzinfo=dt.timezone.utc)
        finish = dt.datetime.strptime(dates[1], "%Y.%m.%d").replace(
            tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
        bars = mt5.copy_rates_range("XAUUSD@", mt5.TIMEFRAME_M5, begin, finish)
        if bars is None or len(bars) < 500:
            raise GuardFailure("Insufficient broker historical M5 candles for future period")
        first = dt.datetime.fromtimestamp(int(bars[0]["time"]), dt.timezone.utc)
        last = dt.datetime.fromtimestamp(int(bars[-1]["time"]), dt.timezone.utc)
        if first > begin + dt.timedelta(days=4) or last < finish - dt.timedelta(days=5):
            raise GuardFailure("Historical M5 feed missing a window edge; reject replay")
        return {
            "m5_candles_observed": len(bars),
            "first_bar_utc": first.isoformat(),
            "last_bar_utc": last.isoformat(),
            "scope_note": "Edge checks only; native Strategy Tester must independently report 100% real tick quality",
        }
    finally:
        mt5.shutdown()


def validate_pair(control_path: Path, trial_path: Path,
                  expected_dates: tuple[str, str] | None = None) -> dict:
    base, b = validated_native_report(control_path)
    trial, t = validated_native_report(trial_path)
    diffs = {k: [b.get(k), t.get(k)] for k in b.keys() | t.keys()
             if b.get(k) != t.get(k)}
    if len(b) != 171 or len(t) != 171 or set(diffs) != {INPUT}:
        raise GuardFailure("Native HTML has 171 enumerated inputs or A/B differs by more than spread")
    if float(b[INPUT]) != 500 or float(t[INPUT]) != 400:
        raise GuardFailure("Native HTML did not apply intended spread values")
    if base.get("tested_range") != trial.get("tested_range"):
        raise GuardFailure("Native report test windows differ")
    if expected_dates is not None:
        expected_label = f"({expected_dates[0]} - {expected_dates[1]})"
        if expected_label not in str(base.get("tested_range", "")):
            raise GuardFailure("Native report did not use preregistered future-only dates")
    a_deals, b_deals = native_deal_rows(control_path), native_deal_rows(trial_path)
    if len(a_deals) != 2 * base["trades"] or len(b_deals) != 2 * trial["trades"]:
        raise GuardFailure("Native deal table does not reconcile to trade counts")
    return {
        "baseline": base, "trial": trial,
        "only_native_input_difference": diffs,
        "control_deal_rows": len(a_deals),
        "trial_deal_rows": len(b_deals),
        "native_ledgers_identical": a_deals == b_deals,
        "delta_net_usd": round(trial["net"] - base["net"], 2),
        "previous_709_reference_reproduced": (
            base["trades"] == 709 and abs(base["net"] - 1091.44) <= .02
        ),
        "warning": "In-sample, post-selection A/B; NOT unseen/live validation",
    }


def run(args: argparse.Namespace) -> int:
    if os.name != "nt":
        print("Windows / installed DEMO MetaTrader 5 required", file=sys.stderr)
        return 2
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    run_dir = OUT / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    zip_path = ROOT / f"NYAO_SPREAD_GATE_EVIDENCE_{stamp}.zip"
    state: dict = {
        "verdict": "FAILED_CLOSED__LIVE_LOCKED",
        "experiment": "ONE entry spread gate, 500 baseline vs 400 trial",
        "symbol": "XAUUSD@", "period": "M5",
        "dates": ["2026.01.01", "2026.11.02"],
        "initial_deposit_usd": 3000, "live_trading_permitted": False,
        "errors": [],
    }
    log = run_dir / "runner.log"

    def note(message: str) -> None:
        print(message, flush=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(message + "\n")

    started = time.time()
    zip_packaging_failed = False
    terminal, data = None, None
    auto_started, closed_for_tests, was_running = False, False, False
    installed: list[Path] = []
    try:
        dates = derive_forward_dates() if args.forward else None
        if dates is not None:
            state["experiment"] = "PREREGISTERED_UNSEEN_REPLAY_500_VS_400__LIVE_LOCKED"
            state["dates"] = list(dates)
            state["window_scope"] = "UTC-2 settled retrospective replay, NOT live DEMO execution"
            note("Future-only historical window: " + dates[0] + " -> " + dates[1])
        vendor = ROOT / "nyao_scalper.mq5"
        if sha256(vendor) not in REQUIRED_ORIGINAL_SHA:
            raise GuardFailure("Original EA SHA changed: abort")
        if sha256(SOURCE_PRESET) != BASE_SHA256:
            raise GuardFailure("Frozen .set SHA changed: abort")
        base_text, trial_text = frozen_profiles(SOURCE_PRESET.read_text("utf-8-sig"))
        terminal, data = find_mt5(args.data_folder)
        note("Verifying DEMO account with zero positions/orders...")
        auto_started = launch_safe_preflight(terminal, run_dir)
        login, server = verify_demo_after_autostart(terminal, data, auto_started)
        was_running = True
        state["demo_verified"] = True
        state["demo_server"] = server
        note("PASS: WMMarkets DEMO, no positions/orders")
        if dates is not None:
            state["future_history_coverage"] = verify_future_history_coverage(terminal, dates)
            note("PASS: independent broker M5 history coverage at window edges")
        expert = compile_tester_control(terminal, data, vendor, run_dir)
        state["source_sha256"] = sha256(vendor)
        state["guarded_control_ex5_sha256"] = sha256(expert)
        profiles = data / "MQL5" / "Profiles" / "Tester"
        profiles.mkdir(parents=True, exist_ok=True)
        names = [f"Trader_SPREAD_BASE_{stamp}.set", f"Trader_SPREAD_TRIAL_{stamp}.set"]
        for name, content in zip(names, (base_text, trial_text)):
            p = profiles / name
            if p.exists():
                raise GuardFailure("Refusing to overwrite run-unique .set file")
            p.write_text(content, "utf-8")
            installed.append(p)
            shutil.copy2(p, run_dir / name)
        suffix = stamp.replace("_", "")
        labels = ["NYAO_STOP_SPREAD_BASE_" + suffix,
                  "NYAO_STOP_SPREAD_TRIAL_" + suffix]
        ini_names = ["private_base.ini", "private_trial.ini"]
        for name, label, ini in zip(names, labels, ini_names):
            write_utf16(run_dir / ini, config_for(login, server, label, name, dates))
        if not close_terminal(terminal, wait_s=120):
            raise GuardFailure("Cannot close DEMO terminal safely")
        closed_for_tests = True
        reports = []
        for label, ini, folder, caption in zip(
            labels, ini_names, ("native_baseline", "native_trial"),
            ("BASE 500", "TRIAL 400")
        ):
            note("Running native real-tick test: " + caption)
            since, rc = run_tester_pass(terminal, run_dir / ini, args.max_minutes, caption)
            if rc != 0:
                raise GuardFailure(f"Strategy Tester returned {rc} on {caption}")
            reports.append(copy_report(data, terminal, label, run_dir / folder, since))
        evidence = validate_pair(*reports, expected_dates=dates)
        sys.path.insert(0, str(ROOT / "research" / "spread_gate"))
        from analyze_stop_slippage import compare_reports
        state["stop_execution_forensics"] = compare_reports(reports[0], reports[1])
        (run_dir / "stop_execution_forensics.json").write_text(
            json.dumps(state["stop_execution_forensics"], indent=2) + "\n", encoding="utf-8"
        )
        state["comparison"] = evidence
        state["candidate_risk_review"] = {
            "equity_dd_delta_percentage_points": round(
                evidence["trial"]["dd_pct"] - evidence["baseline"]["dd_pct"], 2
            ),
            "candidate_promoted": False,
            "reason": "In-sample improvement alone cannot validate forward profitability; inspect drawdown and trade concentration",
        }
        if dates is not None:
            state["verdict"] = (
                "UNSEEN_PERIOD_REPLAY_VALID__NO_LIVE_APPROVAL__LIVE_LOCKED"
                if min(evidence["baseline"]["trades"], evidence["trial"]["trades"]) >= 50
                else "UNSEEN_PERIOD_REPLAY_TOO_FEW_TRADES__LIVE_LOCKED"
            )
            note("Future-period historical replay, NOT prospective DEMO order execution.")
        else:
            state["verdict"] = (
                "HISTORICAL_AB_VALID__FORWARD_NOT_VALIDATED__LIVE_LOCKED"
                if evidence["previous_709_reference_reproduced"] else
                "HISTORICAL_AB_VALID__BASELINE_DRIFT__LIVE_LOCKED"
            )
        note(f"Control net USD {evidence['baseline']['net']:.2f}, "
             f"trial net USD {evidence['trial']['net']:.2f}, "
             f"delta USD {evidence['delta_net_usd']:+.2f}")
        note(f"Equity max DD: {evidence['baseline']['dd_pct']:.2f}% -> "
             f"{evidence['trial']['dd_pct']:.2f}% (not approved for live)")
        note("HISTORICAL ONLY: no forward validation, no live approval")
    except (Exception, KeyboardInterrupt) as exc:
        state["errors"].append(f"{type(exc).__name__}: {exc}")
        (run_dir / "failure_trace.txt").write_text(traceback.format_exc(), "utf-8")
        note(f"FAIL CLOSED: {type(exc).__name__}: {exc}")
    finally:
        if terminal is not None and data is not None:
            try:
                capture_filtered_logs(data, run_dir, started)
            except Exception as exc:
                state["errors"].append(f"journal_capture: {type(exc).__name__}")
        for p in installed:
            try:
                if p.exists() and sha256(p) == sha256(run_dir / p.name):
                    p.unlink()
            except OSError:
                state["errors"].append("Temporary .set cleanup failed")
        if terminal is not None:
            try:
                if auto_started:
                    if not closed_for_tests:
                        close_terminal(terminal, wait_s=30)
                    note("Auto-started MT5 not reopened in chart mode")
                elif closed_for_tests and was_running:
                    reopen_terminal(terminal)
                    note("Existing DEMO MT5 reopened")
            except Exception as exc:
                state["errors"].append(f"terminal_restore: {type(exc).__name__}")
        state["elapsed_seconds"] = round(time.time() - started, 1)
        state["files_sha256"] = {
            p.relative_to(run_dir).as_posix(): sha256(p)
            for p in run_dir.rglob("*") if p.is_file()
            and not p.name.startswith("private_")
            and p.name not in ("manifest.json", "runner.log")
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", "utf-8")
        (run_dir / "READ_ME_FIRST.txt").write_text(
            "Research only: unchanged original guarded EA, spread 500 vs 400.\n"
            f"VERDICT: {state['verdict']}\n"
            "LIVE LOCKED. Native HTML may disclose DEMO account number.\n", "utf-8")
        try:
            pack_evidence(run_dir, zip_path)
            note("Upload this ONE evidence ZIP: " + str(zip_path))
            note("VERDICT: " + state["verdict"])
        except Exception as exc:
            zip_packaging_failed = True
            note(f"ZIP failure: {exc}; results retained at {run_dir}")
    if zip_packaging_failed:
        return 3
    return 0 if state["verdict"].startswith((
        "HISTORICAL_AB_VALID", "UNSEEN_PERIOD_REPLAY_VALID"
    )) else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forward", action="store_true",
                        help="Replay only preregistered Nov 5+ unseen dates, after 30 settled days")
    parser.add_argument("--data-folder", default="")
    parser.add_argument("--max-minutes", type=int, default=240)
    args = parser.parse_args()
    if not 5 <= args.max_minutes <= 1440:
        parser.error("--max-minutes must be between 5 and 1440")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
