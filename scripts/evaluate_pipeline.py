#!/usr/bin/env python3
"""
Standalone End-to-End Pipeline Evaluation Script for Driftline (Session 18).
Runs full pipeline (ingestion -> decomposition -> anomaly detection -> driver analysis -> forecasting & backtesting)
against demo_data/synthetic_mrr.csv and compares outputs against scripts/synthetic_ground_truth.json.

Computes primary performance metrics plus classification accuracy and uniform shift proportionality:
1. detection_recall: injected_anomalies_correctly_flagged / 4
2. classification_accuracy: correct_anomaly_types / detected_anomalies
3. false_positive_rate: anomalies_flagged_on_untouched_days / total_untouched_days
4. driver_accuracy: correct_top_segment_matches / 3 (segment-concentrated events)
5. forecast_MAPE: mean(|actual - predicted_p50| / actual) from ForecastAccuracyLog
6. interval_coverage: percentage of actuals falling within [p10, p90] from ForecastAccuracyLog
7. uniform_shift_proportionality: boolean pass/fail check for Level-Shift relative step size (~15%)
"""

import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db.session import AsyncSessionLocal
from src.ingestion.models import Metric, Observation, DimensionDef, DirectionGoodEnum, GrainEnum
from src.ingestion.service import inspect_and_validate_csv, confirm_and_persist_observations
from src.anomalies.models import DailyRollup, Anomaly
from src.anomalies.service import run_daily_rollup_and_decomposition, detect_and_persist_anomalies
from src.drivers.service import calculate_anomaly_drivers, train_and_persist_structural_importance
from src.forecasting.models import Forecast, ForecastAccuracyLog
from src.forecasting.service import generate_multi_step_forecast, run_walk_forward_backtest, get_forecast_accuracy

BENCHMARK_METRIC_NAME = "Synthetic MRR Benchmark"

async def reset_benchmark_metric(db: AsyncSession) -> Metric:
    """
    Idempotently deletes any existing benchmark metric and all associated downstream records.
    Creates a fresh Metric configuration with sensitivity='medium'.
    """
    res = await db.execute(select(Metric).where(Metric.name == BENCHMARK_METRIC_NAME))
    existing_metrics = list(res.scalars().all())

    for m in existing_metrics:
        await db.execute(delete(ForecastAccuracyLog).where(ForecastAccuracyLog.metric_id == m.id))
        await db.execute(delete(Forecast).where(Forecast.metric_id == m.id))
        await db.execute(delete(Anomaly).where(Anomaly.metric_id == m.id))
        await db.execute(delete(DailyRollup).where(DailyRollup.metric_id == m.id))
        await db.execute(delete(Observation).where(Observation.metric_id == m.id))
        await db.execute(delete(DimensionDef).where(DimensionDef.metric_id == m.id))
        await db.execute(delete(Metric).where(Metric.id == m.id))
    await db.commit()

    metric = Metric(
        workspace_id=1,
        name=BENCHMARK_METRIC_NAME,
        unit="USD",
        direction_good=DirectionGoodEnum.up_is_good,
        sensitivity="medium",
        grain=GrainEnum.daily
    )
    db.add(metric)
    await db.commit()
    await db.refresh(metric)
    return metric

