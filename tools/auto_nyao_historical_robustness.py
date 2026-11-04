#!/usr/bin/env python3
"""One-click, historical-only native MT5 regime stress test: Nyao 500 vs 400.

Same guarded original EA, same 172 inputs except entry spread cap.
Four independently reset historical slices; no prospective-performance claims.
Never sends chart/real orders or modifies canonical vendor EA.
"""
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
    ROOT, CONTROL_EXPERT, PRESET, REQUIRED_ORIGINAL_SHA, GuardFailure,
    sha256, find_mt5, launch_safe_preflight, verify_demo_after_autostart,
    compile_tester_control, make_tester_ini, run_tester_pass, copy_report,
    validated_native_report, native_deal_rows, write_utf16, close_terminal,
    reopen_terminal, capture_filtered_logs, pack_evidence,
)
from auto_nyao_spread_gate import (
    SOURCE_PRESET, KNOWN_BASE_SHA256, frozen_profiles, validate_pair,
)

sys.path.insert(0, str(ROOT / "research" / "spread_gate"))
from analyze_stop_slippage import compare_reports

FOLDS = (
    ("Q1", "2026.01.01", "2026.03.31"),
    ("Q2", "2026.04.01", "2026.06.30"),
    ("Q3", "2026.07.01", "2026.08.31"),
    ("Q4", "2026.09.01", "2026.11.02"),
)
OUTPUT = ROOT / "local_runs" / "spread_robustness"


def assert_folds() -> None:
    for i, (name, begin, end) in enumerate(FOLDS):
        if not re.fullmatch(r"Q[1-4]", name):
            raise GuardFailure("Unrecognized historical fold")
        a = dt.datetime.strptime(begin, "%Y.%m.%d").date()
        b = dt.datetime.strptime(end, "%Y.%m.%d").date()
        if b <= a or b >= dt.date(2026, 11, 5):
            raise GuardFailure("Fold crosses future or has nonpositive span")
        if i:
            prev = dt.datetime.strptime(FOLDS[i - 1][2], "%Y.%m.%d").date()
            if prev >= a:
                raise GuardFailure("Historical folds overlap")
    if FOLDS[0][1] != "2026.01.01" or FOLDS[-1][2] != "2026.11.02":
        raise GuardFailure("Frozen historical date plan changed")


def historical_ini(login: int, server: str, report_name: str,
                   profile_name: str, fold: tuple[str, str, str]) -> str:
    if fold not in FOLDS or not profile_name.startswith("Trader_HIST_"):
        raise GuardFailure("Only preregistered historical folds and profiles permitted")
    config = make_tester_ini(login, server, report_name, CONTROL_EXPERT)
    replacements = {
        f"ExpertParameters={PRESET}": f"ExpertParameters={profile_name}",
        "FromDate=2026.01.01": f"FromDate={fold[1]}",
        "ToDate=2026.11.02": f"ToDate={fold[2]}",
    }
    for old, new in replacements.items():
        if config.count(old) != 1:
            raise GuardFailure("Tester configuration key missing or ambiguous")
        config = config.replace(old, new, 1)
    if "AllowLiveTrading=0" not in config or "Model=4" not in config:
        raise GuardFailure("Unsafe or nonreal-tick tester configuration")
    return config


def native_fold_metrics(report_a: Path, report_b: Path,
                        fold: tuple[str, str, str]) -> dict:
    result = validate_pair(report_a, report_b)
    expected = f"({fold[1]} - {fold[2]})"
    for tag in ("baseline", "trial"):
        metrics = result[tag]
        if expected not in str(metrics.get("tested_range", "")):
            raise GuardFailure("MT5 did not execute the exact historical fold")
        if metrics["trades"] < 20:
            raise GuardFailure("Insufficient completed trades for historical fold")
    result["fold"] = {
        "id": fold[0], "start": fold[1], "end": fold[2]
    }
    stops = compare_reports(report_a, report_b)
    result["stop_execution"] = stops
    result["trial_drawdown_delta_pp"] = round(
        result["trial"]["dd_pct"] - result["baseline"]["dd_pct"], 3
    )
    result["trial_net_gain"] = result["delta_net_usd"] > 0.01
    result["trial_drawdown_not_worse"] = result["trial_drawdown_delta_pp"] <= 0.01
    result["trial_gap_not_worse"] = (
        stops["trial"]["worst_adverse_slippage_quote_units"]
        <= stops["baseline"]["worst_adverse_slippage_quote_units"] + .01
    )
    result["limitation"] = (
        "Retrospective in-sample regime stress. Separate MT5 tester runs reset "
        "position state and deposit. Summing fold P&L is not one continuous account."
    )
    return result


