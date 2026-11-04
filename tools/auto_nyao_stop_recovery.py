#!/usr/bin/env python3
"""One-run Windows MT5 diagnostic orchestrator: test, reconcile, ZIP.

A synchronous wrapper around the EXISTING tester-only EA and installer.
Never launches the vendor EA on a trading chart, never sends real broker orders.
No third-party requirement beyond the user's installed MetaTrader5 Python API.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

from backtest.nyao_backtest import (BELOW_NORMAL_PRIORITY_CLASS, close_terminal,
                                  parse_report, read_text_any, reopen_terminal,
                                  report_files, terminal_running, write_utf16)

ROOT = Path(__file__).resolve().parents[1]
APPDATA = Path(os.environ.get("APPDATA", ""))
OUTPUT_ROOT = ROOT / "local_runs" / "stop_recovery"
START_DATE, END_DATE = "2026.01.01", "2026.11.02"
SYMBOL, PERIOD = "XAUUSD@", "M5"
PRESET = "Trader_FRESH_ER015_FIXED001.set"
EXPERT = r"TraderResearch\nyao_scalper_diagnostic"
ENTRY_CSV = "NYAO_ENTRY_DIAGNOSTICS.csv"
STOP_CSV = "NYAO_STOP_RECOVERY_TICKS.csv"
EXPECTED_TRADES, EXPECTED_NET, EXPECTED_STOP_LOSSES = 718, 1212.42, 371
REQUIRED_ORIGINAL_SHA = {
    "91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837",
    "f4d5a57075745d8dd41297e3b252b31bbc08996f2eec727c898c2165e3cc9e3b",
}


class GuardFailure(Exception):
    """A precondition failed; do not launch the tester or declare success."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_mt5(data_folder: str = "") -> tuple[Path, Path]:
    root = APPDATA / "MetaQuotes" / "Terminal"
    found: list[tuple[Path, Path]] = []
    for data in sorted(root.iterdir()) if root.is_dir() else []:
        origin = data / "origin.txt"
        if not origin.is_file():
            continue
        raw = read_text_any(origin).strip().strip("\ufeff").strip('"')
        terminal = Path(raw) if raw.lower().endswith("terminal64.exe") else Path(raw) / "terminal64.exe"
        if terminal.is_file() and (terminal.parent / "metaeditor64.exe").is_file():
            found.append((terminal.resolve(), data.resolve()))
    if data_folder:
        wanted = Path(data_folder).resolve()
        found = [(exe, data) for exe, data in found if data == wanted]
    if len(found) != 1:
        raise GuardFailure(
            f"Expected ONE installed MT5 data directory, found {len(found)}. "
            "Do not run an unknown terminal; use --data-folder with the correct DEMO MT5 folder."
        )
    return found[0]


def make_tester_ini(login: int, server: str, report_name: str) -> str:
    """Official MT5 /config Tester startup. Only a known DEMO account is accepted."""
    if not isinstance(login, int) or login <= 0:
        raise GuardFailure("Cannot lock tester to a validated DEMO login")
    if not server or re.search(r"[\r\n=\[\]]", server):
        raise GuardFailure("Invalid DEMO server name")
    if not re.fullmatch(r"NYAO_STOP_[A-Za-z0-9_]+", report_name):
        raise GuardFailure("Unsafe report name")
    return "\n".join([
        "[Common]", f"Login={login}", f"Server={server}",
        "[Tester]", f"Expert={EXPERT}", f"ExpertParameters={PRESET}",
        f"Symbol={SYMBOL}", f"Period={PERIOD}", "Model=4",
        "ExecutionMode=0", "Optimization=0", "ForwardMode=0",
        f"FromDate={START_DATE}", f"ToDate={END_DATE}",
        "Deposit=3000", "Currency=USD", "Leverage=1:100",
        "Visual=0", "UseLocal=1", "UseRemote=0", "UseCloud=0",
        f"Report={report_name}", "ReplaceReport=0", "ShutdownTerminal=1", "",
    ])


