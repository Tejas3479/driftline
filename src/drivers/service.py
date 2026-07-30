import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
import altair as alt
from catboost import CatBoostRegressor, Pool
from fastapi import HTTPException, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import Metric, Observation, DimensionDef, DirectionGoodEnum
from src.anomalies.models import Anomaly, DailyRollup
from src.drivers.models import AnomalyDriver
from src.drivers.schemas import SegmentContributionSchema, StructuralImportanceSchema, AnomalyDriversResponseSchema

logger = structlog.get_logger(__name__)


async def calculate_anomaly_drivers(db: AsyncSession, anomaly_id: int, workspace_id: int) -> Dict[str, Any]:
    # 1. Fetch anomaly
    anom_stmt = select(Anomaly).where(Anomaly.id == anomaly_id)
    anom_res = await db.execute(anom_stmt)
    anomaly = anom_res.scalars().first()
    if not anomaly:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Anomaly with id {anomaly_id} not found")

    # 2. Fetch metric
    metric_stmt = select(Metric).where(Metric.id == anomaly.metric_id)
    metric_res = await db.execute(metric_stmt)
    metric = metric_res.scalars().first()
    if not metric or metric.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Metric with id {anomaly.metric_id} not found")

    # 3. Fetch total daily rollup on anomaly date
    tot_stmt = select(DailyRollup).where(
        DailyRollup.metric_id == anomaly.metric_id,
        DailyRollup.date == anomaly.date,
        DailyRollup.dimension_values == {}
    )
    tot_res = await db.execute(tot_stmt)
    total_rollup = tot_res.scalars().first()
    
    if not total_rollup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Daily rollup for anomaly date {anomaly.date} not found")

    actual_total = float(total_rollup.value_total)
    trend_total = float(total_rollup.trend) if total_rollup.trend is not None else 0.0
    seasonal_total = float(total_rollup.seasonal) if total_rollup.seasonal is not None else 0.0
    baseline_expected_total = trend_total + seasonal_total
    total_delta = actual_total - baseline_expected_total

    # 4. Fetch per-segment daily rollups on anomaly date
    seg_stmt = select(DailyRollup).where(
        DailyRollup.metric_id == anomaly.metric_id,
        DailyRollup.date == anomaly.date,
        DailyRollup.dimension_values != {}
    )
    seg_res = await db.execute(seg_stmt)
    segment_rollups = seg_res.scalars().all()

    # Process segment contributions
    dimension_segments: Dict[str, List[Dict[str, Any]]] = {}
    valid_segments_all: List[Dict[str, Any]] = []

    for r in segment_rollups:
        if not r.dimension_values:
            continue
        
        # Check if segment has valid decomposition on date t
        if r.trend is None or r.seasonal is None:
            logger.debug(f"Segment {r.dimension_values} excluded on date {r.date} due to incomplete decomposition history.")
            continue

        dim_name = list(r.dimension_values.keys())[0]
        dim_val = str(r.dimension_values[dim_name])

        seg_actual = float(r.value_total)
        seg_expected = float(r.trend) + float(r.seasonal)
        seg_delta = seg_actual - seg_expected
        
        # Calculate contribution_pct safely against total_delta
        if abs(total_delta) >= 1e-4:
            contrib_pct = seg_delta / total_delta
        else:
            contrib_pct = 0.0

        seg_info = {
            "dimension": dim_name,
            "segment_value": dim_val,
            "actual_value": seg_actual,
            "expected_value": seg_expected,
            "delta": seg_delta,
            "contribution_pct": contrib_pct
        }

        if dim_name not in dimension_segments:
            dimension_segments[dim_name] = []
        dimension_segments[dim_name].append(seg_info)
        valid_segments_all.append(seg_info)

    # Sort all valid segments by absolute delta descending for overall ranking
    valid_segments_all.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Select single dimension to feature in explanation_text
    selected_dimension = None
    top_segment_info = None

    if dimension_segments:
        best_dim = None
        best_top_contrib = -1.0

        for dim_name in sorted(dimension_segments.keys()):
            segs = dimension_segments[dim_name]
            segs.sort(key=lambda x: abs(x["delta"]), reverse=True)
            top_seg = segs[0]
            top_abs_contrib = abs(top_seg["contribution_pct"])
            
            if top_abs_contrib > best_top_contrib:
                best_top_contrib = top_abs_contrib
                best_dim = dim_name
                top_segment_info = top_seg

        selected_dimension = best_dim

    # Compose LLM-Free Explanation Text
    explanation_text = compose_explanation_text(
        actual_total=actual_total,
        baseline_expected_total=baseline_expected_total,
        total_delta=total_delta,
        direction_good=metric.direction_good,
        selected_dimension=selected_dimension,
        top_segment_info=top_segment_info,
        dimension_segments=dimension_segments.get(selected_dimension, []) if selected_dimension else []
    )

    # Persist AnomalyDriver records to DB (compliance with AGENTS.md rule)
    await db.execute(delete(AnomalyDriver).where(AnomalyDriver.anomaly_id == anomaly.id))
    driver_records = []
    for rank_idx, seg in enumerate(valid_segments_all, start=1):
        driver_records.append(AnomalyDriver(
            anomaly_id=anomaly.id,
            dimension_name=seg["dimension"],
            dimension_value=seg["segment_value"],
            contribution_value=seg["delta"],
            contribution_pct=seg["contribution_pct"],
            rank=rank_idx
        ))
    if driver_records:
        db.add_all(driver_records)
    await db.commit()

    # Fetch structural importance from metric model
    raw_structural = metric.structural_importance or []
    structural_importance = [
        {"feature": str(item.get("feature", "")), "importance": float(item.get("importance", 0.0))}
        for item in raw_structural
    ]

    return {
        "anomaly_id": anomaly.id,
        "metric_id": metric.id,
        "explanation_text": explanation_text,
        "primary_dimension": selected_dimension,
        "ranked_segments": valid_segments_all,
        "structural_importance": structural_importance
    }