def assess_regime_stability(folds: list[dict]) -> dict:
    if len(folds) != len(FOLDS) or [x["fold"]["id"] for x in folds] != [x[0] for x in FOLDS]:
        raise GuardFailure("Not all chronological folds completed; cannot rank candidate")
    improved = sum(x["trial_net_gain"] for x in folds)
    acceptable_dd = sum(x["trial_drawdown_not_worse"] for x in folds)
    acceptable_gap = sum(x["trial_gap_not_worse"] for x in folds)
    base_sum = round(sum(x["baseline"]["net"] for x in folds), 2)
    trial_sum = round(sum(x["trial"]["net"] for x in folds), 2)
    base_gross_profit = sum(x["baseline"]["gross_profit"] for x in folds)
    trial_gross_profit = sum(x["trial"]["gross_profit"] for x in folds)
    base_gross_loss = sum(x["baseline"]["gross_loss"] for x in folds)
    trial_gross_loss = sum(x["trial"]["gross_loss"] for x in folds)
    base_pf = (round(base_gross_profit / abs(base_gross_loss), 4)
               if base_gross_loss < 0 else None)
    trial_pf = (round(trial_gross_profit / abs(trial_gross_loss), 4)
                if trial_gross_loss < 0 else None)
    strict = (improved >= 3 and acceptable_dd >= 3
              and acceptable_gap >= 3 and trial_sum > base_sum
              and base_pf is not None and trial_pf is not None
              and trial_pf > base_pf
              and max(x["trial_drawdown_delta_pp"] for x in folds) <= 1.0)
    return {
        "verdict": (
            "HISTORICAL_STRESS_CANDIDATE_FOR_DEMO_CHART_REVIEW_ONLY"
            if strict else "HISTORICAL_STRESS_NO_ROBUST_IMPROVEMENT"
        ),
        "live_trading_approved": False,
        "tested_windows": len(folds),
        "trial_outperformed_net_in_windows": improved,
        "trial_dd_not_worse_in_windows": acceptable_dd,
        "trial_extreme_stop_gap_not_worse_in_windows": acceptable_gap,
        "fold_net_sum_usd_baseline": base_sum,
        "fold_net_sum_usd_trial": trial_sum,
        "pooled_pf_baseline": base_pf,
        "pooled_pf_trial": trial_pf,
        "worst_dd_pct_baseline": max(x["baseline"]["dd_pct"] for x in folds),
        "worst_dd_pct_trial": max(x["trial"]["dd_pct"] for x in folds),
        "warning": (
            "Fold sums are descriptive only, because each test starts at $3000. "
            "All 2026 market history informed prior strategy research. "
            "Passing stress criteria never proves future profitability or authorizes REAL trading."
        ),
    }


