#!/usr/bin/env python3
"""Minimal scan runner for tag-side loop.

Current scope:
- iterates parameter sets
- updates/builds/flashes tag
- parses receiver-relevant params from tag serial output
- saves per-run metadata and a simple receiver task file for next step

Receiver GUI operation is intentionally not hard-coupled yet.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tag_pipeline import run_single


def now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def load_runs_from_csv(csv_path: Path) -> list[Dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV plan not found: {csv_path}")

    runs: list[Dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        required = {"clock_div0", "clock_div1", "desired_baud"}
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

            run_id = (row.get("run_id") or row.get("id") or f"run_{idx:03d}").strip()
            run: Dict[str, Any] = {
                "id": run_id,
                "clock_div0": int((row.get("clock_div0") or "").strip()),
                "clock_div1": int((row.get("clock_div1") or "").strip()),
                "desired_baud": int((row.get("desired_baud") or "").strip()),
                "target_packets": int((row.get("target_packets") or "200").strip()),
                "receiver_timeout_s": int((row.get("receiver_timeout_s") or "60").strip()),
            }
            note = (row.get("notes") or "").strip()
            if note:
                run["notes"] = note
            runs.append(run)

    if not runs:
        raise ValueError(f"No enabled runs found in CSV: {csv_path}")
    return runs


def save_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVP tag loop from config")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--plan-csv", type=Path, help="CSV run plan; overrides config.runs")
    parser.add_argument("--enable-build", action="store_true")
    parser.add_argument("--enable-flash", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    root = Path(cfg.get("workspace_root", ".")).resolve()

    main_c = (root / cfg["main_c_path"]).resolve()
    project_dir = (root / cfg["tag_project_dir"]).resolve()
    build_dir = (root / cfg["build_dir"]).resolve()
    results_root = (root / cfg.get("results_root", "automation/results/runs")).resolve()
    raw_root = (root / cfg.get("raw_logs_root", "automation/results/raw")).resolve()

    elf_name = cfg.get("elf_name", "carrier_receiver_baseband.elf")
    serial_port = cfg["serial_port"]
    serial_baud = int(cfg.get("serial_baud", 115200))
    serial_timeout_s = int(cfg.get("serial_timeout_s", 20))
    carrier_freq_hz = int(cfg["carrier_freq_hz"])
    picotool_path = cfg.get("picotool_path", "picotool")

    if args.plan_csv:
        csv_path = args.plan_csv if args.plan_csv.is_absolute() else (root / args.plan_csv)
        runs = load_runs_from_csv(csv_path.resolve())
    elif "plan_csv" in cfg:
        csv_path = Path(cfg["plan_csv"])
        if not csv_path.is_absolute():
            csv_path = root / csv_path
        runs = load_runs_from_csv(csv_path.resolve())
    else:
        runs = cfg["runs"]
    session_id = now_stamp()
    session_root = results_root / f"session_{session_id}"
    session_root.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {"session_id": session_id, "runs": []}

    for i, run in enumerate(runs, start=1):
        run_id = run.get("id", f"run_{i:03d}")
        d0 = int(run["clock_div0"])
        d1 = int(run["clock_div1"])
        baud = int(run["desired_baud"])
        timeout_s = int(run.get("receiver_timeout_s", 60))
        target_packets = int(run.get("target_packets", 200))

        run_dir = session_root / run_id
        serial_log = raw_root / f"{session_id}_{run_id}_tag_serial.txt"

        parsed = run_single(
            main_c_path=main_c,
            project_dir=project_dir,
            build_dir=build_dir,
            elf_name=elf_name,
            d0=d0,
            d1=d1,
            desired_baud=baud,
            serial_port=serial_port,
            serial_baud=serial_baud,
            serial_timeout_s=serial_timeout_s,
            carrier_freq_hz=carrier_freq_hz,
            enable_build=args.enable_build,
            enable_flash=args.enable_flash,
            picotool_path=picotool_path,
            serial_log_file=serial_log,
        )

        receiver_task = {
            "run_id": run_id,
            "target_packets": target_packets,
            "timeout_s": timeout_s,
            "save_path": str((raw_root / f"{session_id}_{run_id}_receiver_log.txt").resolve()),
            "base_freq_hz": parsed["rx_base_freq_hz"],
            "data_rate_baud": parsed["baudrate"],
            "deviation_hz": parsed["deviation_hz"],
            "rx_filter_bw_hz": parsed["rx_bandwidth_hz"],
            "source": "tag_serial_computed_baseband_settings",
            "suggested_ahk_command": (
                "AutoHotkey.exe automation/gui/smartrf_mvp.ahk "
                "automation/gui/smartrf_coords.ini "
                f"{parsed['rx_base_freq_hz']} "
                f"{parsed['baudrate']} "
                f"{parsed['deviation_hz']} "
                f"{parsed['rx_bandwidth_hz']} "
                f'\"{str((raw_root / f"{session_id}_{run_id}_receiver_log.txt").resolve())}\" '
                f"{timeout_s} {target_packets}"
            ),
        }

        run_meta = {
            "run_id": run_id,
            "tag_params": {"clock_div0": d0, "clock_div1": d1, "desired_baud": baud},
            "tag_serial_log": str(serial_log.resolve()),
            "receiver_task": receiver_task,
        }

        save_json(run_dir / "receiver_task.json", receiver_task)
        save_json(run_dir / "run_meta.json", run_meta)

        summary["runs"].append(
            {
                "run_id": run_id,
                "receiver_task_file": str((run_dir / "receiver_task.json").resolve()),
                "run_meta_file": str((run_dir / "run_meta.json").resolve()),
            }
        )

        print(f"[{i}/{len(runs)}] prepared {run_id}")

    save_json(session_root / "session_summary.json", summary)
    print(f"Session done: {session_root}")


if __name__ == "__main__":
    main()
