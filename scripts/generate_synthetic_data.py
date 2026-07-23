#!/usr/bin/env python3
"""
Standalone synthetic data generator for Driftline (Session 17).
Generates 2 full calendar years (731 days: 2024-01-01 to 2025-12-31 inclusive, accounting for leap year 2024)
of daily MRR data across 9 segment combinations (3 plan tiers x 3 channels).

Injects 4 deliberate ground-truth anomaly events:
1. SPIKE (2024-04-29 / Day 120): +$8,000.00 total across Paid channel segments.
2. DIP (2024-10-06 / Day 280): -$6,500.00 total drop across Enterprise plan segments.
3. LEVEL-SHIFT (2025-03-25 to 2025-12-31 / Day 450+): +15.0% permanent step increase across all segments.
4. VOLATILITY (2025-08-22 to 2025-09-05 / Days 600..614): x4.5 noise multiplier on Self-serve plan segments.

Outputs:
- demo_data/synthetic_mrr.csv (Canonical CSV)
- scripts/synthetic_ground_truth.json (Canonical Ground Truth Spec)
"""

import argparse
import json
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

PLANS = ["Enterprise", "SMB", "Self-serve"]
CHANNELS = ["Organic", "Paid", "Referral"]

# Share weights per dimension
PLAN_SHARES = {"Enterprise": 0.45, "SMB": 0.35, "Self-serve": 0.20}
CHANNEL_SHARES = {"Organic": 0.50, "Paid": 0.35, "Referral": 0.15}

# Day of week seasonality factors (Mon=0 .. Sun=6)
# Lower values on weekends (Sat/Sun)
DOW_MULTIPLIERS = [1.08, 1.08, 1.06, 1.06, 1.04, 0.84, 0.84]

