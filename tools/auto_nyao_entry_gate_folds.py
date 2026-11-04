#!/usr/bin/env python3
"""One-click native A/B: original NYAO vs one virtual-reentry quality gate.

Historical XAUUSD@ real-tick DEMO research only. Original vendor EA and
presets unchanged; both compiled variants refuse non-tester chart execution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

from auto_nyao_stop_recovery import (
    ROOT, CONTROL_EXPERT, PRESET, REQUIRED_ORIGINAL_SHA, GuardFailure,
    sha256, find_mt5, launch_safe_preflight, verify_demo_after_autostart,
    guarded_control_source, compile_tester_control, run_tester_pass, copy_report,
    validated_native_report, native_deal_rows, write_utf16, read_text_any,
    close_terminal, reopen_terminal, capture_filtered_logs, pack_evidence,
)
from auto_nyao_historical_robustness import (
    FOLDS, assert_folds, historical_ini,
)
from auto_nyao_spread_gate import (
    SOURCE_PRESET, KNOWN_BASE_SHA256, native_identity, profile_inputs,
)

sys.path.insert(0, str(ROOT / "research" / "spread_gate"))
from analyze_stop_slippage import compare_reports

TRIAL_SOURCE = ROOT / "research" / "entry_quality" / "nyao_scalper_entry_gate.mq5"
TRIAL_SOURCE_ALLOWED_SHA = {
    "ebda1ba5954d9ea6b0ffcd6f73d734adba13b140cb61bcc28e65e5591c221305",
    "c8dd2450b64bbc53a85fce4504b9915e401f0fe7cfffb14cf8dac840bb16ea39",
}
TRIAL_EXPERT = r"TraderResearch\nyao_scalper_entry_gate_control"
OUT = ROOT / "local_runs" / "entry_quality_folds"


def compile_tester_trial(terminal: Path, data: Path, session: Path) -> Path:
    if sha256(TRIAL_SOURCE) not in TRIAL_SOURCE_ALLOWED_SHA:
        raise GuardFailure("Entry gate source drifted from preapproved one-change research")
    target = data / "MQL5" / "Experts" / "TraderResearch"
    target.mkdir(parents=True, exist_ok=True)
    source = target / "nyao_scalper_entry_gate_control.mq5"
    binary = source.with_suffix(".ex5")
    log = source.with_suffix(".log")
    content = guarded_control_source(TRIAL_SOURCE.read_text(encoding="utf-8"))
    if content.count("if(!MQLInfoInteger(MQL_TESTER)") != 1:
        raise GuardFailure("No unique MQL5 tester-only trial safety guard")
    source.write_text(content, encoding="utf-8")
    for old in (binary, log):
        if old.exists():
            old.unlink()
    compiler = terminal.parent / "metaeditor64.exe"
    if not compiler.is_file():
        raise GuardFailure("MetaEditor missing; cannot compile trial")
    t0 = time.time()
    proc = subprocess.run(
        f'"{compiler}" /compile:"{source}" /log',
        capture_output=True, text=True, timeout=240,
    )
    compiler_output = read_text_any(log) if log.is_file() else ""
    (session / "trial_compile.log").write_text(
        compiler_output + "\nPROCESS_EXIT_CODE=" + str(proc.returncode) + "\n",
        encoding="utf-8",
    )
    if (not re.search(r"(?im)^\s*Result:\s*0 errors,\s*0 warnings\b", compiler_output)
        or not re.search(r"(?im)^\s*:\s*information:\s*code generated\s*$", compiler_output)
        or not binary.is_file() or binary.stat().st_size <= 0
        or binary.stat().st_mtime < t0-3):
        raise GuardFailure("Tester-only entry gate compile failed; see trial_compile.log")
    (session / "trial_source_receipt.json").write_text(
        json.dumps({
            "research_source_sha256": sha256(TRIAL_SOURCE),
            "guarded_source_sha256": sha256(source),
            "guarded_ex5_sha256": sha256(binary),
            "tester_only": True,
            "original_source_unchanged": True,
        }, indent=2) + "\n", encoding="utf-8",
    )
    return binary


def entry_fold_ini(login: int, server: str, label: str,
                   profile: str, fold: tuple[str, str, str], trial: bool) -> str:
    ini = historical_ini(login, server, label, profile, fold)
    if trial:
        expected = "Expert=" + CONTROL_EXPERT
        if ini.count(expected) != 1:
            raise GuardFailure("Cannot select guarded experimental Expert")
        ini = ini.replace(expected, "Expert=" + TRIAL_EXPERT, 1)
    return ini


def compare_entry_fold(baseline: Path, trial: Path,
                       fold: tuple[str, str, str]) -> dict:
    base, base_inputs = validated_native_report(baseline)
    experimental, exp_inputs = validated_native_report(trial)
    if len(base_inputs) != 171 or base_inputs != exp_inputs:
        raise GuardFailure("Experimental entry gate changed native EA INPUTS")
    for tag, path, metrics in (
        ("control", baseline, base), ("entry_gate", trial, experimental)
    ):
        header = native_identity(path)
        expected_period = f"M5 ({fold[1]} - {fold[2]})"
        if header["period"] != expected_period or metrics["tested_range"] != expected_period:
            raise GuardFailure(tag + " native report has wrong fold time window")
        if abs(metrics["deposit"]-3000) > .001 or metrics["trades"] < 20:
            raise GuardFailure(tag + " invalid deposit or too few completed trades")
        deals = native_deal_rows(path)
        if len(deals) != 2 * metrics["trades"]:
            raise GuardFailure(tag + " incomplete native exit ledger")
    slip = compare_reports(baseline, trial)
    return {
        "fold": {"id": fold[0], "start": fold[1], "end": fold[2]},
        "control": base, "trial": experimental,
        "net_gain_usd": round(experimental["net"]-base["net"], 2),
        "dd_delta_pp": round(experimental["dd_pct"]-base["dd_pct"], 2),
        "native_identical_inputs": True,
        "executed_stop_comparison": slip,
        "decision": "Retrospective code-change A/B, NOT live approval",
    }


def try_cache_baselines(
    session: Path, vendor_hash: str, control_ex5_sha: str, preset_hash: str
) -> dict[str, Path]:
    """Reuse earlier fold BASE only with intact evidence and matching native EX5."""
    candidates = sorted(
        ROOT.glob("NYAO_HISTORICAL_STRESS_EVIDENCE_*.zip"), reverse=True
    )
    for archive in candidates:
        reports: dict[str, Path] = {}
        extracted: list[Path] = []
        try:
            with zipfile.ZipFile(archive) as z:
                if z.testzip() is not None:
                    continue
                m = json.loads(z.read("manifest.json"))
                if (not m.get("verdict", "").startswith("HISTORICAL_STRESS_")
                    or m.get("demo_account_verified") is not True
                    or m.get("source_sha256") != vendor_hash
                    or m.get("guarded_control_ex5_sha256") != control_ex5_sha
                    or m.get("preset_source_sha256") != preset_hash
                    or tuple(tuple(x) for x in m.get("folds_preregistered", [])) != FOLDS
                    or len(m.get("fold_results", [])) != 4):
                    continue
                hashes = m.get("files_sha256", {})
                for i, fold in enumerate(FOLDS):
                    name = fold[0]
                    paths = [
                        p for p in z.namelist() if re.fullmatch(
                            rf"native/{name}_BASE/NYAO_STOP_HIST_{name}_BASE_\d+\.htm",
                            p
                        )
                    ]
                    if len(paths) != 1:
                        raise GuardFailure("Cached baseline missing unique native MT5 HTML")
                    raw = z.read(paths[0])
                    if hashlib.sha256(raw).hexdigest() != hashes.get(paths[0]):
                        raise GuardFailure("Cached original HTML digest mismatch")
                    folder = session / "native" / (name + "_BASE")
                    folder.mkdir(parents=True, exist_ok=True)
                    path = folder / Path(paths[0]).name
                    path.write_bytes(raw)
                    extracted.append(path)
                    metrics, inputs = validated_native_report(path)
                    header = native_identity(path)
                    if (metrics["trades"] < 20 or len(inputs) != 171
                        or float(inputs["MaxSpreadPoints"]) != 500
                        or header["period"] != f"M5 ({fold[1]} - {fold[2]})"
                        or abs(metrics["deposit"]-3000) > .001
                        or len(native_deal_rows(path)) != 2*metrics["trades"]):
                        raise GuardFailure("Cached fold report did not pass native checks")
                    saved = m["fold_results"][i]["baseline"]
                    if (saved["trades"] != metrics["trades"]
                        or abs(saved["net"]-metrics["net"]) > .01):
                        raise GuardFailure("Cached MT5 report differs from saved fold summary")
                    reports[name] = path
                if len(reports) == 4:
                    (session / "verified_baseline_resume.json").write_text(
                        json.dumps({"zip": archive.name,
                                    "native_control_ex5_sha256": control_ex5_sha,
                                    "baseline_windows": list(reports)}, indent=2) + "\n",
                        encoding="utf-8"
                    )
                    return reports
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, GuardFailure):
            pass
        for path in extracted:
            try:
                path.unlink()
            except OSError:
                pass
    return {}


def outcome_summary(results: list[dict]) -> dict:
    if len(results) != 4 or [r["fold"]["id"] for r in results] != [x[0] for x in FOLDS]:
        raise GuardFailure("Not all 4 folds validated")
    improved = sum(r["net_gain_usd"] > .01 for r in results)
    dd_not_worse = sum(r["dd_delta_pp"] <= .01 for r in results)
    control = round(sum(r["control"]["net"] for r in results), 2)
    trial = round(sum(r["trial"]["net"] for r in results), 2)
    pf = {}
    for side in ("control", "trial"):
        profits = sum(r[side]["gross_profit"] for r in results)
        losses = sum(r[side]["gross_loss"] for r in results)
        pf[side] = round(profits / abs(losses), 4) if losses < 0 else None
    candidate = (
        improved >= 3 and dd_not_worse >= 3 and trial > control
        and pf["control"] is not None and pf["trial"] is not None
        and pf["trial"] > pf["control"]
    )
    return {
        "verdict": (
            "HISTORICAL_ENTRY_GATE_RESEARCH_CANDIDATE_ONLY"
            if candidate else "HISTORICAL_ENTRY_GATE_NOT_PROVEN"
        ),
        "improved_folds": improved, "drawdown_not_worse_folds": dd_not_worse,
        "fold_reset_control_sum_usd": control,
        "fold_reset_trial_sum_usd": trial,
        "pooled_pf": pf,
        "real_trading_approved": False,
        "note": "Each fold restarts balance/EA state. Same-year after-selection research. Demo chart monitoring is a separate operational decision.",
    }


def run(args: argparse.Namespace) -> int:
    if os.name != "nt":
        print("Windows + WMMarkets DEMO MT5 required", file=sys.stderr)
        return 2
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    session = OUT / stamp
    session.mkdir(parents=True, exist_ok=False)
    evidence_zip = ROOT / f"NYAO_ENTRY_GATE_EVIDENCE_{stamp}.zip"
    manifest: dict = {
        "verdict": "FAILED_CLOSED__LIVE_LOCKED",
        "test": "Original NYAO vs one fixed virtual re-entry quality gate",
        "windows": FOLDS, "live_trading_allowed": False,
        "real_orders_submitted": False,
        "errors": [], "fold_results": [],
    }
    log = session / "runner.log"

    def note(message: str) -> None:
        print(message, flush=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(message + "\n")

    begin = time.time()
    terminal = data = None
    auto_started = closed_for_tests = was_running = False
    tmp_profiles: list[Path] = []
    zip_ok = False
    try:
        assert_folds()
        original = ROOT / "nyao_scalper.mq5"
        if sha256(original) not in REQUIRED_ORIGINAL_SHA:
            raise GuardFailure("Vendor original changed")
        if sha256(SOURCE_PRESET) not in KNOWN_BASE_SHA256:
            raise GuardFailure("Original frozen 172-input preset changed")
        if sha256(TRIAL_SOURCE) not in TRIAL_SOURCE_ALLOWED_SHA:
            raise GuardFailure("Preapproved virtual reentry source changed")
        preset_text = SOURCE_PRESET.read_text(encoding="utf-8-sig")
        values = profile_inputs(preset_text)
        if len(values) != 172 or values.get("EnableVirtualSLReentry") != "true" \
           or values.get("ReentryMinSignalPct") != "0.75" \
           or values.get("MaxSpreadPoints") != "500" \
           or values.get("RiskPerTradePct") != "0.0" \
           or values.get("BaseLotSize") != "0.01":
            raise GuardFailure("Preset does not preserve virtual reentry controlled study")
        terminal, data = find_mt5(args.data_folder)
        auto_started = launch_safe_preflight(terminal, session)
        login, server = verify_demo_after_autostart(terminal, data, auto_started)
        was_running = True
        manifest["demo_verified"] = True
        note("PASS: WMMarkets DEMO, 0 open positions/orders")
        control = compile_tester_control(terminal, data, original, session)
        trial = compile_tester_trial(terminal, data, session)
        manifest["vendor_source_sha256"] = sha256(original)
        manifest["frozen_set_sha256"] = sha256(SOURCE_PRESET)
        manifest["control_ex5_sha256"] = sha256(control)
        manifest["trial_ex5_sha256"] = sha256(trial)
        profiles = data / "MQL5" / "Profiles" / "Tester"
        profiles.mkdir(parents=True, exist_ok=True)
        profile = profiles / f"Trader_HIST_ENTRY_GATE_{stamp}.set"
        if profile.exists():
            raise GuardFailure("Study-specific .set already exists")
        profile.write_text(preset_text, encoding="utf-8")
        tmp_profiles.append(profile)
        shutil.copy2(profile, session / profile.name)
        cached = try_cache_baselines(
            session, sha256(original), sha256(control), sha256(SOURCE_PRESET)
        )
        if cached:
            note("PASS: four native historical control reports verified against previous ZIP.")
            manifest["baseline_reused"] = True
        else:
            note("No cryptographically matching prior baseline; rerun all 8 passes.")
            manifest["baseline_reused"] = False
        plan = []
        for fold in FOLDS:
            for is_trial in (False, True):
                if cached and not is_trial:
                    continue
                kind = "GATE" if is_trial else "BASE"
                label = f"NYAO_STOP_ENTRY_{fold[0]}_{kind}_{stamp.replace('_', '')}"
                # historical_ini guards name and 172 frozen input values.
                config_label = f"NYAO_STOP_HIST_{fold[0]}_{kind}_{stamp.replace('_', '')}"
                name = f"private_{fold[0]}_{kind}.ini"
                content = entry_fold_ini(
                    login, server, config_label, profile.name, fold, is_trial
                )
                # Native report filename is unique but may use the ENTRY prefix.
                (session / name).parent.mkdir(parents=True, exist_ok=True)
                write_utf16(session / name, content)
                plan.append((fold, kind, config_label, name, is_trial))
        if not close_terminal(terminal, wait_s=120):
            raise GuardFailure("DEM0 MT5 cannot be safely closed for tester-only research")
        closed_for_tests = True
        done = {}
        for index, (fold, kind, label, ini, is_trial) in enumerate(plan, start=1):
            key = fold[0] + "_" + kind
            note(f"[{index}/{len(plan)}] Native 100% real-ticks {key}...")
            since, rc = run_tester_pass(terminal, session / ini, args.max_minutes, key)
            if rc != 0:
                raise GuardFailure(f"MT5 runner exited {rc} on {key}")
            report = copy_report(
                data, terminal, label, session / "native" / key, since
            )
            done[key] = report
            if is_trial:
                base = cached.get(fold[0]) or done.get(fold[0] + "_BASE")
                if base is None:
                    raise GuardFailure("No verified native baseline for fold")
                result = compare_entry_fold(base, report, fold)
                manifest["fold_results"].append(result)
                (session / "partial_results.json").write_text(
                    json.dumps(manifest["fold_results"], indent=2) + "\n",
                    encoding="utf-8"
                )
                note(f"{fold[0]} net: BASE {result['control']['net']:.2f}; "
                     f"GATE {result['trial']['net']:.2f}; "
                     f"equity DD {result['control']['dd_pct']:.2f}% -> "
                     f"{result['trial']['dd_pct']:.2f}%")
        manifest["assessment"] = outcome_summary(manifest["fold_results"])
        manifest["verdict"] = manifest["assessment"]["verdict"] + "__LIVE_LOCKED"
        (session / "result.json").write_text(
            json.dumps(manifest["assessment"], indent=2) + "\n", "utf-8"
        )
        note("RESEARCH VERDICT: " + manifest["verdict"])
        note("Neither historical ranking nor compiler success is LIVE permission.")
    except (Exception, KeyboardInterrupt) as exc:
        manifest["errors"].append(f"{type(exc).__name__}: {exc}")
        (session / "failure_trace.txt").write_text(traceback.format_exc(), "utf-8")
        note(f"FAILED CLOSED: {type(exc).__name__}: {exc}")
    finally:
        if data is not None:
            try:
                capture_filtered_logs(data, session, begin)
            except Exception as exc:
                manifest["errors"].append(f"log_capture: {type(exc).__name__}")
        for p in tmp_profiles:
            try:
                if p.exists() and sha256(p) == sha256(session / p.name):
                    p.unlink()
            except OSError:
                manifest["errors"].append("Research .set cleanup failed")
        if terminal is not None:
            try:
                if auto_started:
                    if not closed_for_tests:
                        close_terminal(terminal, wait_s=30)
                    note("Auto-started terminal not reopened for charts")
                elif closed_for_tests and was_running:
                    reopen_terminal(terminal)
                    note("Previous DEMO terminal reopened")
            except Exception as exc:
                manifest["errors"].append(f"terminal_restore: {type(exc).__name__}")
        manifest["elapsed_seconds"] = round(time.time()-begin, 1)
        manifest["files_sha256"] = {
            p.relative_to(session).as_posix(): sha256(p)
            for p in session.rglob("*") if p.is_file()
            and not p.name.startswith("private_")
            and p.name not in ("manifest.json", "runner.log")
        }
        (session / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (session / "READ_ME_FIRST.txt").write_text(
            "Native historical REAL-TICK DEMO A/B; one entry quality fix.\n"
            "A source-level bug is not a proven profitable trading edge.\n"
            "LIVE LOCKED. Native MT5 reports may include DEMO account identifiers.\n"
            "VERDICT: " + manifest["verdict"] + "\n", encoding="utf-8"
        )
        try:
            pack_evidence(session, evidence_zip)
            zip_ok = True
            note("UPLOAD ONE ZIP: " + str(evidence_zip))
        except Exception as exc:
            note(f"ZIP PACKAGING FAILED: {exc}; raw files at {session}")
    if not zip_ok:
        return 3
    return 0 if manifest["verdict"].startswith("HISTORICAL_ENTRY_GATE_") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-folder", default="")
    parser.add_argument("--max-minutes", type=int, default=240)
    args = parser.parse_args()
    if not 5 <= args.max_minutes <= 1440:
        parser.error("--max-minutes must be 5..1440")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