def compose_explanation_text(
    actual_total: float,
    baseline_expected_total: float,
    total_delta: float,
    direction_good: DirectionGoodEnum,
    selected_dimension: Optional[str],
    top_segment_info: Optional[Dict[str, Any]],
    dimension_segments: List[Dict[str, Any]]
) -> str:
    # 1. Neutral topline case
    if abs(total_delta) < 1e-4:
        val_str = f"{actual_total:.1f}".rstrip('0').rstrip('.')
        sentence_1 = f"Metric remained flat ({val_str}) vs its 28-day baseline."
        if top_segment_info:
            top_name = f"{top_segment_info['dimension']}: {top_segment_info['segment_value']}"
            shift_val = f"{abs(top_segment_info['delta']):.1f}".rstrip('0').rstrip('.')
            sentence_2 = f"{top_name} drove the largest segment shift of {shift_val}."
        else:
            sentence_2 = "All segments remained within normal range."
        return f"{sentence_1} {sentence_2}"

    # 2. Determine semantic direction word
    is_up = total_delta > 0
    if is_up:
        direction_word = "Increased" if direction_good == DirectionGoodEnum.up_is_good else "Declined"
    else:
        direction_word = "Declined" if direction_good == DirectionGoodEnum.up_is_good else "Improved"

    # Percentage calculation (unsigned)
    pct_val = (abs(total_delta) / baseline_expected_total) * 100.0 if baseline_expected_total > 0 else 0.0
    pct_str = f"{pct_val:.1f}%"
    delta_str = f"{abs(total_delta):.1f}".rstrip('0').rstrip('.')

    sentence_1 = f"{direction_word} {delta_str} ({pct_str}) vs its 28-day baseline."

    if not selected_dimension or not top_segment_info:
        return sentence_1

    # Format top segment phrasing
    top_name = f"{top_segment_info['dimension']}: {top_segment_info['segment_value']}"
    top_abs_contrib = abs(top_segment_info["contribution_pct"]) * 100.0
    top_contrib_str = f"{top_abs_contrib:.1f}%"
    top_delta = top_segment_info["delta"]
    top_is_same_direction = (top_delta > 0) == (total_delta > 0)
    verb = "contributing" if top_is_same_direction else "offsetting"

    # Multi-segment anomaly check
    anomalous_segments = [s for s in dimension_segments if abs(s["contribution_pct"]) >= 0.15]
    if len(anomalous_segments) > 1:
        sentence_2 = f"{top_name} was the primary driver, {verb} {top_contrib_str} of the shift. Other {selected_dimension} segments also experienced significant shifts."
    else:
        sentence_2 = f"This was primarily driven by {top_name}, {verb} {top_contrib_str} of the shift."

    return f"{sentence_1} {sentence_2}"