def generate_synthetic_dataset(seed: int = 42, inject_anomalies: bool = True) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Generates synthetic daily MRR dataset and ground-truth specification dictionary.
    """
    rng = np.random.default_rng(seed)

    start_date = date(2024, 1, 1)
    num_days = 731  # 2024 (366 days) + 2025 (365 days) = 731 days total (ends 2025-12-31)
    dates = [start_date + timedelta(days=i) for i in range(num_days)]

    # 1. Base trend: Total daily revenue growing linearly from $12,000 to $28,000
    base_daily_totals = np.linspace(12000.0, 28000.0, num_days)

    records = []

    # Precalculate segment base revenue array [num_days, 9]
    segments = [(p, c) for p in PLANS for c in CHANNELS]

    for d_idx, d in enumerate(dates):
        dow = d.weekday()  # 0=Mon..6=Sun
        dow_factor = DOW_MULTIPLIERS[dow]

        for plan, channel in segments:
            share = PLAN_SHARES[plan] * CHANNEL_SHARES[channel]
            expected_val = base_daily_totals[d_idx] * share * dow_factor

            # Baseline noise: ~3% relative standard deviation
            sigma = expected_val * 0.03
            noise = float(rng.normal(0.0, sigma))

            records.append({
                "date": d.isoformat(),
                "day_index": d_idx + 1,  # 1-indexed (Day 1..731)
                "plan": plan,
                "channel": channel,
                "base_value": expected_val,
                "noise": noise,
                "value": expected_val + noise
            })

    df = pd.DataFrame(records)

    # Convert date back to date object for easy filtering
    df["date_obj"] = pd.to_datetime(df["date"]).dt.date

    # Define Ground Truth Anomaly Specifications
    ground_truth_events = [
        {
            "id": "anomaly_1_spike",
            "type": "spike",
            "date": "2024-04-29",
            "day_index": 120,
            "affected_dimension": "channel",
            "affected_channel": "Paid",
            "affected_segments": [
                {"plan": "Enterprise", "channel": "Paid", "per_segment_magnitude": round(8000.0 / 3.0, 4)},
                {"plan": "SMB", "channel": "Paid", "per_segment_magnitude": round(8000.0 / 3.0, 4)},
                {"plan": "Self-serve", "channel": "Paid", "per_segment_magnitude": round(8000.0 / 3.0, 4)},
            ],
            "total_magnitude": 8000.0,
            "tolerance_window_days": {"before": 1, "after": 1},
            "description": "Paid-channel-driven promotional revenue spike (+$8,000.00 total across Paid channel segments)"
        },
        {
            "id": "anomaly_2_dip",
            "type": "dip",
            "date": "2024-10-06",
            "day_index": 280,
            "affected_dimension": "plan",
            "affected_plan": "Enterprise",
            "affected_segments": [
                {"plan": "Enterprise", "channel": "Organic", "per_segment_magnitude": round(-6500.0 / 3.0, 4)},
                {"plan": "Enterprise", "channel": "Paid", "per_segment_magnitude": round(-6500.0 / 3.0, 4)},
                {"plan": "Enterprise", "channel": "Referral", "per_segment_magnitude": round(-6500.0 / 3.0, 4)},
            ],
            "total_magnitude": -6500.0,
            "tolerance_window_days": {"before": 1, "after": 1},
            "description": "Enterprise-plan-driven revenue drop (-$6,500.00 total across Enterprise plan segments)"
        },
        {
            "id": "anomaly_3_level_shift",
            "type": "level_shift",
            "date_start": "2025-03-25",
            "date_end": "2025-12-31",
            "day_index_start": 450,
            "day_index_end": 731,
            "affected_dimension": "global",
            "affected_segments": "all",
            "magnitude_multiplier": 1.15,
            "magnitude_pct": 15.0,
            "tolerance_window_days": {"before": 0, "after": 30},
            "description": "Pricing-change-driven permanent +15% step increase across all segments from 2025-03-25 to 2025-12-31"
        },
        {
            "id": "anomaly_4_volatility",
            "type": "volatility",
            "date_start": "2025-08-22",
            "date_end": "2025-09-05",
            "day_index_start": 600,
            "day_index_end": 614,
            "affected_dimension": "plan",
            "affected_plan": "Self-serve",
            "affected_segments": [
                {"plan": "Self-serve", "channel": "Organic"},
                {"plan": "Self-serve", "channel": "Paid"},
                {"plan": "Self-serve", "channel": "Referral"}
            ],
            "variance_multiplier": 4.5,
            "tolerance_window_days": {"before": 2, "after": 2},
            "description": "Self-serve plan volatility change period with 4.5x day-to-day noise scaling from 2025-08-22 to 2025-09-05"
        }
    ]

    if inject_anomalies:
        # Step 2: Apply LEVEL-SHIFT (+15.0% step multiplier for t >= Day 450) across all segments
        level_shift_start = date(2025, 3, 25)
        mask_ls = df["date_obj"] >= level_shift_start
        df.loc[mask_ls, "value"] = df.loc[mask_ls, "value"] * 1.15

        # Step 3: Apply VOLATILITY CHANGE (x4.5 noise scaling for Self-serve plan over Days 600..614)
        vol_start = date(2025, 8, 22)
        vol_end = date(2025, 9, 5)

        mask_vol = (df["date_obj"] >= vol_start) & (df["date_obj"] <= vol_end) & (df["plan"] == "Self-serve")
        # Scale the baseline noise component by 4.5 and update value on top of level-shifted baseline
        df.loc[mask_vol, "value"] = df.loc[mask_vol, "value"] + (df.loc[mask_vol, "noise"] * 3.5)

        # Step 4: Apply SPIKE (+$8,000.00 total across Paid channel on 2024-04-29)
        spike_date = date(2024, 4, 29)
        mask_spike = (df["date_obj"] == spike_date) & (df["channel"] == "Paid")
        per_paid_spike = 8000.0 / 3.0
        df.loc[mask_spike, "value"] = df.loc[mask_spike, "value"] + per_paid_spike

        # Step 5: Apply DIP (-$6,500.00 total across Enterprise plan on 2024-10-06)
        dip_date = date(2024, 10, 6)
        mask_dip = (df["date_obj"] == dip_date) & (df["plan"] == "Enterprise")
        per_enterprise_dip = -6500.0 / 3.0
        df.loc[mask_dip, "value"] = df.loc[mask_dip, "value"] + per_enterprise_dip

    # Clean up value column format (round to 2 decimal places)
    df["mrr"] = df["value"].round(2)
    export_df = df[["date", "plan", "channel", "mrr"]].copy()

    # Build Ground Truth Spec Dictionary with native Python types
    ground_truth_spec = {
        "dataset_name": "Synthetic 2-Year Daily MRR",
        "seed": int(seed),
        "num_days": int(num_days),
        "num_segments": 9,
        "date_start": "2024-01-01",
        "date_end": "2025-12-31",
        "total_rows": int(len(export_df)),
        "injected_anomalies": ground_truth_events
    }

    return export_df, ground_truth_spec

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic SaaS daily MRR dataset with ground truth anomalies.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation (default: 42)")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    demo_dir = os.path.join(project_root, "demo_data")
    scripts_dir = os.path.join(project_root, "scripts")

    os.makedirs(demo_dir, exist_ok=True)
    os.makedirs(scripts_dir, exist_ok=True)

    csv_path = os.path.join(demo_dir, "synthetic_mrr.csv")
    json_path = os.path.join(scripts_dir, "synthetic_ground_truth.json")

    df, spec = generate_synthetic_dataset(seed=args.seed, inject_anomalies=True)

    # Save canonical CSV
    df.to_csv(csv_path, index=False, float_format="%.2f")
    print(f"[+] Canonical synthetic CSV generated at: {csv_path} ({len(df)} rows)")

    # Save canonical ground truth JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    print(f"[+] Canonical ground truth JSON generated at: {json_path}")

if __name__ == "__main__":
    main()