async def run_pipeline_evaluation(session: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """
    Runs the complete evaluation benchmark pipeline and returns structured metric results.
    Accepts an optional caller-provided AsyncSession for pytest NullPool event-loop safety.
    """
    if session is None:
        async with AsyncSessionLocal() as db:
            return await run_pipeline_evaluation(session=db)

    db = session

    print("=" * 80)
    print(" DRIFTLINE END-TO-END PIPELINE EVALUATION BENCHMARK")
    print("=" * 80)

    csv_path = os.path.join(PROJECT_ROOT, "demo_data", "synthetic_mrr.csv")
    gt_path = os.path.join(PROJECT_ROOT, "scripts", "synthetic_ground_truth.json")

    if not os.path.exists(csv_path) or not os.path.exists(gt_path):
        raise FileNotFoundError("Synthetic dataset or ground truth spec missing. Run scripts/generate_synthetic_data.py first.")

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_spec = json.load(f)

    print("[1/6] Initializing clean benchmark metric environment...")
    metric = await reset_benchmark_metric(db)
    metric_id = metric.id
    print(f"      Created metric ID #{metric_id} ('{BENCHMARK_METRIC_NAME}') with sensitivity='medium'")

    print("[2/6] Ingesting synthetic MRR dataset (731 days, 9 segments)...")
    with open(csv_path, "rb") as f:
        file_bytes = f.read()

    inspect_res = inspect_and_validate_csv(metric, file_bytes)
    assert inspect_res["validation_report"]["is_valid"], f"CSV validation failed: {inspect_res['validation_report']['errors']}"

    confirm_schema = type("Schema", (), {
        "date_col": inspect_res["inferred_mapping"]["date_col"],
        "value_col": inspect_res["inferred_mapping"]["value_col"],
        "dimension_cols": inspect_res["inferred_mapping"]["dimension_cols"],
        "rows": inspect_res["rows"],
        "replace": True
    })()

    confirm_res = await confirm_and_persist_observations(db, metric_id, confirm_schema)
    print(f"      Ingested {confirm_res['total_observations']} raw observation rows into database.")

    print("[3/6] Running time series decomposition & anomaly detection...")
    await run_daily_rollup_and_decomposition(db, metric_id)
    await detect_and_persist_anomalies(db, metric_id)

    anom_res = await db.execute(
        select(Anomaly).where(Anomaly.metric_id == metric_id).order_by(Anomaly.date.asc())
    )
    detected_anomalies = list(anom_res.scalars().all())
    print(f"      Detected {len(detected_anomalies)} total anomalies in database.")

    print("[4/6] Running driver analysis & CatBoost structural importance...")
    for anomaly in detected_anomalies:
        try:
            driver_data = await calculate_anomaly_drivers(db, anomaly.id)
            anomaly.explanation_text = driver_data["explanation_text"]
        except Exception as e:
            print(f"      [!] Driver analysis skipped for anomaly on {anomaly.date}: {e}")
    await db.commit()

    await train_and_persist_structural_importance(db, metric_id)

    print("[5/6] Running 12-week walk-forward backtest & generating 30-day forecast...")
    await run_walk_forward_backtest(metric_id=metric_id, session=db, horizon_days=7, model_backend="lightgbm", max_weeks=12)
    await generate_multi_step_forecast(metric_id=metric_id, session=db, horizon_days=30, save_to_db=True)

    print("[6/6] Evaluating whole-pipeline accuracy against ground truth...")
    
    injected_events = gt_spec["injected_anomalies"]
    
    def to_d(date_str: str) -> date:
        return datetime.strptime(date_str, "%Y-%m-%d").date()

    gt_evaluations = []
    detected_gt_count = 0
    correct_classified_count = 0
    correct_driver_count = 0
    
    for ev in injected_events:
        ev_id = ev["id"]
        ev_type = ev["type"]
        tolerance = ev.get("tolerance_window_days", {"before": 1, "after": 1})
        before_days = tolerance.get("before", 1)
        after_days = tolerance.get("after", 1)

        if "date" in ev:
            ev_start = to_d(ev["date"]) - timedelta(days=before_days)
            ev_end = to_d(ev["date"]) + timedelta(days=after_days)
            target_date = to_d(ev["date"])
        else:
            ev_start = to_d(ev["date_start"]) - timedelta(days=before_days)
            ev_end = to_d(ev["date_start"]) + timedelta(days=after_days)
            target_date = to_d(ev["date_start"])

        matching_anoms = [a for a in detected_anomalies if ev_start <= a.date <= ev_end]
        is_detected = len(matching_anoms) > 0
        
        primary_anom = None
        if is_detected:
            detected_gt_count += 1
            matching_exact_type = [a for a in matching_anoms if (a.type.value if hasattr(a.type, "value") else str(a.type)) == ev_type]
            if matching_exact_type:
                primary_anom = max(matching_exact_type, key=lambda a: abs(a.z_score))
                type_matched = True
                correct_classified_count += 1
            else:
                primary_anom = max(matching_anoms, key=lambda a: abs(a.z_score))
                type_matched = False
        else:
            type_matched = False

        driver_matched = False
        driver_explanation = ""
        if ev_type != "level_shift":
            if is_detected and primary_anom is not None:
                driver_data = await calculate_anomaly_drivers(db, primary_anom.id)
                expected_dim = ev["affected_dimension"]
                expected_target = ev.get(f"affected_{expected_dim}")
                
                ranked_segs = driver_data.get("ranked_segments", [])
                dim_segs = [s for s in ranked_segs if s["dimension"] == expected_dim]
                if dim_segs:
                    dim_segs.sort(key=lambda x: abs(x["delta"]), reverse=True)
                    top_seg_val = dim_segs[0]["segment_value"]
                    if top_seg_val == expected_target:
                        driver_matched = True
                        correct_driver_count += 1
                        driver_explanation = f"Matched top segment '{expected_dim}: {top_seg_val}'"
                    else:
                        driver_explanation = f"Top segment was '{expected_dim}: {top_seg_val}' (expected: '{expected_target}')"
                else:
                    driver_explanation = f"No segments found for dimension '{expected_dim}'"
            else:
                driver_explanation = "Missed anomaly detection; driver analysis skipped (0/1)"
        else:
            driver_explanation = "Level-shift uniform event (scored via Uniform Shift Proportionality Check)"

        gt_evaluations.append({
            "id": ev_id,
            "type": ev_type,
            "target_date": target_date.isoformat(),
            "detected": is_detected,
            "type_matched": type_matched,
            "detected_anomaly_date": primary_anom.date.isoformat() if primary_anom else None,
            "detected_type": (primary_anom.type.value if hasattr(primary_anom.type, "value") else str(primary_anom.type)) if primary_anom else None,
            "driver_matched": driver_matched if ev_type != "level_shift" else None,
            "driver_explanation": driver_explanation
        })

    detection_recall = detected_gt_count / 4.0
    classification_accuracy = (correct_classified_count / float(detected_gt_count)) if detected_gt_count > 0 else 0.0
    driver_accuracy = correct_driver_count / 3.0

    # Level-Shift Uniform Shift Proportionality Check (Days 481..510 post-settling vs Days 401..431 pre-shift)
    rollups_res = await db.execute(
        select(DailyRollup).where(DailyRollup.metric_id == metric_id)
    )
    all_rollups = list(rollups_res.scalars().all())

    pre_shift_start = date(2025, 2, 4)   # Day 401
    pre_shift_end = date(2025, 3, 6)     # Day 431
    post_shift_start = date(2025, 4, 25) # Day 481
    post_shift_end = date(2025, 5, 24)   # Day 510

    pre_rollups = [r for r in all_rollups if pre_shift_start <= r.date <= pre_shift_end]
    post_rollups = [r for r in all_rollups if post_shift_start <= r.date <= post_shift_end]

    def compute_mean_by_dim(rollups_list: List[DailyRollup]) -> Dict[str, float]:
        dim_groups: Dict[str, List[float]] = {}
        for r in rollups_list:
            key = json.dumps(r.dimension_values, sort_keys=True)
            dim_groups.setdefault(key, []).append(float(r.value_total))
        return {k: float(np.mean(vals)) for k, vals in dim_groups.items()}

    pre_means = compute_mean_by_dim(pre_rollups)
    post_means = compute_mean_by_dim(post_rollups)

    daily_trend_slope = (28000.0 - 12000.0) / 730.0
    elapsed_days = (date(2025, 5, 9) - date(2025, 2, 19)).days

    PLAN_SHARES = {"Enterprise": 0.45, "SMB": 0.35, "Self-serve": 0.20}
    CHANNEL_SHARES = {"Organic": 0.50, "Paid": 0.35, "Referral": 0.15}

    segment_shift_pcts = []
    for key, pre_m in pre_means.items():
        if key == "{}" or pre_m == 0:
            continue
        dim_dict = json.loads(key)
        weight = 1.0
        if "plan" in dim_dict and "channel" in dim_dict:
            weight = PLAN_SHARES.get(dim_dict["plan"], 0.33) * CHANNEL_SHARES.get(dim_dict["channel"], 0.33)
        elif "plan" in dim_dict:
            weight = PLAN_SHARES.get(dim_dict["plan"], 0.33)
        elif "channel" in dim_dict:
            weight = CHANNEL_SHARES.get(dim_dict["channel"], 0.33)

        organic_growth = elapsed_days * daily_trend_slope * weight
        post_m = post_means.get(key, pre_m)
        trend_adjusted_post = post_m - organic_growth
        pct_shift = ((trend_adjusted_post - pre_m) / pre_m) * 100.0
        segment_shift_pcts.append(pct_shift)

    uniform_shift_proportionality = len(segment_shift_pcts) > 0 and all(12.0 <= p <= 18.0 for p in segment_shift_pcts)
    mean_level_shift_pct = float(np.mean(segment_shift_pcts)) if segment_shift_pcts else 0.0

    # False Positive Rate on Untouched Days
    excluded_dates = set()
    for d in pd.date_range("2024-01-01", "2024-01-13").date:
        excluded_dates.add(d)
    for d in pd.date_range("2024-04-28", "2024-04-30").date:
        excluded_dates.add(d)
    for d in pd.date_range("2024-10-05", "2024-10-07").date:
        excluded_dates.add(d)
    for d in pd.date_range("2025-03-25", "2025-04-24").date:
        excluded_dates.add(d)
    for d in pd.date_range("2025-08-20", "2025-09-07").date:
        excluded_dates.add(d)

    all_dates = set(pd.date_range("2024-01-01", "2025-12-31").date)
    untouched_dates = all_dates - excluded_dates
    total_untouched_days = len(untouched_dates)

    flagged_untouched_dates = {a.date for a in detected_anomalies if a.date in untouched_dates}
    false_positive_count = len(flagged_untouched_dates)
    false_positive_rate = false_positive_count / float(total_untouched_days)

    # Forecast Accuracy Metrics (MAPE & Interval Coverage from ForecastAccuracyLog)
    accuracy_info = await get_forecast_accuracy(
        metric_id=metric_id,
        session=db,
        horizon_days=7,
        model_backend="lightgbm",
        auto_run=False
    )

    forecast_MAPE = accuracy_info.get("mape")
    interval_coverage = accuracy_info.get("coverage_pct")
    evaluations_count = accuracy_info.get("total_evaluations", 0)

    results = {
        "metric_id": metric_id,
        "metric_name": BENCHMARK_METRIC_NAME,
        "total_observations": confirm_res['total_observations'],
        "total_anomalies_flagged": len(detected_anomalies),
        "ground_truth_events_count": len(injected_events),
        "detection_recall": detection_recall,
        "classification_accuracy": classification_accuracy,
        "false_positive_rate": false_positive_rate,
        "false_positive_count": false_positive_count,
        "total_untouched_days": total_untouched_days,
        "driver_accuracy": driver_accuracy,
        "uniform_shift_proportionality": uniform_shift_proportionality,
        "mean_level_shift_pct": mean_level_shift_pct,
        "forecast_MAPE": forecast_MAPE,
        "interval_coverage": interval_coverage,
        "backtest_evaluations_count": evaluations_count,
        "ground_truth_evaluations": gt_evaluations
    }

    print_results_table(results)
    return results

def print_results_table(results: Dict[str, Any]) -> None:
    """Formats and prints the canonical evaluation benchmark results table."""
    print("\n" + "=" * 80)
    print(" DRIFTLINE WHOLE-PIPELINE ACCURACY BENCHMARK RESULTS")
    print("=" * 80)
    print(f" Metric Name               : {results['metric_name']} (ID #{results['metric_id']})")
    print(f" Total Observations        : {results['total_observations']} rows (731 days, 9 segments)")
    print(f" Total Anomalies Flagged   : {results['total_anomalies_flagged']}")
    print("-" * 80)
    print(" METRIC NAME                      VALUE       TARGET / BENCHMARK      STATUS")
    print("-" * 80)
    
    rec = results['detection_recall']
    rec_status = "PASS" if rec >= 0.75 else "FAIL"
    print(f" detection_recall          : {rec*100.0:6.2f}%    (>= 75.0% / 3 of 4 GT)   [{rec_status}]")

    cls_acc = results['classification_accuracy']
    cls_status = "PASS" if cls_acc >= 0.75 else "FAIL"
    print(f" classification_accuracy   : {cls_acc*100.0:6.2f}%    (>= 75.0% type match)  [{cls_status}]")

    fpr = results['false_positive_rate']
    fpr_status = "PASS" if fpr <= 0.10 else "FAIL"
    print(f" false_positive_rate       : {fpr*100.0:6.2f}%    (<= 10.0% / {results['false_positive_count']}/{results['total_untouched_days']} d) [{fpr_status}]")

    drv = results['driver_accuracy']
    drv_status = "PASS" if drv >= 0.66 else "FAIL"
    print(f" driver_accuracy           : {drv*100.0:6.2f}%    (>= 66.0% / 2 of 3 seg)  [{drv_status}]")

    unf = results['uniform_shift_proportionality']
    unf_status = "PASS" if unf else "FAIL"
    print(f" uniform_shift_prop        :  {str(unf):>5}     (15.0% ±3.0% all segs)  [{unf_status}] (mean: {results['mean_level_shift_pct']:.1f}%)")

    mape = results['forecast_MAPE']
    mape_str = f"{mape*100.0:6.2f}%" if mape is not None else "   N/A "
    mape_status = "PASS" if (mape is not None and mape <= 0.15) else "FAIL"
    print(f" forecast_MAPE (12w)       : {mape_str}    (<= 15.0% held-out)     [{mape_status}]")

    cov = results['interval_coverage']
    cov_str = f"{cov*100.0:6.2f}%" if cov is not None else "   N/A "
    cov_status = "PASS" if (cov is not None and 0.65 <= cov <= 0.95) else "FAIL"
    print(f" interval_coverage (p10-p90): {cov_str}    (65.0% .. 95.0%)       [{cov_status}]")
    print("=" * 80)

    print("\n[+] EVENT-BY-EVENT GROUND TRUTH DIAGNOSTIC BREAKDOWN:")
    for ev in results['ground_truth_evaluations']:
        det_str = f"DETECTED on {ev['detected_anomaly_date']} ({ev['detected_type']})" if ev['detected'] else "MISSED"
        cls_str = "Type Match" if ev['type_matched'] else "Type Mismatch"
        drv_str = ev['driver_explanation']
        print(f"  • [{ev['id'].upper()}] (Expected {ev['type']} on {ev['target_date']}):")
        print(f"    - Detection Status : {det_str} ({cls_str})")
        print(f"    - Driver Analysis  : {drv_str}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_pipeline_evaluation())
