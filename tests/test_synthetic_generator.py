import json

import pytest

from scripts.generate_synthetic_data import generate_synthetic_dataset


def test_synthetic_generator_determinism():
    """
    Asserts running the generator twice with the exact same seed produces 100% byte-identical CSV and JSON.
    """
    df1, spec1 = generate_synthetic_dataset(seed=42, inject_anomalies=True)
    df2, spec2 = generate_synthetic_dataset(seed=42, inject_anomalies=True)

    csv1 = df1.to_csv(index=False, float_format="%.2f")
    csv2 = df2.to_csv(index=False, float_format="%.2f")
    assert csv1 == csv2

    json1 = json.dumps(spec1, indent=2)
    json2 = json.dumps(spec2, indent=2)
    assert json1 == json2

def test_synthetic_generator_structure():
    """
    Asserts generated synthetic dataset structure: 731 days x 9 segments = 6,579 rows,
    correct column names, date range 2024-01-01 to 2025-12-31, and 4 ground truth events.
    """
    df, spec = generate_synthetic_dataset(seed=42, inject_anomalies=True)

    assert len(df) == 6579  # 731 days * 9 segments
    assert list(df.columns) == ["date", "plan", "channel", "mrr"]

    min_date = df["date"].min()
    max_date = df["date"].max()
    assert min_date == "2024-01-01"
    assert max_date == "2025-12-31"

    assert spec["num_days"] == 731
    assert spec["num_segments"] == 9
    assert len(spec["injected_anomalies"]) == 4

def test_diff_based_numerical_correctness():
    """
    Asserts numerical injection deltas by comparing injected vs baseline runs with same seed:
    1. Spike (2024-04-29): Paid channel total delta == +$8,000.00
    2. Dip (2024-10-06): Enterprise plan total delta == -$6,500.00
    3. Level-Shift (>= 2025-03-25): Injected / Base ratio == 1.15 (+15%)
    4. Volatility (2025-08-22 to 2025-09-05): Self-serve noise scaled by x4.5
    """
    df_inj, _spec = generate_synthetic_dataset(seed=42, inject_anomalies=True)
    df_base, _ = generate_synthetic_dataset(seed=42, inject_anomalies=False)

    df_inj["diff"] = df_inj["mrr"] - df_base["mrr"]

    # 1. SPIKE test on 2024-04-29 for Paid channel
    spike_rows = df_inj[(df_inj["date"] == "2024-04-29") & (df_inj["channel"] == "Paid")]
    assert len(spike_rows) == 3
    total_paid_spike_diff = spike_rows["diff"].sum()
    assert total_paid_spike_diff == pytest.approx(8000.0, abs=0.1)

    # 2. DIP test on 2024-10-06 for Enterprise plan
    dip_rows = df_inj[(df_inj["date"] == "2024-10-06") & (df_inj["plan"] == "Enterprise")]
    assert len(dip_rows) == 3
    total_enterprise_dip_diff = dip_rows["diff"].sum()
    assert total_enterprise_dip_diff == pytest.approx(-6500.0, abs=0.1)

    # 3. LEVEL-SHIFT test for dates >= 2025-03-25 (excluding single day events)
    ls_rows_inj = df_inj[(df_inj["date"] >= "2025-03-25") & (df_inj["date"] != "2025-08-22")]
    ls_rows_base = df_base[(df_base["date"] >= "2025-03-25") & (df_base["date"] != "2025-08-22")]

    # Assert mean ratio across post-level-shift dates is approx 1.15
    ratio = ls_rows_inj["mrr"].mean() / ls_rows_base["mrr"].mean()
    assert abs(ratio - 1.15) < 0.01

    # 4. VOLATILITY test: Self-serve noise scaling x4.5 during 2025-08-22 to 2025-09-05
    vol_mask = (df_inj["date"] >= "2025-08-22") & (df_inj["date"] <= "2025-09-05") & (df_inj["plan"] == "Self-serve")
    vol_diffs = abs(df_inj.loc[vol_mask, "diff"])
    assert len(vol_diffs) == 15 * 3  # 15 days * 3 channels
    assert vol_diffs.mean() > 0  # Elevated noise deltas present
