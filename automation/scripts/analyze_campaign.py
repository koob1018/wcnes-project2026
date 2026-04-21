#!/usr/bin/env python3
"""Aggregate repeated receiver logs and produce comparison outputs."""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
STATS_DIR = REPO_ROOT / "stats"
if str(STATS_DIR) not in sys.path:
    sys.path.insert(0, str(STATS_DIR))

from functions import compute_ber, compute_ber_packet, readfile  # type: ignore


def load_manifest(manifest_csv: Path) -> pd.DataFrame:
    if not manifest_csv.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_csv}")
    df = pd.read_csv(manifest_csv)
    if df.empty:
        raise RuntimeError(f"Manifest is empty: {manifest_csv}")
    if "repeat_index" not in df.columns:
        df["repeat_index"] = 1
    if "campaign_id" not in df.columns:
        df["campaign_id"] = manifest_csv.parent.name
    return df


def valid_payload_mask(df: pd.DataFrame, payload_size: int) -> pd.Series:
    expected_len = payload_size * 3 - 1
    return df.payload.apply(lambda payload: len(payload) == expected_len)


def estimate_per_from_bit_errors(valid_df: pd.DataFrame, packet_len: int) -> tuple[float, int, int]:
    packet_count = int(len(valid_df))
    if packet_count == 0:
        return float("nan"), 0, 0

    packet_errors = 0
    for _, df_row in valid_df.iterrows():
        bit_errors, _ = compute_ber_packet(df_row, PACKET_LEN=packet_len)
        if bit_errors > 0:
            packet_errors += 1

    per = packet_errors / packet_count if packet_count > 0 else float("nan")
    return per, packet_errors, packet_count


def analyze_receiver_log(log_path: Path, payload_size: int, target_packets: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "receiver_raw_log": str(log_path.resolve()),
        "status": "ok",
        "reason": "",
        "received_rows": 0,
        "valid_rows": 0,
        "target_packets_required": target_packets,
        "packet_error_count": 0,
        "packet_count_for_per": 0,
        "per": float("nan"),
        "ber": float("nan"),
        "avg_rssi_dbm": float("nan"),
    }

    if not log_path.exists():
        row["status"] = "missing"
        row["reason"] = "receiver_log_missing"
        return row

    if log_path.stat().st_size == 0:
        row["status"] = "empty"
        row["reason"] = "receiver_log_empty"
        return row

    try:
        df = readfile(str(log_path))
    except Exception as exc:  # pragma: no cover - defensive for malformed lab logs
        row["status"] = "parse_error"
        row["reason"] = repr(exc)
        return row

    valid = df[valid_payload_mask(df, payload_size)].copy()
    valid.reset_index(drop=True, inplace=True)

    row["received_rows"] = int(len(df))
    row["valid_rows"] = int(len(valid))
    if len(valid) == 0:
        row["status"] = "no_valid_packets"
        row["reason"] = "no_valid_packets"
        return row
    if len(valid) < target_packets:
        row["status"] = "insufficient_packets"
        row["reason"] = f"valid_packets_lt_target_{target_packets}"
        return row

    packet_len = payload_size - 2
    with contextlib.redirect_stdout(io.StringIO()):
        ber = float(compute_ber(valid, PACKET_LEN=packet_len))
    per, packet_error_count, packet_count_for_per = estimate_per_from_bit_errors(valid, packet_len=packet_len)

    row["per"] = per
    row["ber"] = ber
    row["avg_rssi_dbm"] = float(valid.rssi.mean())
    row["packet_error_count"] = packet_error_count
    row["packet_count_for_per"] = packet_count_for_per
    return row


