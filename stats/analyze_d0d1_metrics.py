#!/usr/bin/env python3
"""Analyze BER, PER, and RSSI over d0-d1 parameter files.

Input data are expected under stats/WCNES_data/d0d1 with filenames that start
with the parameter pair, e.g. 20-18.txt, 24-20无数据.txt, 36-28很差.txt.

This script reuses the project's existing log parser and BER computation:
- stats/functions.py::readfile
- stats/functions.py::compute_ber

It produces a two-panel heatmap figure for BER and RSSI.
"""

from __future__ import annotations

import contextlib
import io
import argparse
import re
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from functions import compute_ber, readfile

PAYLOADSIZE = 14
NUM_16RND = (PAYLOADSIZE - 2) // 2
DEFAULT_MIN_VALID_PACKETS = 20
PAIR_PATTERN = re.compile(r"^(?P<d0>\d+)-(?P<d1>\d+)")


def extract_pair(file_name: str) -> tuple[int, int]:
    match = PAIR_PATTERN.match(file_name)
    if not match:
        raise ValueError(f"Unsupported filename format: {file_name}")
    return int(match.group("d0")), int(match.group("d1"))


def valid_payload_mask(df: pd.DataFrame) -> pd.Series:
    expected_len = PAYLOADSIZE * 3 - 1
    return df.payload.apply(lambda payload: len(payload) == expected_len)


def summarize_file(file_path: Path, min_valid_packets: int) -> dict[str, Any]:
    d0, d1 = extract_pair(file_path.name)
    f0_hz = 125_000_000 / d0
    f1_hz = 125_000_000 / d1
    deviation_khz = abs(f1_hz - f0_hz) / 2 / 1000
    center_offset_mhz = (f0_hz + f1_hz) / 2 / 1_000_000
    min_rx_bw_khz = 100 + 2 * deviation_khz
    base: dict[str, Any] = {
        "file": file_path.name,
        "d0": d0,
        "d1": d1,
        "deviation_khz": deviation_khz,
        "center_offset_mhz": center_offset_mhz,
        "min_rx_bw_khz": min_rx_bw_khz,
        "status": "excluded",
        "reason": "",
        "total_rows": np.nan,
        "valid_rows": np.nan,
        "received_packets": np.nan,
        "missing_packets_est": np.nan,
        "estimated_sent_packets": np.nan,
        "per": np.nan,
        "ber": np.nan,
        "reliability_pct": np.nan,
        "avg_rssi_dbm": np.nan,
        "rssi_std_dbm": np.nan,
    }

    if file_path.stat().st_size == 0:
        base["reason"] = "empty_file"
        return base

    try:
        df = readfile(str(file_path))
    except Exception as exc:
        base["reason"] = f"parse_error: {exc!r}"
        return base

    valid = df[valid_payload_mask(df)].copy()
    valid.reset_index(drop=True, inplace=True)

    total_rows = int(len(df))
    valid_rows = int(len(valid))
    base["total_rows"] = total_rows
    base["valid_rows"] = valid_rows

    if valid_rows == 0:
        base["reason"] = "no_valid_packets"
        return base

    if valid_rows < min_valid_packets:
        base["reason"] = f"insufficient_valid_packets<{min_valid_packets}"
        return base

    avg_rssi_dbm = float(valid.rssi.mean())
    rssi_std_dbm = float(valid.rssi.std(ddof=0)) if valid_rows > 1 else 0.0
    with contextlib.redirect_stdout(io.StringIO()):
        ber = float(compute_ber(valid, PACKET_LEN=NUM_16RND * 2))
    reliability_pct = (1.0 - ber) * 100.0

    seq_values = [int(value) for value in valid.seq.tolist()]
    missing_packets = 0
    if len(seq_values) > 1:
        for previous_seq, current_seq in zip(seq_values, seq_values[1:]):
            missing_packets += (current_seq - previous_seq - 1) % 256
    estimated_sent_packets = valid_rows + missing_packets
    per = missing_packets / estimated_sent_packets if estimated_sent_packets > 0 else np.nan

    base.update(
        {
            "status": "included",
            "reason": "",
            "received_packets": valid_rows,
            "missing_packets_est": missing_packets,
            "estimated_sent_packets": estimated_sent_packets,
            "per": per,
            "ber": ber,
            "reliability_pct": reliability_pct,
            "avg_rssi_dbm": avg_rssi_dbm,
            "rssi_std_dbm": rssi_std_dbm,
        }
    )
    return base


