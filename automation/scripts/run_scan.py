#!/usr/bin/env python3
"""Windows-first MVP experiment runner.

Single execution path:
CSV plan -> tag patch/build/flash -> tag serial parse -> SmartRF GUI automation

Outputs are intentionally minimal:
- tag serial raw logs
- receiver raw logs
- one session manifest CSV
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tag_pipeline import run_single


def now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def load_runs_from_csv(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV plan not found: {csv_path}")

    runs: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        required = {"run_id", "clock_div0", "clock_div1", "desired_baud"}
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")

        for idx, row in enumerate(reader, start=1):
            if not any((v or "").strip() for v in row.values()):
                continue

            enabled_text = (row.get("enabled", "1") or "1").strip()
            if enabled_text and not parse_bool(enabled_text):
                continue

            run_id = (row.get("run_id") or f"run_{idx:03d}").strip()
            run: dict[str, Any] = {
                "run_id": run_id,
                "clock_div0": int((row.get("clock_div0") or "").strip()),
                "clock_div1": int((row.get("clock_div1") or "").strip()),
                "desired_baud": int((row.get("desired_baud") or "").strip()),
                "target_packets": int((row.get("target_packets") or "200").strip()),
                "receiver_timeout_s": int((row.get("receiver_timeout_s") or "60").strip()),
                "notes": (row.get("notes") or "").strip(),
            }
            runs.append(run)

    if not runs:
        raise ValueError(f"No enabled runs found in CSV: {csv_path}")
    return runs


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def stop_requested(stop_flag: Path) -> bool:
    return stop_flag.exists()


def raise_if_stop_requested(stop_flag: Path) -> None:
    if stop_requested(stop_flag):
        raise KeyboardInterrupt("Stop requested via stop flag")


def start_session_manifest(path: Path) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "run_id",
                "clock_div0",
                "clock_div1",
                "desired_baud",
                "target_packets",
                "receiver_timeout_s",
                "rx_base_freq_hz",
                "deviation_hz",
                "rx_data_rate_baud",
                "rx_bandwidth_hz",
                "tag_serial_log",
                "receiver_raw_log",
                "notes",
            ]
        )


def append_manifest_row(path: Path, row: list[Any]) -> None:
    with path.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(row)


def run_receiver_capture(
    ahk_exe: str,
    ahk_script: Path,
    coords_ini: Path,
    base_freq_hz: int,
    data_rate_baud: int,
    deviation_hz: int,
    rx_bw_hz: int,
    save_path: Path,
    timeout_s: int,
    target_packets: int,
    stop_flag: Path,
) -> None:
    ensure_parent(save_path)
    cmd = [
        ahk_exe,
        str(ahk_script),
        str(coords_ini),
        str(base_freq_hz),
        str(data_rate_baud),
        str(deviation_hz),
        str(rx_bw_hz),
        str(save_path),
        str(timeout_s),
        str(target_packets),
        str(stop_flag),
    ]
    proc = subprocess.Popen(cmd)
    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                if ret != 0:
                    raise RuntimeError(f"Receiver GUI automation failed ({ret})")
                return
            if stop_requested(stop_flag):
                # Let the AHK script observe the same stop flag and stop the RX GUI cleanly.
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    proc.wait(timeout=5)
                return
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_flag.touch()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVP backscatter experiment scan on Windows.")
    parser.add_argument(
        "--plan-csv",
        type=Path,
        default=Path("automation/config/scan_plan.csv"),
        help="Single source of experiment parameters.",
    )
    parser.add_argument("--serial-port", required=True, help="Tag USB serial port, e.g. COM3.")
    parser.add_argument("--serial-baud", default=115200, type=int)
    parser.add_argument("--serial-timeout-s", default=20, type=int)
    parser.add_argument("--carrier-freq-hz", default=2450000000, type=int)
    parser.add_argument("--main-c", type=Path, default=Path("carrier-receiver-baseband/main.c"))
    parser.add_argument("--project-dir", type=Path, default=Path("carrier-receiver-baseband"))
    parser.add_argument("--build-dir", type=Path, default=Path("carrier-receiver-baseband/build"))
    parser.add_argument("--elf-name", default="carrier_receiver_baseband.elf")
    parser.add_argument("--picotool-path", default="picotool")
    parser.add_argument("--enable-build", action="store_true")
    parser.add_argument("--enable-flash", action="store_true")
    parser.add_argument("--receiver-ahk-exe", default="AutoHotkey.exe")
    parser.add_argument(
        "--receiver-ahk-script",
        type=Path,
        default=Path("automation/gui/smartrf_mvp.ahk"),
    )
    parser.add_argument(
        "--receiver-coords-ini",
        type=Path,
        default=Path("automation/gui/smartrf_coords.ini"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("automation/results"),
        help="Each session gets one folder under this directory.",
    )
    parser.add_argument(
        "--stop-flag",
        type=Path,
        default=Path("automation/stop.flag"),
        help="Create this file to request a graceful stop.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    plan_csv = (root / args.plan_csv).resolve() if not args.plan_csv.is_absolute() else args.plan_csv.resolve()
    main_c = (root / args.main_c).resolve() if not args.main_c.is_absolute() else args.main_c.resolve()
    project_dir = (root / args.project_dir).resolve() if not args.project_dir.is_absolute() else args.project_dir.resolve()
    build_dir = (root / args.build_dir).resolve() if not args.build_dir.is_absolute() else args.build_dir.resolve()
    ahk_script = (
        (root / args.receiver_ahk_script).resolve()
        if not args.receiver_ahk_script.is_absolute()
        else args.receiver_ahk_script.resolve()
    )
    coords_ini = (
        (root / args.receiver_coords_ini).resolve()
        if not args.receiver_coords_ini.is_absolute()
        else args.receiver_coords_ini.resolve()
    )
    results_dir = (root / args.results_dir).resolve() if not args.results_dir.is_absolute() else args.results_dir.resolve()
    stop_flag = (root / args.stop_flag).resolve() if not args.stop_flag.is_absolute() else args.stop_flag.resolve()

    runs = load_runs_from_csv(plan_csv)

    session_id = now_stamp()
    session_dir = results_dir / session_id
    raw_dir = session_dir / "raw"
    manifest_csv = session_dir / "manifest.csv"
    start_session_manifest(manifest_csv)

    try:
        for idx, run in enumerate(runs, start=1):
            raise_if_stop_requested(stop_flag)

            run_id = str(run["run_id"])
            d0 = int(run["clock_div0"])
            d1 = int(run["clock_div1"])
            desired_baud = int(run["desired_baud"])
            timeout_s = int(run["receiver_timeout_s"])
            target_packets = int(run["target_packets"])
            notes = str(run.get("notes", ""))

            tag_serial_log = raw_dir / f"{run_id}_tag_serial.txt"
            receiver_raw_log = raw_dir / f"{run_id}_receiver_raw.txt"

            print(f"[{idx}/{len(runs)}] tag {run_id}: d0={d0} d1={d1} baud={desired_baud}")
            raise_if_stop_requested(stop_flag)
            parsed = run_single(
                main_c_path=main_c,
                project_dir=project_dir,
                build_dir=build_dir,
                elf_name=args.elf_name,
                d0=d0,
                d1=d1,
                desired_baud=desired_baud,
                serial_port=args.serial_port,
                serial_baud=args.serial_baud,
                serial_timeout_s=args.serial_timeout_s,
                carrier_freq_hz=args.carrier_freq_hz,
                enable_build=args.enable_build,
                enable_flash=args.enable_flash,
                picotool_path=args.picotool_path,
                serial_log_file=tag_serial_log,
            )

            print(f"[{idx}/{len(runs)}] receiver {run_id}: GUI capture")
            raise_if_stop_requested(stop_flag)
            run_receiver_capture(
                ahk_exe=args.receiver_ahk_exe,
                ahk_script=ahk_script,
                coords_ini=coords_ini,
                base_freq_hz=int(parsed["rx_base_freq_hz"]),
                data_rate_baud=int(parsed["baudrate"]),
                deviation_hz=int(parsed["deviation_hz"]),
                rx_bw_hz=int(parsed["rx_bandwidth_hz"]),
                save_path=receiver_raw_log,
                timeout_s=timeout_s,
                target_packets=target_packets,
                stop_flag=stop_flag,
            )

            append_manifest_row(
                manifest_csv,
                [
                    run_id,
                    d0,
                    d1,
                    desired_baud,
                    target_packets,
                    timeout_s,
                    parsed["rx_base_freq_hz"],
                    parsed["deviation_hz"],
                    parsed["baudrate"],
                    parsed["rx_bandwidth_hz"],
                    str(tag_serial_log.resolve()),
                    str(receiver_raw_log.resolve()),
                    notes,
                ],
            )

            raise_if_stop_requested(stop_flag)
    except KeyboardInterrupt:
        print(f"Stop requested. Exiting at a safe point. If present, clear: {stop_flag}")
    finally:
        print(f"Session complete: {session_dir}")


if __name__ == "__main__":
    main()