def run(args: argparse.Namespace) -> int:
    if os.name != "nt":
        print("Native Windows MT5 DEMO required; no simulated PASS", file=sys.stderr)
        return 2
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    session = OUTPUT / stamp
    session.mkdir(parents=True, exist_ok=False)
    zip_path = ROOT / f"NYAO_HISTORICAL_STRESS_EVIDENCE_{stamp}.zip"
    manifest = {
        "verdict": "FAILED_CLOSED__LIVE_LOCKED",
        "kind": "Native historical-only XAUUSD@ M5 100pct-real-tick paired regime stress",
        "folds_preregistered": FOLDS,
        "live_trading_allowed": False,
        "real_orders_submitted": False,
        "errors": [],
        "fold_results": [],
    }
    log = session / "runner.log"

    def note(message: str) -> None:
        print(message, flush=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(message + "\n")

    started = time.time()
    terminal = data = None
    auto_started = closed_for_tests = was_running = False
    profiles: list[Path] = []
    packaged = False
    try:
        assert_folds()
        vendor = ROOT / "nyao_scalper.mq5"
        if sha256(vendor) not in REQUIRED_ORIGINAL_SHA:
            raise GuardFailure("Canonical EA source was modified; abort")
        if sha256(SOURCE_PRESET) not in KNOWN_BASE_SHA256:
            raise GuardFailure("Frozen research .set hash changed; abort")
        base, trial = frozen_profiles(SOURCE_PRESET.read_text(encoding="utf-8-sig"))
        terminal, data = find_mt5(args.data_folder)
        note("Checking WMMarkets DEMO account, flat positions and orders...")
        auto_started = launch_safe_preflight(terminal, session)
        login, server = verify_demo_after_autostart(terminal, data, auto_started)
        was_running = True
        manifest["demo_account_verified"] = True
        note("PASS: DEMO-only and zero open positions/orders")
        ex5 = compile_tester_control(terminal, data, vendor, session)
        manifest["source_sha256"] = sha256(vendor)
        manifest["guarded_control_ex5_sha256"] = sha256(ex5)
        manifest["preset_source_sha256"] = sha256(SOURCE_PRESET)
        names = [f"Trader_HIST_BASE_{stamp}.set",
                 f"Trader_HIST_TRIAL_{stamp}.set"]
        target = data / "MQL5" / "Profiles" / "Tester"
        target.mkdir(parents=True, exist_ok=True)
        for name, content in zip(names, (base, trial)):
            p = target / name
            if p.exists():
                raise GuardFailure("Run-specific .set already exists; refusing overwrite")
            p.write_text(content, encoding="utf-8")
            profiles.append(p)
            shutil.copy2(p, session / name)
        runplan = []
        for fold in FOLDS:
            for variant, profile in zip(("BASE", "TRIAL"), names):
                label = f"NYAO_STOP_HIST_{fold[0]}_{variant}_{stamp.replace('_', '')}"
                ini_name = f"private_{fold[0]}_{variant}.ini"
                write_utf16(session / ini_name,
                            historical_ini(login, server, label, profile, fold))
                runplan.append((fold, variant, label, ini_name))
        if not close_terminal(terminal, wait_s=120):
            raise GuardFailure("Could not close DEMO terminal without force")
        closed_for_tests = True
        reports: dict[str, Path] = {}
        for position, (fold, variant, label, ini) in enumerate(runplan, start=1):
            key = f"{fold[0]}_{variant}"
            note(f"[{position}/{len(runplan)}] Historical real-ticks {key}...")
            test_started, exit_code = run_tester_pass(
                terminal, session / ini, args.max_minutes, key
            )
            if exit_code != 0:
                raise GuardFailure(f"Native MT5 Strategy Tester exited {exit_code} on {key}")
            reports[key] = copy_report(
                data, terminal, label, session / "native" / key, test_started
            )
            if variant == "TRIAL":
                control = reports[f"{fold[0]}_BASE"]
                result = native_fold_metrics(control, reports[key], fold)
                manifest["fold_results"].append(result)
                (session / "partial_fold_results.json").write_text(
                    json.dumps(manifest["fold_results"], indent=2) + "\n", "utf-8"
                )
                note(f"{fold[0]}: BASE USD {result['baseline']['net']:.2f}; "
                     f"TRIAL USD {result['trial']['net']:.2f}; "
                     f"DD % {result['baseline']['dd_pct']:.2f} -> "
                     f"{result['trial']['dd_pct']:.2f}")
        assessment = assess_regime_stability(manifest["fold_results"])
        manifest["assessment"] = assessment
        manifest["verdict"] = assessment["verdict"] + "__LIVE_LOCKED"
        (session / "historical_robustness_report.json").write_text(
            json.dumps(assessment, indent=2) + "\n", "utf-8"
        )
        note("RESULT: " + manifest["verdict"])
        note("Retrospective research only, NOT evidence for guaranteed future profit")
    except (Exception, KeyboardInterrupt) as exc:
        manifest["errors"].append(f"{type(exc).__name__}: {exc}")
        (session / "failure_trace.txt").write_text(traceback.format_exc(), "utf-8")
        note(f"FAIL CLOSED: {type(exc).__name__}: {exc}")
    finally:
        if terminal is not None and data is not None:
            try:
                capture_filtered_logs(data, session, started)
            except Exception as exc:
                manifest["errors"].append(f"log_capture: {type(exc).__name__}")
        for p in profiles:
            try:
                if p.exists() and sha256(p) == sha256(session / p.name):
                    p.unlink()
            except OSError:
                manifest["errors"].append("Temporary test profile cleanup failed")
        if terminal is not None:
            try:
                if auto_started:
                    if not closed_for_tests:
                        close_terminal(terminal, wait_s=30)
                    note("Auto-started terminal not reopened in chart mode")
                elif closed_for_tests and was_running:
                    reopen_terminal(terminal)
                    note("Original DEMO terminal reopened")
            except Exception as exc:
                manifest["errors"].append(f"terminal_restore: {type(exc).__name__}")
        manifest["elapsed_seconds"] = round(time.time() - started, 1)
        manifest["files_sha256"] = {
            p.relative_to(session).as_posix(): sha256(p)
            for p in session.rglob("*") if p.is_file()
            and not p.name.startswith("private_")
            and p.name not in ("manifest.json", "runner.log")
        }
        (session / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", "utf-8"
        )
        (session / "READ_ME_FIRST.txt").write_text(
            f"VERDICT: {manifest['verdict']}\n"
            "Tester-only original EA; no chart or real orders sent.\n"
            "Historical 2026 has already been inspected; not true OOS.\n"
            "All native HTML reports may contain a DEMO account number.\n",
            "utf-8"
        )
        try:
            pack_evidence(session, zip_path)
            packaged = True
            note("UPLOAD ONE EVIDENCE ZIP: " + str(zip_path))
        except Exception as exc:
            note(f"Cannot package ZIP: {exc}; inspect preserved {session}")
    if not packaged:
        return 3
    return 0 if manifest["verdict"].startswith("HISTORICAL_STRESS_") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-folder", default="")
    parser.add_argument("--max-minutes", type=int, default=240)
    args = parser.parse_args()
    if not 5 <= args.max_minutes <= 1440:
        parser.error("--max-minutes must be 5...1440 per historical pass")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