def verify_running_demo(terminal: Path, data: Path) -> tuple[int, str]:
    """Attach to an ALREADY RUNNING terminal; abort rather than start unknown account."""
    if not terminal_running(terminal):
        raise GuardFailure(
            "WMMarkets DEMO terminal must already be open and logged in once. "
            "No terminal was started because its account type could not be verified."
        )
    try:
        import MetaTrader5 as mt5
    except ImportError as ex:
        raise GuardFailure(
            "Python MetaTrader5 package missing. Run: py -3 -m pip install MetaTrader5"
        ) from ex
    ok = False
    try:
        ok = mt5.initialize(path=str(terminal), timeout=30000)
        if not ok:
            raise GuardFailure("Could not inspect running MT5 account through Python API")
        terminal_info = mt5.terminal_info()
        acct = mt5.account_info()
        if terminal_info is None or acct is None:
            raise GuardFailure("MT5 login/account details unavailable")
        if Path(str(terminal_info.path)).resolve() != terminal.parent.resolve():
            raise GuardFailure("MetaTrader5 API attached to a different MT5 installation")
        if Path(str(terminal_info.data_path)).resolve() != data.resolve():
            raise GuardFailure("MetaTrader5 API attached to a different MT5 data folder")
        if int(acct.trade_mode) != 0 or "demo" not in str(acct.server).lower():
            raise GuardFailure("Account is NOT verified DEMO; aborting automatic tester")
        if not str(acct.server).lower().startswith("wmmarkets"):
            raise GuardFailure("Unexpected demo broker server; refusing silent switch")
        positions = mt5.positions_total()
        orders = mt5.orders_total()
        if positions is None or orders is None:
            raise GuardFailure("Cannot confirm flat DEMO account")
        if positions != 0 or orders != 0:
            raise GuardFailure(
                "DEMO terminal has open positions/orders. Refusing to close it automatically."
            )
        return int(acct.login), str(acct.server)
    finally:
        if ok:
            mt5.shutdown()


def pack_evidence(run_dir: Path, zip_path: Path) -> None:
    """Include only this run's evidence. Never include MT5 credentials/config."""
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=7, allowZip64=True) as out:
        for p in sorted(run_dir.rglob("*")):
            if not p.is_file() or p.name.lower().endswith((".ini", ".dat", ".key")):
                continue
            if "archive" in p.relative_to(run_dir).parts:
                continue
            out.write(p, p.relative_to(run_dir).as_posix())
            file_count += 1
    if file_count == 0:
        raise RuntimeError("Empty evidence package")
    with zipfile.ZipFile(zip_path) as z:
        for bad in z.testzip(),:
            if bad is not None:
                raise RuntimeError(f"ZIP integrity failure: {bad}")


def archive_previous_csvs(common: Path, run_dir: Path) -> None:
    backup = run_dir / "archive"
    for name in (ENTRY_CSV, STOP_CSV):
        previous = common / name
        if previous.is_file():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.move(str(previous), str(backup / name))
    if any((common / name).exists() for name in (ENTRY_CSV, STOP_CSV)):
        raise GuardFailure("Old tester CSV still exists. New evidence would be overwritten.")


def copy_report(data: Path, terminal: Path, base: str, out: Path,
                started: float) -> Path:
    choices = [data, terminal.parent, data / "tester"]
    report: Path | None = None
    for folder in choices:
        for extension in (".htm", ".html"):
            candidate = folder / (base + extension)
            if candidate.is_file() and candidate.stat().st_mtime >= started - 3:
                report = candidate
                break
        if report:
            break
    if report is None:
        raise GuardFailure(
            "No FRESH MT5 HTML tester report was produced. "
            "Likely login/history/tester startup issue; see logs and launch receipt."
        )
    out.mkdir(parents=True, exist_ok=True)
    for p in report_files(report.parent, base):
        if p.is_file() and p.stat().st_mtime >= started - 3:
            shutil.copy2(p, out / p.name)
    if not (out / report.name).exists():
        shutil.copy2(report, out / report.name)
    return out / report.name