async def train_and_persist_structural_importance(db: AsyncSession, metric_id: int) -> List[Dict[str, Any]]:
    """
    Trains CatBoostRegressor on raw observations to compute global structural feature importance.
    Stores array of {feature: str, importance: float} on Metric.structural_importance.
    """
    # 1. Fetch metric
    metric_stmt = select(Metric).where(Metric.id == metric_id)
    m_res = await db.execute(metric_stmt)
    metric = m_res.scalars().first()
    if not metric:
        return []

    # 2. Fetch raw observations
    obs_stmt = select(Observation).where(Observation.metric_id == metric_id).order_by(Observation.date.asc())
    obs_res = await db.execute(obs_stmt)
    observations = obs_res.scalars().all()

    # Check 30-day minimum history guard
    distinct_dates = {obs.date for obs in observations}
    if len(distinct_dates) < 30:
        logger.info(f"Skipping CatBoost structural importance for metric {metric_id}: history ({len(distinct_dates)} days) < 30 days.")
        return metric.structural_importance or []

    # Prepare DataFrame for CatBoost
    records = []
    min_date = min(distinct_dates)
    dimension_cols = set()

    for obs in observations:
        row = {
            "date": obs.date,
            "day_of_week": obs.date.weekday(),
            "trend_index": (obs.date - min_date).days,
            "value": float(obs.value)
        }
        if obs.dimension_values:
            for k, v in obs.dimension_values.items():
                dimension_cols.add(k)
                row[k] = str(v) if v is not None else "__unassigned__"
        records.append(row)

    df = pd.DataFrame(records)
    dim_col_list = sorted(list(dimension_cols))
    
    # Fill missing dimension values for any columns
    for col in dim_col_list:
        if col not in df.columns:
            df[col] = "__unassigned__"
        else:
            df[col] = df[col].fillna("__unassigned__")

    feature_cols = ["day_of_week", "trend_index"] + dim_col_list
    cat_cols = dim_col_list

    if df["value"].nunique() <= 1:
        logger.info(f"Skipping CatBoost structural importance for metric {metric_id}: target values are constant.")
        return metric.structural_importance or []

    try:
        async with db.begin_nested():
            train_pool = Pool(
                data=df[feature_cols],
                label=df["value"],
                cat_features=cat_cols
            )

            model = CatBoostRegressor(iterations=300, verbose=False)
            model.fit(train_pool)

            imp_df = model.get_feature_importance(train_pool, type='PredictionValuesChange', prettified=True)

            structural_results = []
            for _, row in imp_df.iterrows():
                feat_name = str(row["Feature Id"])
                imp_val = float(row["Importances"])
                structural_results.append({
                    "feature": feat_name,
                    "importance": round(imp_val, 2)
                })

            metric.structural_importance = structural_results
        await db.commit()
        return structural_results

    except Exception as e:
        logger.error(f"CatBoost training failed for metric {metric_id}: {str(e)}", exc_info=True)
        # Preserve existing metric.structural_importance on savepoint rollback
        return metric.structural_importance or []