def format_metric(value: Any, scale: float = 1.0, digits: int = 3) -> str:
    if pd.isna(value):
        return "nan"
    return f"{float(value) * scale:.{digits}f}"


def build_heatmap(ax: plt.Axes, pivot: pd.DataFrame, title: str, cmap: str, value_scale: float = 1.0, value_format: str = ".2f") -> None:
    if pivot.empty:
        ax.set_title(f"{title} (no data)")
        ax.axis("off")
        return

    data = pivot.to_numpy(dtype=float)
    im = ax.imshow(data, aspect="auto", origin="lower", cmap=cmap)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(int(idx)) for idx in pivot.index])
    ax.set_xlabel("d0")
    ax.set_ylabel("d1")
    ax.set_title(title)

    for row_idx, row_value in enumerate(pivot.index):
        for col_idx, col_value in enumerate(pivot.columns):
            cell = pivot.loc[row_value, col_value]
            if pd.isna(cell):
                continue
            ax.text(
                col_idx,
                row_idx,
                format(cell * value_scale, value_format),
                ha="center",
                va="center",
                fontsize=8,
                color="black",
            )

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)


def save_outputs(result_df: pd.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_path = output_dir / "d0d1_metrics_ber_rssi.png"

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)

    ber_pivot = result_df.pivot(index="d1", columns="d0", values="ber") * 100.0
    rssi_pivot = result_df.pivot(index="d1", columns="d0", values="avg_rssi_dbm")

    build_heatmap(axes[0], ber_pivot, "BER [%] across d0-d1", cmap="YlGn_r", value_scale=1.0, value_format=".2f")
    build_heatmap(axes[1], rssi_pivot, "Average RSSI [dBm] across d0-d1", cmap="viridis", value_scale=1.0, value_format=".0f")

    fig.suptitle("WCNES parameter sweep summary", fontsize=16)
    fig.savefig(fig_path, dpi=220)
    plt.close(fig)

    return fig_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze BER, PER, and RSSI over d0-d1 files.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=SCRIPT_DIR / "WCNES_data" / "d0d1",
        help="Directory containing parameter logs named like 20-18.txt",
    )
    parser.add_argument(
        "--min-valid-packets",
        type=int,
        default=DEFAULT_MIN_VALID_PACKETS,
        help="Minimum number of valid packets required to include a file in the analysis.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCRIPT_DIR / "WCNES_data" / "analysis",
        help="Directory to write CSV summaries and charts.",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []

    for file_path in sorted(data_dir.glob("*.txt")):
        row = summarize_file(file_path, min_valid_packets=args.min_valid_packets)
        if row["status"] == "included":
            rows.append(row)
        else:
            excluded_rows.append(row)

    if not rows:
        raise RuntimeError("No files met the minimum valid packet threshold.")

    result_df = pd.DataFrame(rows).sort_values(["d1", "d0"]).reset_index(drop=True)
    excluded_df = pd.DataFrame(excluded_rows).sort_values(["d1", "d0"]).reset_index(drop=True)

    fig_path = save_outputs(result_df, args.output_dir)

    # Minimal stdout: only report what was kept and where the figure was saved.
    print("Included files:")
    print(result_df[["file", "d0", "d1", "deviation_khz", "min_rx_bw_khz", "ber", "avg_rssi_dbm"]].to_string(index=False))
    print("\nExcluded files:")
    if len(excluded_df) > 0:
        print(excluded_df[["file", "d0", "d1", "valid_rows", "reason"]].to_string(index=False))
    else:
        print("None")
    print(f"Saved figure: {fig_path}")


if __name__ == "__main__":
    main()
