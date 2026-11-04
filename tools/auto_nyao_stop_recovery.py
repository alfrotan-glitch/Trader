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
import html
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
CONTROL_EXPERT = r"TraderResearch\nyao_scalper_control"
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


def make_tester_ini(login: int, server: str, report_name: str,
                    expert: str = EXPERT) -> str:
    """Official MT5 /config Tester startup. Only a known DEMO account is accepted."""
    if not isinstance(login, int) or login <= 0:
        raise GuardFailure("Cannot lock tester to a validated DEMO login")
    if not server or re.search(r"[\r\n=\[\]]", server):
        raise GuardFailure("Invalid DEMO server name")
    if not re.fullmatch(r"NYAO_STOP_[A-Za-z0-9_]+", report_name):
        raise GuardFailure("Unsafe report name")
    if expert not in (EXPERT, CONTROL_EXPERT):
        raise GuardFailure("Only pinned research diagnostics/control Expert allowed")
    return "\n".join([
        "[Common]", f"Login={login}", f"Server={server}",
        "[Experts]", "Enabled=0", "AllowLiveTrading=0", "AllowDllImport=0",
        "Account=1", "Profile=1",
        "[Tester]", f"Expert={expert}", f"ExpertParameters={PRESET}",
        f"Symbol={SYMBOL}", f"Period={PERIOD}", "Model=4",
        "ExecutionMode=0", "Optimization=0", "ForwardMode=0",
        f"FromDate={START_DATE}", f"ToDate={END_DATE}",
        "Deposit=3000", "Currency=USD", "Leverage=1:100",
        "Visual=0", "UseLocal=1", "UseRemote=0", "UseCloud=0",
        f"Report={report_name}", "ReplaceReport=0", "ShutdownTerminal=1", "",
    ])



def make_safe_preflight_ini() -> str:
    """Start the local GUI with chart EAs OFF, before inspecting any account.

    This does NOT authorize a real trading account: a live/unknown login still
    fails before tester installation and the process is closed again.
    """
    return "\n".join([
        "[Experts]", "Enabled=0", "AllowLiveTrading=0", "AllowDllImport=0",
        "Account=1", "Profile=1", "",
    ])


def detect_any_terminal_process() -> bool:
    """Fail closed if a different/hidden terminal is running (avoid double launches)."""
    command = (
        "if (Get-Process -Name terminal64 -ErrorAction SilentlyContinue) "
        "{ exit 0 } else { exit 1 }"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
         "-Command", command],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode not in (0, 1):
        raise GuardFailure("Cannot inspect active terminal64 processes")
    return result.returncode == 0


def launch_safe_preflight(terminal: Path, run_dir: Path) -> bool:
    """Autostart disabled-trading MT5 only if no MT5 process exists.

    Never reuse a hidden terminal under an unknown account, and never enable
    automated chart trading while probing the saved login.
    """
    if terminal_running(terminal):
        return False
    if detect_any_terminal_process():
        raise GuardFailure(
            "An MT5 process is already running but does not match the selected "
            "installation. Close the unrelated MT5 or use --data-folder for "
            "the actual WMMarkets-Demo terminal. No second terminal launched."
        )
    try:
        import MetaTrader5  # noqa: F401
    except ImportError as exc:
        raise GuardFailure(
            "The MetaTrader5 Python package is missing. Install it with "
            "py -3 -m pip install MetaTrader5, then rerun."
        ) from exc
    ini = run_dir / "private_demo_preflight.ini"
    write_utf16(ini, make_safe_preflight_ini())
    try:
        proc = subprocess.Popen(
            [str(terminal), f"/config:{ini}"],
            creationflags=BELOW_NORMAL_PRIORITY_CLASS,
        )
    except OSError as exc:
        raise GuardFailure(f"MT5 could not start with safe trading-disabled config: {exc}") from exc
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            if terminal_running(terminal):
                return True
            if proc.poll() is not None:
                raise GuardFailure(
                    f"MT5 safe preflight exited before connection (code {proc.returncode}). "
                    "See ZIP and verify the installed terminal."
                )
            time.sleep(2)
        raise GuardFailure(
            "MT5 did not become visible within the safe preflight window; "
            "no test started. If it remains open, select the correct demo login."
        )
    except Exception:
        # Even an unexpected launcher timeout must not leave an unverified
        # terminal on a potentially REAL saved login.
        try:
            if terminal_running(terminal):
                close_terminal(terminal, wait_s=30)
            elif proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)
        except (OSError, subprocess.SubprocessError):
            pass
        raise