async def generate_segment_comparison_spec(
    db: AsyncSession,
    metric_id: int,
    dimension: Optional[str] = None,
    range_token: Optional[str] = "all",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Generates a Vega-Lite JSON specification dictionary comparing all segments of a dimension
    side by side on a shared y-scale using Altair faceting.
    """
    # 1. Fetch metric
    metric_stmt = select(Metric).where(Metric.id == metric_id)
    metric_res = await db.execute(metric_stmt)
    metric = metric_res.scalars().first()
    if not metric:
        raise ValueError(f"Metric #{metric_id} not found")

    # 2. Fetch dimension definitions ordered deterministically by id asc
    dim_stmt = select(DimensionDef).where(DimensionDef.metric_id == metric_id).order_by(DimensionDef.id.asc())
    dim_res = await db.execute(dim_stmt)
    dimensions = list(dim_res.scalars().all())

    if not dimensions:
        raise ValueError(f"Metric #{metric_id} has no configured dimensions")

    available_dim_names = [d.name for d in dimensions]

    if dimension is not None:
        if dimension not in available_dim_names:
            raise ValueError(f"Unknown dimension '{dimension}' for metric #{metric_id}")
        target_dim = dimension
    else:
        target_dim = available_dim_names[0]

    # 3. Determine max_date in DailyRollup for server-side range token anchoring
    max_date_stmt = select(func.max(DailyRollup.date)).where(DailyRollup.metric_id == metric_id)
    max_date = await db.scalar(max_date_stmt)

    cutoff_date: Optional[date] = start_date
    if cutoff_date is None and range_token and range_token != "all" and max_date is not None:
        if range_token == "7d":
            cutoff_date = max_date - timedelta(days=7)
        elif range_token == "30d":
            cutoff_date = max_date - timedelta(days=30)
        elif range_token == "90d":
            cutoff_date = max_date - timedelta(days=90)
        elif range_token == "1y":
            cutoff_date = max_date - timedelta(days=365)

    # 4. Query DailyRollups for target_dim using JSONB has_key (jsonb_exists)
    query_stmt = select(DailyRollup).where(
        DailyRollup.metric_id == metric_id,
        func.jsonb_exists(DailyRollup.dimension_values, target_dim)
    )

    if cutoff_date:
        query_stmt = query_stmt.where(DailyRollup.date >= cutoff_date)
    if end_date:
        query_stmt = query_stmt.where(DailyRollup.date <= end_date)

    query_stmt = query_stmt.order_by(DailyRollup.date.asc())

    res = await db.execute(query_stmt)
    rollups = list(res.scalars().all())

    records = []
    for r in rollups:
        seg_val = r.dimension_values.get(target_dim, "__unassigned__")
        records.append({
            "date": r.date.isoformat(),
            "value": float(r.value_total),
            "segment_value": str(seg_val)
        })

    if not records:
        df = pd.DataFrame(columns=["date", "value", "segment_value"])
        chart = alt.Chart(df).mark_line().encode(
            x='date:T',
            y='value:Q',
        ).facet(column='segment_value:N').properties(
            title=f"Segment Comparison for {metric.name} ({target_dim})"
        )
        return chart.to_dict()

    df = pd.DataFrame(records)

    # 5. Compute relative y-domain padding across all segment values
    y_min = float(df["value"].min())
    y_max = float(df["value"].max())
    y_diff = y_max - y_min
    padding = y_diff * 0.05 if y_diff > 0 else (abs(y_max) * 0.05 or 1.0)
    y_domain = [y_min - padding, y_max + padding]

    # 6. Build Altair chart with shared scale and faceting
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X('date:T', title='Date'),
        y=alt.Y('value:Q', scale=alt.Scale(domain=y_domain), title='Value'),
        color=alt.Color('segment_value:N', legend=None),
        tooltip=['date:T', 'segment_value:N', 'value:Q']
    ).facet(
        facet=alt.Facet('segment_value:N', title=f'Segment ({target_dim})'),
        columns=3
    ).properties(
        title=f"Segment Comparison for {metric.name} ({target_dim})"
    )

    return chart.to_dict()