def copy_fresh_csvs(common: Path, out: Path, started: float) -> dict[str, Path]:
    result = {}
    for name in (ENTRY_CSV, STOP_CSV):
        src = common / name
        if not src.is_file() or src.stat().st_mtime < started - 3 or src.stat().st_size < 128:
            raise GuardFailure(f"Missing, empty or stale tester CSV: {name}")
        dst = out / name
        shutil.copy2(src, dst)
        result[name] = dst
    return result


def capture_filtered_logs(data: Path, run_dir: Path, started: float) -> None:
    """Small sanitized diagnostic excerpts, not the user's full terminal/account logs."""
    lines: list[str] = []
    for folder in (data / "logs", data / "tester" / "logs"):
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)[:3]:
            if p.stat().st_mtime < started - 600:
                continue
            try:
                content = read_text_any(p)[-800000:]
            except (OSError, UnicodeError):
                continue
            selected = [ln for ln in content.splitlines()
                        if any(needle in ln.lower()
                               for needle in ("[dx]", "tester", "strategy test", "invalid stops",
                                              "no history", "not enough money", "error", "failed"))]
            for line in selected[-180:]:
                line = re.sub(r"(?i)(?:password|token|login|account)\s*[:=]\s*\S+",
                              "private=REDACTED", line)
                line = re.sub(r"\b\d{6,12}\b", "[ACCOUNT_REDACTED]", line)
                lines.append(f"[{p.parent.name}/{p.name}] {line[:450]}")
    if lines:
        (run_dir / "diagnostic_journal_excerpt.txt").write_text(
            "\n".join(lines[-600:]) + "\n", encoding="utf-8"
        )


def run_analyzer(args: list[str], logfile: Path) -> bool:
    run = subprocess.run([sys.executable, *args], capture_output=True,
                         text=True, timeout=120, cwd=str(ROOT))
    logfile.write_text((run.stdout or "") + "\n" + (run.stderr or ""),
                       encoding="utf-8")
    return run.returncode == 0


def check_report(path: Path) -> dict:
    result = parse_report(path)
    if result is None:
        raise GuardFailure("MT5 HTML summary missing or unreadable; see report")
    if result["trades"] != EXPECTED_TRADES or abs(result["net"] - EXPECTED_NET) > 0.02:
        raise GuardFailure(
            f"Diagnostic A/A parity FAIL: {result['trades']} trades, net {result['net']}; "
            f"expected {EXPECTED_TRADES} / {EXPECTED_NET}. Trading rules NOT validated."
        )
    quality = str(result.get("quality", "")).lower()
    if "real" not in quality or "100%" not in quality:
        raise GuardFailure(
            "Historical report does not explicitly verify 100% real ticks; "
            f"History Quality={result.get('quality')!r}. Reject non-reproducible data."
        )
    return result


def snapshot_hashes(paths: dict[str, Path]) -> dict[str, str | None]:
    return {name: sha256(p) if p.is_file() else None for name, p in paths.items()}