def write_plot(summary_df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = summary_df.sort_values(["clock_div0", "clock_div1"]).reset_index(drop=True)
    labels = [
        f"{row.run_id} ({int(row.valid_repeat_count)}/{int(row.requested_repeat_count)} valid)"
        for row in ordered.itertuples()
    ]
    positions = list(range(len(labels)))
    per_xerr = ordered["per_std"].fillna(0.0)
    ber_xerr = ordered["ber_std"].fillna(0.0)
    rssi_xerr = ordered["avg_rssi_dbm_std"].fillna(0.0)

    fig, axes = plt.subplots(3, 1, figsize=(14, max(8, len(labels) * 0.45)), constrained_layout=True)

    axes[0].barh(positions, ordered["per_mean"] * 100.0, xerr=per_xerr * 100.0, color="#c84c4c")
    axes[0].set_title("PER by run_id")
    axes[0].set_xlabel("PER [%]")
    axes[0].set_yticks(positions, labels)

    axes[1].barh(positions, ordered["ber_mean"] * 100.0, xerr=ber_xerr * 100.0, color="#3d7fd6")
    axes[1].set_title("BER by run_id")
    axes[1].set_xlabel("BER [%]")
    axes[1].set_yticks(positions, labels)

    axes[2].barh(positions, ordered["avg_rssi_dbm_mean"], xerr=rssi_xerr, color="#5d9a52")
    axes[2].set_title("RSSI by run_id")
    axes[2].set_xlabel("Average RSSI [dBm]")
    axes[2].set_yticks(positions, labels)

    fig.suptitle("Repeated experiment comparison", fontsize=16)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def analyze_campaign(
    manifest_csv: Path,
    output_dir: Path,
    payload_size: int = 14,
) -> tuple[Path, Path, Path]:
    manifest_df = load_manifest(manifest_csv)

    analysis_rows: list[dict[str, Any]] = []
    for row in manifest_df.to_dict(orient="records"):
        log_path = Path(str(row["receiver_raw_log"]))
        metrics = analyze_receiver_log(
            log_path,
            payload_size=payload_size,
            target_packets=int(row.get("target_packets", 0)),
        )
        merged = dict(row)
        merged.update(metrics)
        analysis_rows.append(merged)

    per_repeat_df = pd.DataFrame(analysis_rows)
    per_repeat_path = output_dir / "per_repeat.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    per_repeat_df.to_csv(per_repeat_path, index=False)

    ok_df = per_repeat_df[per_repeat_df["status"] == "ok"].copy()
    group_cols = ["run_id", "clock_div0", "clock_div1", "desired_baud"]
    requested_df = (
        per_repeat_df.groupby(group_cols, dropna=False)
        .agg(
            requested_repeat_count=("repeat_index", "count"),
            target_packets=("target_packets", "max"),
        )
        .reset_index()
    )
    valid_df = (
        ok_df.groupby(group_cols, dropna=False)
        .agg(valid_repeat_count=("repeat_index", "count"))
        .reset_index()
        if not ok_df.empty
        else pd.DataFrame(columns=group_cols + ["valid_repeat_count"])
    )

    if ok_df.empty:
        summary_df = requested_df.copy()
        summary_df["valid_repeat_count"] = 0
        summary_df["excluded_repeat_count"] = summary_df["requested_repeat_count"]
        summary_df["per_mean"] = float("nan")
        summary_df["per_std"] = float("nan")
        summary_df["ber_mean"] = float("nan")
        summary_df["ber_std"] = float("nan")
        summary_df["avg_rssi_dbm_mean"] = float("nan")
        summary_df["avg_rssi_dbm_std"] = float("nan")
        summary_df["valid_rows_mean"] = float("nan")
        summary_df["valid_rows_min"] = float("nan")
        summary_df["valid_rows_max"] = float("nan")
    else:
        grouped = ok_df.groupby(["run_id", "clock_div0", "clock_div1", "desired_baud"], dropna=False)
        metrics_df = grouped.agg(
            per_mean=("per", "mean"),
            per_std=("per", "std"),
            ber_mean=("ber", "mean"),
            ber_std=("ber", "std"),
            avg_rssi_dbm_mean=("avg_rssi_dbm", "mean"),
            avg_rssi_dbm_std=("avg_rssi_dbm", "std"),
            valid_rows_mean=("valid_rows", "mean"),
            valid_rows_min=("valid_rows", "min"),
            valid_rows_max=("valid_rows", "max"),
        ).reset_index()
        summary_df = requested_df.merge(valid_df, on=group_cols, how="left")
        summary_df = summary_df.merge(metrics_df, on=group_cols, how="left")
        summary_df["valid_repeat_count"] = summary_df["valid_repeat_count"].fillna(0).astype(int)
        summary_df["excluded_repeat_count"] = (
            summary_df["requested_repeat_count"] - summary_df["valid_repeat_count"]
        )
        for col in ["per_std", "ber_std", "avg_rssi_dbm_std"]:
            summary_df[col] = summary_df[col].fillna(0.0)

    summary_path = output_dir / "summary.csv"
    summary_df.to_csv(summary_path, index=False)

    plot_path = output_dir / "comparison_metrics.png"
    if not ok_df.empty:
        write_plot(summary_df, plot_path)
    else:
        plot_path.write_text("No valid receiver logs were available for plotting.\n", encoding="utf-8")

    return per_repeat_path, summary_path, plot_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze repeated automation campaign results.")
    parser.add_argument("--manifest-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--payload-size", default=14, type=int)
    args = parser.parse_args()

    per_repeat_path, summary_path, plot_path = analyze_campaign(
        manifest_csv=args.manifest_csv,
        output_dir=args.output_dir,
        payload_size=args.payload_size,
    )
    print(f"Saved per-repeat metrics: {per_repeat_path}")
    print(f"Saved summary metrics: {summary_path}")
    print(f"Saved comparison plot: {plot_path}")


if __name__ == "__main__":
    main()
