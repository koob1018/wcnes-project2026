from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from functions import compute_ber, readfile


PAYLOADSIZE = 14
NUM_16RND = (PAYLOADSIZE - 2) // 2


def extract_position_m(filename: str) -> float:
    match = re.fullmatch(r"position([0-9]*\.?[0-9]+)\.txt", filename)
    if not match:
        raise ValueError(f"Unsupported filename format: {filename}")
    return float(match.group(1))


def compute_metrics_for_file(file_path: Path) -> dict:
    df = readfile(str(file_path))

    # Keep only packets whose payload length matches notebook assumptions.
    valid = df[df.payload.apply(lambda x: len(x) == (PAYLOADSIZE * 3 - 1))].copy()
    valid.reset_index(drop=True, inplace=True)

    received_packets = int(len(valid))
    avg_rssi_dbm = float(valid.rssi.mean()) if received_packets > 0 else np.nan
    ber = float(compute_ber(valid, PACKET_LEN=NUM_16RND * 2)) if received_packets > 0 else np.nan
    reliability_pct = (1.0 - ber) * 100.0 if received_packets > 0 else np.nan

    seq_values = [int(value) for value in valid.seq.tolist()]
    missing_packets = 0
    if len(seq_values) > 1:
        for previous_seq, current_seq in zip(seq_values, seq_values[1:]):
            missing_packets += (current_seq - previous_seq - 1) % 256
    estimated_sent_packets = received_packets + missing_packets
    per = missing_packets / estimated_sent_packets if estimated_sent_packets > 0 else np.nan

    return {
        "file": file_path.name,
        "position_m": extract_position_m(file_path.name),
        "received_packets": received_packets,
        "missing_packets_est": missing_packets,
        "estimated_sent_packets": estimated_sent_packets,
        "per": per,
        "ber": ber,
        "reliability_pct": reliability_pct,
        "avg_rssi_dbm": avg_rssi_dbm,
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    txt_files = sorted(root.glob("position*.txt"), key=lambda p: extract_position_m(p.name))

    if not txt_files:
        raise FileNotFoundError("No files matching position*.txt were found in stats/.")

    rows = [compute_metrics_for_file(p) for p in txt_files]
    result_df = pd.DataFrame(rows).sort_values("position_m").reset_index(drop=True)

    csv_out = root / "position_metrics.csv"
    result_df.to_csv(csv_out, index=False)

    # Figure: three vertically stacked panels sharing the same X axis.
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

    axes[0].plot(
        result_df["position_m"],
        result_df["per"] * 100.0,
        marker="o",
        linewidth=2,
        color="#2ca02c",
    )
    axes[0].set_ylabel("PER [%]", fontsize=12)
    axes[0].set_title("Tag Position vs PER, BER, and RSSI", fontsize=14)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(
        result_df["position_m"],
        result_df["ber"] * 100.0,
        marker="o",
        linewidth=2,
        color="#1f77b4",
    )
    axes[1].set_ylabel("BER [%]", fontsize=12)
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(
        result_df["position_m"],
        result_df["avg_rssi_dbm"],
        marker="s",
        linewidth=2,
        color="#d62728",
    )
    axes[2].set_xlabel("Tag position from carrier [m]", fontsize=12)
    axes[2].set_ylabel("RSSI [dBm]", fontsize=12)
    axes[2].grid(True, alpha=0.3)

    fig.text(
        0.01,
        0.01,
        "Figure. Three performance metrics versus tag position. PER is estimated from sequence-number gaps, BER is the bit-error rate, and RSSI is shown in dBm.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(root / "position_vs_metrics.png", dpi=200)

    print("Computed metrics:")
    print(result_df.to_string(index=False))
    print(f"\nSaved table: {csv_out}")
    print(f"Saved figure: {root / 'position_vs_metrics.png'}")


if __name__ == "__main__":
    main()