def verify_running_demo(terminal: Path, data: Path) -> tuple[int, str]:
    """Read the currently connected account; never place a broker order."""
    if not terminal_running(terminal):
        raise GuardFailure(
            "MT5 failed to open in safe (chart trading disabled) mode. "
            "Open the installed WMMarkets MT5 once, login to the DEMO account, "
            "then rerun RUN_NYAO_STOP_RECOVERY.bat."
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


def verify_demo_after_autostart(terminal: Path, data: Path,
                                auto_started: bool) -> tuple[int, str]:
    """Give a newly launched MT5 time to restore its DEMO connection.

    Never retry on a REAL login, foreign broker or non-flat account:
    only account-not-ready communication errors are retryable.
    """
    if not auto_started:
        return verify_running_demo(terminal, data)
    deadline = time.monotonic() + 90
    while True:
        try:
            return verify_running_demo(terminal, data)
        except GuardFailure as exc:
            reason = str(exc)
            not_ready = (
                "MT5 login/account details unavailable" in reason or
                "Could not inspect running MT5 account" in reason
            )
            if not not_ready or time.monotonic() >= deadline:
                if not_ready:
                    raise GuardFailure(
                        "MT5 was opened with automated chart trading disabled, "
                        "but there is no connected account yet. Log in to the "
                        "saved WMMarkets DEMO account once, then rerun the batch file."
                    ) from exc
                raise
            time.sleep(5)



def guarded_control_source(vendor_text: str) -> str:
    """One inert tester-only initialization guard, all vendor source lines untouched."""
    marker = "int OnInit()\n{"
    if vendor_text.count(marker) != 1:
        raise GuardFailure("Cannot place unique control tester-only OnInit guard")
    guard = (
        "\n    // RESEARCH CONTROL: never run on a normal chart or in optimization.\n"
        "    if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))\n"
        "        return INIT_FAILED;"
    )
    return vendor_text.replace(marker, marker + guard, 1)


def compile_tester_control(terminal: Path, data: Path, vendor: Path,
                           run_dir: Path) -> Path:
    """Compile one guarded control copy; never install a chart-tradable vendor EA."""
    expert_folder = data / "MQL5" / "Experts" / "TraderResearch"
    expert_folder.mkdir(parents=True, exist_ok=True)
    source = expert_folder / "nyao_scalper_control.mq5"
    binary = source.with_suffix(".ex5")
    compiler_log = source.with_suffix(".log")
    text_source = guarded_control_source(vendor.read_text(encoding="utf-8"))
    source.write_text(text_source, encoding="utf-8")
    for old in (binary, compiler_log):
        if old.is_file():
            old.unlink()
    compiler = terminal.parent / "metaeditor64.exe"
    if not compiler.is_file():
        raise GuardFailure("MetaEditor not found for tester-only control")
    compile_start = time.time()
    completed = subprocess.run(
        f'"{compiler}" /compile:"{source}" /log',
        capture_output=True, text=True, timeout=240
    )
    content = read_text_any(compiler_log) if compiler_log.is_file() else ""
    (run_dir / "control_compile.log").write_text(
        content + "\nPROCESS_EXIT_CODE=" + str(completed.returncode) + "\n",
        encoding="utf-8"
    )
    if (not re.search(r"(?im)^\s*Result:\s*0 errors,\s*0 warnings\b", content)
        or not re.search(r"(?im)^\s*:\s*information:\s*code generated\s*$", content)
        or not binary.is_file() or binary.stat().st_size <= 0
        or binary.stat().st_mtime < compile_start - 3):
        raise GuardFailure("Tester-only control MQL5 compile failed; see control_compile.log")
    # Confirm guard source used for compiled .ex5, and retain the source
    # digest without exposing proprietary broker configuration.
    (run_dir / "control_source_receipt.json").write_text(
        json.dumps({"control_source_sha256": sha256(source),
                    "control_ex5_sha256": sha256(binary),
                    "vendor_source_sha256": sha256(vendor),
                    "tester_only_guard": True}, indent=2) + "\n",
        encoding="utf-8"
    )
    return binary


def native_deal_rows(report: Path) -> list[tuple[str, ...]]:
    """Extract closed deal ledger, not just aggregate profit (no external packages)."""
    page = read_text_any(report)
    rows: list[tuple[str, ...]] = []
    for block in re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", page):
        cells = [
            html.unescape(re.sub(r"(?is)<[^>]*>", "", cell)).replace("\xa0", " ").strip()
            for cell in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", block)
        ]
        if len(cells) == 13 and cells[4] in ("in", "out", "in/out"):
            rows.append(tuple(cells))
    if len(rows) < 2 or sum(r[4] == "in" for r in rows) * 2 != len(rows):
        raise GuardFailure("Native deals ledger missing/incomplete; cannot verify A/A")
    return rows


def compare_native_reports(control: Path, diagnostic: Path) -> dict:
    control_rows, diag_rows = native_deal_rows(control), native_deal_rows(diagnostic)
    first_index = next(
        (i for i in range(min(len(control_rows), len(diag_rows)))
         if control_rows[i] != diag_rows[i]), None
    )
    if first_index is None and len(control_rows) != len(diag_rows):
        first_index = min(len(control_rows), len(diag_rows))
    return {
        "exact_native_deal_parity": control_rows == diag_rows,
        "control_deal_rows": len(control_rows),
        "diagnostic_deal_rows": len(diag_rows),
        "first_different_deal_index": first_index,
        "control_first_different": list(control_rows[first_index])
            if first_index is not None and first_index < len(control_rows) else None,
        "diagnostic_first_different": list(diag_rows[first_index])
            if first_index is not None and first_index < len(diag_rows) else None,
    }


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



def capture_native_compiler_evidence(run_dir: Path, started: float) -> None:
    """Include local MetaEditor compile.log and receipt when this launcher invoked it."""
    folder = ROOT / "local_runs" / "diagnostics"
    if not folder.is_dir():
        return
    candidates = sorted((p for p in folder.iterdir() if p.is_dir()),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        receipt = candidate / "receipt.json"
        log = candidate / "compile.log"
        if not (receipt.is_file() or log.is_file()):
            continue
        fresh = any(p.is_file() and p.stat().st_mtime >= started - 3
                    for p in (receipt, log))
        if not fresh:
            continue
        destination = run_dir / "native_compile"
        destination.mkdir(exist_ok=True)
        if log.is_file():
            shutil.copy2(log, destination / "compile.log")
        if receipt.is_file():
            shutil.copy2(receipt, destination / "receipt.json")
        return


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



def validated_native_report(path: Path) -> tuple[dict, dict[str, str]]:
    """Validate model and frozen inputs on every control/diagnostic pass."""
    report = parse_report(path)
    if report is None:
        raise GuardFailure("Native MT5 report summary missing")
    if "100%" not in str(report.get("quality", "")).lower() or \
       "real ticks" not in str(report.get("quality", "")).lower():
        raise GuardFailure("Not a 100% real-tick report: " + str(report.get("quality")))
    params = dict(re.findall(
        r"(?is)<b>\s*([A-Za-z_]\w*)=([^<\r\n]+)</b>",
        read_text_any(path)
    ))
    for setting, expected in (
        ("RiskPerTradePct", "0.0"),
        ("MaxRiskPerTradePct", "1.0"),
        ("MinEfficiencyToTrade", "0.15"),
        ("BaseLotSize", "0.01"),
        ("EnableCheckpointExit", "true"),
        ("EnableRiskReward", "false"),
    ):
        if params.get(setting) != expected:
            raise GuardFailure(
                f"Native report has nonfrozen {setting}={params.get(setting)!r}, "
                f"expected {expected}"
            )
    if len(params) < 170:
        raise GuardFailure("Native report omitted frozen input fields")
    return report, params


def run_tester_pass(terminal: Path, ini: Path, minutes: int,
                    progress: str) -> tuple[float, int]:
    """Single unattended tester pass; terminal shuts itself down via /config."""
    start = time.time()
    proc = subprocess.Popen(
        f'"{terminal}" /config:"{ini}"',
        creationflags=BELOW_NORMAL_PRIORITY_CLASS
    )
    deadline = time.monotonic() + minutes * 60
    last_print = time.monotonic()
    try:
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                raise GuardFailure(f"{progress} tester timed out; partial evidence kept")
            now = time.monotonic()
            if now - last_print > 120:
                print(f"{progress} tester running (no live orders)...", flush=True)
                last_print = now
            time.sleep(3)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
    return start, int(proc.returncode)


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
        "native_AA_control_required": True,
        "reference_sl_comment_loss_count": EXPECTED_STOP_LOSSES,
        "stop_watch_count_is_derived_from_native_deal_reason": True,
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
    started_safe_preflight = False
    closed_for_test = False
    proc: subprocess.Popen | None = None
    session_start = started
    zip_packaging_failed = False
    try:
        vendor = ROOT / "nyao_scalper.mq5"
        if sha256(vendor) not in REQUIRED_ORIGINAL_SHA:
            raise GuardFailure("Original vendor EA checksum drifted; no run permitted")
        terminal, data = find_mt5(args.data_folder)
        note("Preflight: check local MT5, safe-autostart with live chart trading disabled if closed...")
        started_safe_preflight = launch_safe_preflight(terminal, run_dir)
        if started_safe_preflight:
            note("Opened MT5 automatically using [Experts] Enabled=0 / AllowLiveTrading=0.")
        note("Verifying WMMarkets DEMO login and no open orders...")
        login, server = verify_demo_after_autostart(
            terminal, data, started_safe_preflight
        )
        if started_safe_preflight:
            state["safe_preflight_autostart"] = True
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

        note("Compiling original strategy as a SECOND, tester-only guarded CONTROL...")
        control_ex5 = compile_tester_control(terminal, data, vendor, run_dir)
        state["source_sha256"]["guarded_control_ex5"] = sha256(control_ex5)
        note("PASS: canonical control is protected from non-tester chart execution.")

        common = APPDATA / "MetaQuotes" / "Terminal" / "Common" / "Files"
        common.mkdir(parents=True, exist_ok=True)
        archive_previous_csvs(common, run_dir)
        note("Prior research CSV files archived locally without overwriting.")

        unique = stamp.replace("_", "")
        ctrl_label = "NYAO_STOP_CTRL_" + unique
        dx_label = "NYAO_STOP_DIAG_" + unique
        ctrl_config = run_dir / "private_control_tester.ini"
        dx_config = run_dir / "private_tester.ini"
        write_utf16(ctrl_config,
                    make_tester_ini(login, server, ctrl_label, CONTROL_EXPERT))
        write_utf16(dx_config,
                    make_tester_ini(login, server, dx_label, EXPERT))
        note("Running TWO isolated historical tests under the SAME frozen preset.")
        if not close_terminal(terminal, wait_s=120):
            raise GuardFailure("Running DEMO MT5 could not close gracefully; no forced shutdown")
        closed_for_test = True

        note("[1/2] Original guarded-control tester: XAUUSD@ M5, real ticks...")
        ctrl_started, ctrl_rc = run_tester_pass(
            terminal, ctrl_config, args.max_minutes, "Original control"
        )
        state["control_tester_exit_code"] = ctrl_rc
        ctrl_report = copy_report(
            data, terminal, ctrl_label, run_dir / "native_control", ctrl_started
        )
        ctrl_metrics, ctrl_inputs = validated_native_report(ctrl_report)
        state["native_control_summary"] = ctrl_metrics
        note(f"CONTROL: {ctrl_metrics['trades']} trades / USD {ctrl_metrics['net']:.2f}")

        note("[2/2] Instrumented tester: unchanged signals plus 24h tick observer...")
        session_start, dx_rc = run_tester_pass(
            terminal, dx_config, args.max_minutes, "Instrumented diagnostic"
        )
        state["mt5_process_exit_code"] = dx_rc
        report = copy_report(
            data, terminal, dx_label, run_dir / "native_report", session_start
        )
        files = copy_fresh_csvs(common, run_dir, session_start)
        metrics, dx_inputs = validated_native_report(report)
        state["native_summary"] = metrics
        state["report_file"] = report.name
        if ctrl_inputs != dx_inputs:
            raise GuardFailure(
                "Control/diagnostic native report inputs differ. "
                "No trading behavior conclusions can be drawn."
            )
        comparison = compare_native_reports(ctrl_report, report)
        comparison["same_trades_and_net"] = (
            ctrl_metrics["trades"] == metrics["trades"] and
            abs(ctrl_metrics["net"] - metrics["net"]) <= 0.02
        )
        comparison["historical_718_reference_matched"] = (
            ctrl_metrics["trades"] == EXPECTED_TRADES and
            abs(ctrl_metrics["net"] - EXPECTED_NET) <= 0.02
        )
        state["native_AA_comparison"] = comparison
        if comparison["exact_native_deal_parity"]:
            note("A/A PASS: original control and diagnostic have identical native deal ledgers.")
        else:
            note("A/A FAIL: original control vs diagnostic diverged; "
                 f"first differing deal index={comparison['first_different_deal_index']}.")
        if not comparison["historical_718_reference_matched"]:
            note("HISTORICAL REPLAY DRIFT: original control differs from saved "
                 "718 trade / USD 1212.42 report. Do not misattribute it to the diagnostic.")
        else:
            note("Historical 718 / USD 1212.42 control reference reproduced.")

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
            "--output", str(stop_out)
        ], run_dir / "stop_analyzer.log")
        state["entry_analyzer_passed"] = entry_ok
        state["stop_analyzer_passed"] = stop_ok
        if not stop_ok:
            raise GuardFailure(
                "Post-stop tick analyzer rejected evidence; see stop_analyzer.log."
            )
        if not entry_ok:
            note("ENTRY SIDE INCOMPLETE: check entry_analyzer.log. MT5 may close "
                 "a final trade after EA OnDeinit; raw CSV is preserved.")
        if not comparison["exact_native_deal_parity"]:
            state["verdict"] = "A_A_LEDGER_MISMATCH__HISTORICAL_RESEARCH_ONLY__LIVE_LOCKED"
            note("A/A MISMATCH: diagnostic code may perturb entries/exits. "
                 "No stop-change decision is supported.")
        elif not comparison["historical_718_reference_matched"]:
            state["verdict"] = "RESEARCH_AA_MATCHED__LEGACY_718_DRIFT__LIVE_LOCKED"
            note("A/A matched in today's MT5, but original historical 718 / "
                 "USD 1212.42 is NOT reproduced. Fresh environment drift suspected.")
        elif not entry_ok:
            state["verdict"] = "RESEARCH_AA_MATCHED__END_TEST_CENSORED__LIVE_LOCKED"
            note("A/A and stop watches matched but entry CSV has censored "
                 "end-of-test position; check native report.")
        else:
            state["verdict"] = "COMPLETE_RECONCILED__HISTORICAL_DIAGNOSTIC__LIVE_LOCKED"
            note("PASS: historical control, native A/A deals and analyzers all match.")
        note("Both raw MT5 reports and tick files included in evidence ZIP.")
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
        capture_native_compiler_evidence(run_dir, started)
        if data is not None:
            capture_filtered_logs(data, run_dir, session_start)
        if started_safe_preflight and not closed_for_test and terminal is not None:
            # This probe might have restored a REAL login. It was started with
            # all chart EAs disabled, and must NOT be left running on failure.
            try:
                if not close_terminal(terminal, wait_s=30):
                    note("WARNING: safe preflight MT5 did not close automatically.")
                else:
                    note("Safe-preflight MT5 closed after failed DEMO verification.")
            except Exception as exc:
                state["errors"].append(f"Safe preflight shutdown failed: {type(exc).__name__}")
                note("WARNING: close the safely launched MT5 manually.")
        if closed_for_test and was_running and terminal is not None:
            if started_safe_preflight:
                note("Auto-started MT5 not reopened in ordinary trading mode.")
            else:
                try:
                    reopen_terminal(terminal)
                    note("Existing DEMO terminal reopened after research test.")
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
            "If the verdict reports AA MISMATCH, do not use stop data to change the strategy.\n"
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
            zip_packaging_failed = True
            note(f"ZIP PACKAGING FAILED: {exc}; raw evidence at {run_dir}")
    if zip_packaging_failed:
        return 3
    return 0 if state["verdict"].startswith(("COMPLETE_RECONCILED", "RESEARCH_AA_MATCHED")) else 2


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