def run(args: argparse.Namespace) -> int:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    run_dir = OUTPUT_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    zip_path = ROOT / f"NYAO_STOP_RECOVERY_EVIDENCE_{stamp}.zip"
    started = time.time()
    state = {
        "verdict": "FAILED_CLOSED__LIVE_LOCKED",
        "date": stamp,
        "task": "24h post-stop historical real-tick diagnostic",
        "symbol": SYMBOL,
        "period": PERIOD,
        "range": [START_DATE, END_DATE],
        "model": "4 (Every tick based on real ticks)",
        "deposit_usd": 3000,
        "leverage": "1:100",
        "optimization": False,
        "live_trading_permitted": False,
        "expected_trades": EXPECTED_TRADES,
        "expected_net_usd": EXPECTED_NET,
        "errors": [],
    }
    log = run_dir / "runner.log"
    log.write_text("", encoding="utf-8")

    def note(message: str) -> None:
        msg = str(message)
        print(msg, flush=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    terminal: Path | None = None
    data: Path | None = None
    was_running = False
    closed_for_test = False
    proc: subprocess.Popen | None = None
    session_start = started
    try:
        vendor = ROOT / "nyao_scalper.mq5"
        if sha256(vendor) not in REQUIRED_ORIGINAL_SHA:
            raise GuardFailure("Original vendor EA checksum drifted; no run permitted")
        terminal, data = find_mt5(args.data_folder)
        note("Preflight: validating already-connected WMMarkets DEMO and no open orders...")
        login, server = verify_running_demo(terminal, data)
        was_running = True
        state["demo_verified_before_launch"] = True
        state["demo_server"] = server
        note("PASS: DEMO-only account verified, 0 open positions/orders; login ID omitted from ZIP.")

        note("Installing and compiling the TESTER-ONLY diagnostic (not original EA)...")
        install = subprocess.run([
            "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "tools" / "install_nyao_diagnostics.ps1"),
            "-TerminalPath", str(terminal), "-DataFolder", str(data),
        ], capture_output=True, text=True, timeout=240)
        (run_dir / "compile_install.log").write_text(
            (install.stdout or "") + "\n" + (install.stderr or ""), encoding="utf-8"
        )
        if install.returncode != 0 or "PASS: compiled research-only EA" not in install.stdout:
            raise GuardFailure("Native MetaEditor compilation FAILED; see compile_install.log")
        ex5 = data / "MQL5" / "Experts" / "TraderResearch" / "nyao_scalper_diagnostic.ex5"
        frozen = data / "MQL5" / "Profiles" / "Tester" / PRESET
        if not ex5.is_file() or ex5.stat().st_size < 512:
            raise GuardFailure("Fresh diagnostic EX5 is missing")
        if sha256(frozen) != sha256(ROOT / "research" / "fresh_entry" / PRESET):
            raise GuardFailure("Installed 172-input frozen tester preset differs from GitHub")
        state["source_sha256"] = snapshot_hashes({
            "vendor_mq5": vendor,
            "diagnostic_mq5": ROOT / "research" / "diagnostics" / "nyao_scalper_diagnostic.mq5",
            "diagnostic_header_mqh": ROOT / "research" / "diagnostics" / "NYAO_Diagnostics.mqh",
            "tester_preset": frozen,
            "compiled_ex5": ex5,
        })
        note("PASS: new diagnostic EX5 and pinned 172-input preset.")

        common = APPDATA / "MetaQuotes" / "Terminal" / "Common" / "Files"
        common.mkdir(parents=True, exist_ok=True)
        archive_previous_csvs(common, run_dir)
        note("Prior research CSV files archived locally without overwriting.")

        label = "NYAO_STOP_" + stamp.replace("_", "")
        config = run_dir / "private_tester.ini"
        write_utf16(config, make_tester_ini(login, server, label))
        note("Starting CLI Strategy Tester: XAUUSD@ M5, real ticks, original 0.01-lot preset.")

        if not close_terminal(terminal, wait_s=120):
            raise GuardFailure("Running DEMO MT5 could not close gracefully; no forced shutdown")
        closed_for_test = True
        session_start = time.time()
        proc = subprocess.Popen(
            f'"{terminal}" /config:"{config}"',
            creationflags=BELOW_NORMAL_PRIORITY_CLASS
        )
        deadline = time.monotonic() + (args.max_minutes * 60)
        last_print = 0.0
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                proc.kill()
                proc.wait(timeout=30)
                raise GuardFailure("Tester exceeded configured runtime cap; partial evidence packed")
            now = time.monotonic()
            if now - last_print > 120:
                note("Strategy Tester is running (no live trades).")
                last_print = now
            time.sleep(3)

        state["mt5_process_exit_code"] = proc.returncode
        note(f"Tester launcher exited with code {proc.returncode}. Verifying fresh evidence...")
        report = copy_report(data, terminal, label, run_dir / "native_report", session_start)
        state["report_file"] = report.name
        files = copy_fresh_csvs(common, run_dir, session_start)
        metrics = check_report(report)
        state["native_summary"] = metrics
        note(f"PASS: A/A parity = {metrics['trades']} trades / USD {metrics['net']:.2f}; real ticks confirmed.")

        entry_out = run_dir / "entry_forensics.json"
        entry_ok = run_analyzer([
            str(ROOT / "research" / "diagnostics" / "analyze_nyao_diagnostics.py"),
            str(files[ENTRY_CSV]), "--expected-trades", str(EXPECTED_TRADES),
            "--expected-net", str(EXPECTED_NET), "--out", str(entry_out)
        ], run_dir / "entry_analyzer.log")
        stop_out = run_dir / "stop_recovery_report.json"
        stop_ok = run_analyzer([
            str(ROOT / "research" / "stop_recovery" / "analyze_tick_recovery.py"),
            str(files[STOP_CSV]), "--entry-csv", str(files[ENTRY_CSV]),
            "--expected-stops", str(EXPECTED_STOP_LOSSES),
            "--output", str(stop_out)
        ], run_dir / "stop_analyzer.log")
        state["entry_analyzer_passed"] = entry_ok
        state["stop_analyzer_passed"] = stop_ok
        if not entry_ok or not stop_ok:
            raise GuardFailure(
                "Tester produced evidence but one or both analyzers rejected it; "
                "see entry_analyzer.log and stop_analyzer.log."
            )
        state["verdict"] = "COMPLETE_RECONCILED__HISTORICAL_DIAGNOSTIC__LIVE_LOCKED"
        note("PASS: both CSV evidence tables reconciled. No trading parameters changed.")
    except (GuardFailure, OSError, subprocess.SubprocessError, ValueError,
            RuntimeError) as exc:
        msg = f"{type(exc).__name__}: {exc}"
        state["errors"].append(msg)
        note("FAIL CLOSED: " + msg)
    except Exception as exc:
        state["errors"].append(f"{type(exc).__name__}: {exc}")
        (run_dir / "unexpected_error.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        note(f"FAIL CLOSED: unexpected {type(exc).__name__}; details in ZIP.")
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
        if data is not None:
            capture_filtered_logs(data, run_dir, session_start)
        if closed_for_test and was_running and terminal is not None:
            try:
                reopen_terminal(terminal)
                note("DEMO terminal reopened after research test.")
            except Exception as exc:
                state["errors"].append(f"Could not reopen DEMO terminal: {exc}")
                note("WARNING: DEMO terminal could not reopen.")
        state["elapsed_seconds"] = round(time.time() - started, 1)
        state["files_sha256"] = {
            p.relative_to(run_dir).as_posix(): sha256(p)
            for p in run_dir.rglob("*")
            if p.is_file() and p.name not in ("manifest.json", "runner.log")
            and "archive" not in p.relative_to(run_dir).parts
            and not p.name.lower().endswith(".ini")
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )
        (run_dir / "READ_ME_FIRST.txt").write_text(
            "Nyao Scalper STOP RECOVERY - historical research evidence\n"
            f"VERDICT: {state['verdict']}\n"
            "LIVE trading remains LOCKED. Vendor EA and historical preset unchanged.\n"
            "If the verdict is FAILED_CLOSED, inspect runner.log / analyzer logs.\n"
            "Use the two evidence CSVs and stop_recovery_report.json to review\n"
            "24h post-stop Bid/Ask paths. Native tester replay/parity is mandatory.\n"
            "Account passwords and private tester launch configuration are excluded.\n"
            "MT5 HTML reports may contain an account identifier; handle privately.\n",
            encoding="utf-8"
        )
        try:
            pack_evidence(run_dir, zip_path)
            note("")
            note("EVIDENCE ZIP READY (upload this ONE ZIP):")
            note(str(zip_path))
            note("VERDICT: " + state["verdict"])
        except Exception as exc:
            note(f"ZIP PACKAGING FAILED: {exc}; raw evidence at {run_dir}")
            return 3
    return 0 if state["verdict"].startswith("COMPLETE_RECONCILED") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-folder", default="", help="Disambiguate multiple MT5 demo data folders")
    parser.add_argument("--max-minutes", type=int, default=240,
                        help="Maximum wall-clock run duration; default 240")
    args = parser.parse_args()
    if args.max_minutes < 5 or args.max_minutes > 1440:
        parser.error("--max-minutes must be between 5 and 1440")
    if os.name != "nt":
        print("Windows/MetaTrader5 required for full automation", file=sys.stderr)
        return 2
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
