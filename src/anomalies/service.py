import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sqlalchemy import select, delete, case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import Metric, DimensionDef, Observation
from src.anomalies.models import DailyRollup, Anomaly, AnomalyTypeEnum, AnomalyStatusEnum
from src.anomalies.schemas import TimeseriesPointSchema

def decompose_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Decomposes a time series with a complete continuous date index and a 'value' column.
    Returns a copy of the DataFrame with additional columns: 'trend', 'seasonal', 'residual'.
    
    Formula:
      trend_t     = rolling(28, min_periods=14).mean()
      detrended_t = value_t - trend_t
      seasonal_d  = median(detrended_t for all t sharing day_of_week == d)  # Median for outlier robustness
      residual_t  = value_t - trend_t - seasonal_{day_of_week(t)}
    
    For rows where trend is NULL (e.g. first 13 days or gaps), trend/seasonal/residual are NULL.
    """
    df = df.copy()
    
    # Calculate trend
    df['trend'] = df['value'].rolling(window=28, min_periods=14).mean()
    
    # Calculate detrended
    df['detrended'] = df['value'] - df['trend']
    
    # Day of week (0 = Monday, 6 = Sunday)
    df['day_of_week'] = df.index.dayofweek

    # Seasonal constants (7 day-of-week medians for outlier robustness)
    seasonal_map = df.groupby('day_of_week')['detrended'].median().to_dict()
    df['seasonal'] = df['day_of_week'].map(seasonal_map)
    
    # Calculate residual
    df['residual'] = df['value'] - df['trend'] - df['seasonal']
    
    # Ensure NULL consistency for trend-null days
    null_mask = df['trend'].isnull()
    df.loc[null_mask, 'seasonal'] = np.nan
    df.loc[null_mask, 'residual'] = np.nan
    
    # Strict validation of trend + seasonal + residual == value
    valid_mask = df['trend'].notnull() & df['seasonal'].notnull() & df['residual'].notnull()
    if valid_mask.any():
        actual_val = df.loc[valid_mask, 'value']
        recon_val = df.loc[valid_mask, 'trend'] + df.loc[valid_mask, 'seasonal'] + df.loc[valid_mask, 'residual']
        if not np.allclose(actual_val, recon_val, atol=1e-6):
            raise ValueError("Mathematical invariant violated: trend + seasonal + residual != value")
            
    df = df.drop(columns=['detrended', 'day_of_week'])
    return df

async def run_daily_rollup_and_decomposition(db: AsyncSession, metric_id: int) -> None:
    """
    Groups observations, reindexes to continuous calendar, runs decomposition,
    and bulk upserts rollups to daily_rollups table. Overwrites entire history for the metric.
    """
    # 1. Fetch all observations for the metric
    obs_res = await db.execute(
        select(Observation).where(Observation.metric_id == metric_id).order_by(Observation.date)
    )
    observations = obs_res.scalars().all()
    if not observations:
        return

    # Fetch dimension definitions for the metric
    dim_defs_res = await db.execute(
        select(DimensionDef.name).where(DimensionDef.metric_id == metric_id)
    )
    dimension_names = dim_defs_res.scalars().all()

    # Get overall date range
    dates = [obs.date for obs in observations]
    min_date = min(dates)
    max_date = max(dates)
    full_date_range = pd.date_range(start=min_date, end=max_date, freq='D')

    # Prep list of all timeseries inputs
    # Format: (label_dict, list_of_observations)
    timeseries_groups: List[tuple[Dict[str, str], List[Observation]]] = []

    # Total Group (empty dimension filter)
    timeseries_groups.append(({}, list(observations)))

    # Marginal groups per dimension
    for dim_name in dimension_names:
        dim_values = set()
        for obs in observations:
            val = obs.dimension_values.get(dim_name) if obs.dimension_values else None
            dim_values.add(val if val is not None else "__unassigned__")
            
        for dim_val in dim_values:
            filtered_obs = []
            for obs in observations:
                val = obs.dimension_values.get(dim_name) if obs.dimension_values else None
                if (dim_val == "__unassigned__" and val is None) or (val == dim_val):
                    filtered_obs.append(obs)
            timeseries_groups.append(({dim_name: dim_val}, filtered_obs))

    upsert_values = []

    for dim_vals, group_obs in timeseries_groups:
        # Group by date and sum value
        records = []
        for obs in group_obs:
            records.append({"date": pd.to_datetime(obs.date), "value": obs.value})
        
        group_df = pd.DataFrame(records)
        if group_df.empty:
            continue
            
        group_df = group_df.groupby("date")["value"].sum().reset_index()
        group_df.set_index("date", inplace=True)
        
        # Reindex to continuous calendar
        group_df = group_df.reindex(full_date_range)
        
        # Decompose
        decomposed_df = decompose_timeseries(group_df)
        
        # Create DailyRollup values
        for d, row in decomposed_df.iterrows():
            d_date = d.date()
            val_tot = float(row['value']) if pd.notnull(row['value']) else 0.0
            trend = float(row['trend']) if pd.notnull(row['trend']) else None
            seasonal = float(row['seasonal']) if pd.notnull(row['seasonal']) else None
            residual = float(row['residual']) if pd.notnull(row['residual']) else None
            
            upsert_values.append({
                "metric_id": metric_id,
                "date": d_date,
                "value_total": val_tot,
                "trend": trend,
                "seasonal": seasonal,
                "residual": residual,
                "dimension_values": dim_vals
            })

    if upsert_values:
        # Run insert ON CONFLICT DO UPDATE
        stmt = insert(DailyRollup)
        update_dict = {
            'value_total': stmt.excluded.value_total,
            'trend': stmt.excluded.trend,
            'seasonal': stmt.excluded.seasonal,
            'residual': stmt.excluded.residual
        }
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['metric_id', 'date', 'dimension_values'],
            set_=update_dict
        )
        await db.execute(upsert_stmt, upsert_values)
        await db.commit()

    # Trigger anomaly detection and persistence
    await detect_and_persist_anomalies(db, metric_id)

async def get_metric(db: AsyncSession, metric_id: int) -> Optional[Metric]:
    """Retrieve metric by ID."""
    result = await db.execute(select(Metric).where(Metric.id == metric_id))
    return result.scalar_one_or_none()

def compute_scaled_mad(residuals: np.ndarray, values: np.ndarray) -> Optional[float]:
    """
    Computes the scaled Median Absolute Deviation (MAD) over a series of residuals and values.
    Returns None if the series is empty, or if the early return flat-series condition is met (mad_scaled < 1e-9).
    """
    if len(residuals) == 0:
        return None
    med_res = np.median(residuals)
    abs_devs = np.abs(residuals - med_res)
    mad = np.median(abs_devs)

    med_val = np.median(np.abs(values))
    mad_floor = 0.01 * med_val

    mad_scaled = max(mad, mad_floor)
    if mad_scaled < 1e-9:
        return None
    return float(mad_scaled)

def compute_timeseries_anomaly_signals(metric: Metric, rollups: List[DailyRollup]) -> Optional[pd.DataFrame]:
    """
    Unified source of truth for time series anomaly signals calculation.
    Returns a pandas DataFrame of valid points (where trend is not null) containing:
      - 'date'
      - 'value_total'
      - 'trend'
      - 'residual'
      - 'robust_z'
      - 'isolation_score'
      - 'norm_z'
      - 'severity_score'
    """
    if len(rollups) < 14:
        return None

    # Convert to DataFrame
    df = pd.DataFrame([
        {
            "date": r.date,
            "value_total": r.value_total,
            "trend": r.trend,
            "seasonal": r.seasonal,
            "residual": r.residual
        }
        for r in rollups
    ])
    
    # Sort and reset index to ensure continuous calendar calculations
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # 1. Compute rolling features on continuous calendar history (prevents NaN issues on trailing edge)
    df["rolling_7d_std"] = df["residual"].rolling(window=7, min_periods=1).std().fillna(0.0)
    df["val_diff"] = df["value_total"].diff()
    df["rolling_7d_mean_delta"] = df["val_diff"].rolling(window=7, min_periods=1).mean().fillna(0.0)
    df["day_of_week"] = df["date"].apply(lambda d: d.weekday())

    # 2. Filter to valid segment where trend decomposition has started
    df_valid = df[df["trend"].notnull()].copy()
    if df_valid.empty:
        return None

    # 3. Compute robust z-score via shared compute_scaled_mad
    residuals = df_valid["residual"].values
    vals = df_valid["value_total"].values
    mad_scaled = compute_scaled_mad(residuals, vals)
    if mad_scaled is None:
        return None

    med_res = np.median(residuals)
    df_valid["robust_z"] = 0.6745 * (df_valid["residual"] - med_res) / mad_scaled

    # Normalize robust_z to [0, 1] over valid history
    abs_z = df_valid["robust_z"].abs().values
    min_z = abs_z.min()
    max_z = abs_z.max()
    z_range = max_z - min_z
    if z_range > 1e-9:
        df_valid["norm_z"] = (abs_z - min_z) / z_range
    else:
        df_valid["norm_z"] = 0.0

    # 4. Cold-Start Guard check: skip IsolationForest if < 30 points
    if len(df_valid) < 30:
        df_valid["isolation_score"] = 0.0
        # Under cold start, z-score gets 100% weight, severity is not diluted
        combined = df_valid["norm_z"].values
        df_valid["severity_score"] = 100.0 / (1.0 + np.exp(-12.0 * (combined - 0.5)))
    else:
        from sklearn.ensemble import IsolationForest
        features = ['value_total', 'residual', 'robust_z', 'rolling_7d_std', 'rolling_7d_mean_delta', 'day_of_week']
        X = df_valid[features].values
        
        # Fit IsolationForest with random_state=42 for deterministic runs
        model = IsolationForest(random_state=42)
        model.fit(X)
        
        # score_samples yields negative values; multiply by -1 to get positive anomaly scores
        raw_scores = -1.0 * model.score_samples(X)
        min_score = raw_scores.min()
        max_score = raw_scores.max()
        score_range = max_score - min_score
        
        if score_range > 1e-9:
            df_valid["isolation_score"] = (raw_scores - min_score) / score_range
        else:
            df_valid["isolation_score"] = 0.0

        # Clamp isolation score to 0.0 if robust z-score magnitude is extremely small
        # to prevent tiny noise fluctuations on flat metrics from being scaled up to 1.0.
        df_valid["isolation_score"] = np.where(df_valid["robust_z"].abs() < 0.1, 0.0, df_valid["isolation_score"])

        w_z = metric.z_score_weight
        w_iso = 1.0 - w_z
        combined = w_z * df_valid["norm_z"].values + w_iso * df_valid["isolation_score"].values
        df_valid["severity_score"] = 100.0 / (1.0 + np.exp(-12.0 * (combined - 0.5)))

    return df_valid

async def detect_and_persist_anomalies(db: AsyncSession, metric_id: int) -> None:
    """
    Computes robust z-scores and IsolationForest scores, combines them into severity scores,
    and updates anomalies table with 14-day history freezing.
    """
    metric = await get_metric(db, metric_id)
    if not metric:
        return

    # Fetch total daily rollups
    rollup_res = await db.execute(
        select(DailyRollup).where(
            DailyRollup.metric_id == metric_id,
            DailyRollup.dimension_values == {}
        ).order_by(DailyRollup.date)
    )
    rollups = rollup_res.scalars().all()
    if len(rollups) < 14:
        return

    # Compute z-scores, isolation scores and severity scores
    df_valid = compute_timeseries_anomaly_signals(metric, rollups)
    if df_valid is None or df_valid.empty:
        return

    # Get metric sensitivity thresholds
    sensitivity = metric.sensitivity.value if hasattr(metric.sensitivity, 'value') else str(metric.sensitivity)
    if sensitivity == 'low':
        z_threshold = 3.5
        iso_threshold = 999.0
    elif sensitivity == 'high':
        z_threshold = 1.8
        iso_threshold = 0.70
    else:
        z_threshold = 2.5
        iso_threshold = 0.85

    # Flag if robust_z absolute value breaches threshold OR isolation_score breaches threshold
    flagged_mask = (df_valid["robust_z"].abs() > z_threshold) | (df_valid["isolation_score"] > iso_threshold)
    flagged_indices = df_valid[flagged_mask].index.tolist()
    if not flagged_indices:
        return

    max_date = df_valid["date"].max()
    cutoff_date = max_date - timedelta(days=14)

    # Centered 7-day standard deviation of residuals for volatility checking
    df_for_std = pd.DataFrame([{"date": r.date, "residual": r.residual} for r in rollups]).sort_values("date").reset_index(drop=True)
    rolling_std = df_for_std["residual"].rolling(window=7, center=True).std()
    df_valid["rolling_std_centered"] = rolling_std

    residuals_vals = df_valid["residual"].values
    vals_vals = df_valid["value_total"].values
    mad_scaled = compute_scaled_mad(residuals_vals, vals_vals)
    if mad_scaled is None:
        return

    upsert_values = []

    for idx in flagged_indices:
        row = df_valid.loc[idx]
        d_date = row["date"]
        r_z = float(row["robust_z"])
        res_val = float(row["residual"])
        iso_score = float(row["isolation_score"])
        severity_score = float(row["severity_score"])

        # Default classification
        classification = "spike" if res_val > 0 else "dip"
        explanation = f"Spike detected with robust z-score {r_z:.2f}." if res_val > 0 else f"Dip detected with robust z-score {r_z:.2f}."

        # Check Level Shift
        if idx >= 14 and idx < len(df_valid) - 14:
            trend_before = df_valid.loc[idx - 14:idx - 1, "trend"].mean()
            trend_after = df_valid.loc[idx + 1:idx + 14, "trend"].mean()
            if pd.notnull(trend_before) and pd.notnull(trend_after):
                diff = abs(trend_before - trend_after)
                if diff > 3.0 * mad_scaled:
                    classification = "level_shift"
                    explanation = f"Level shift detected: trend shifted by {diff:.2f} (threshold: {3.0*mad_scaled:.2f})."

        # Check Volatility
        if classification != "level_shift":
            if idx >= 3 and idx < len(df_valid) - 3:
                adjacent_indices = [idx - 1, idx + 1]
                adjacent_elevated = any(
                    abs(df_valid.loc[adj, "robust_z"]) > 1.8 
                    for adj in adjacent_indices 
                    if adj in df_valid.index
                )
                
                if adjacent_elevated:
                    std_local = df_valid.loc[idx, "rolling_std_centered"]
                    
                    # Exclude ±14 day buffer around idx from historical rolling-std baseline population
                    historical_slice = df_valid["rolling_std_centered"].drop(
                        index=df_valid.index[max(0, idx - 14):min(len(df_valid), idx + 15)],
                        errors="ignore"
                    )
                    baseline_std = historical_slice.median()
                    
                    if pd.notnull(std_local) and pd.notnull(baseline_std) and baseline_std > 0:
                        if std_local > 3.0 * baseline_std:
                            classification = "volatility"
                            explanation = f"Volatility detected: local std {std_local:.2f} deviates significantly from historical std {baseline_std:.2f}."

        upsert_values.append({
            "metric_id": metric_id,
            "date": d_date,
            "severity_score": severity_score,
            "type": classification,
            "z_score": r_z,
            "isolation_score": iso_score,
            "explanation_text": explanation
        })

    if upsert_values:
        stmt = insert(Anomaly)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['metric_id', 'date'],
            set_={
                'z_score': case(
                    (Anomaly.date < cutoff_date, Anomaly.z_score),
                    else_=stmt.excluded.z_score
                ),
                'type': case(
                    (Anomaly.date < cutoff_date, Anomaly.type),
                    else_=stmt.excluded.type
                ),
                'severity_score': case(
                    (Anomaly.date < cutoff_date, Anomaly.severity_score),
                    else_=stmt.excluded.severity_score
                ),
                'isolation_score': case(
                    (Anomaly.date < cutoff_date, Anomaly.isolation_score),
                    else_=stmt.excluded.isolation_score
                )
            }
        )
        await db.execute(upsert_stmt, upsert_values)
        await db.commit()

async def get_anomalies(
    db: AsyncSession,
    metric_id: int,
    status_filter: Optional[AnomalyStatusEnum] = None,
    severity_min: Optional[float] = None,
    type_filter: Optional[AnomalyTypeEnum] = None
) -> List[Anomaly]:
    """List anomalies for a metric with query filtering."""
    query = select(Anomaly).where(Anomaly.metric_id == metric_id).order_by(Anomaly.date)
    
    if status_filter:
        query = query.where(Anomaly.status == status_filter)
    if severity_min:
        query = query.where(Anomaly.severity_score >= severity_min)
    if type_filter:
        query = query.where(Anomaly.type == type_filter)
        
    res = await db.execute(query)
    return list(res.scalars().all())

async def get_anomaly_detail(db: AsyncSession, anomaly_id: int, workspace_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full details for a specific anomaly."""
    stmt = select(Anomaly, Metric).join(Metric, Anomaly.metric_id == Metric.id).where(Anomaly.id == anomaly_id)
    if workspace_id is not None:
        stmt = stmt.where(Metric.workspace_id == workspace_id)
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        return None
    anomaly, metric = row
    return {"anomaly": anomaly, "metric": metric}

async def record_anomaly_feedback(db: AsyncSession, anomaly_id: int, status: AnomalyStatusEnum, workspace_id: Optional[int] = None) -> Anomaly:
    """Record anomaly feedback (reviews, false positives, etc.) and run weight updates/updates on false positives."""
    detail = await get_anomaly_detail(db, anomaly_id, workspace_id)
    if not detail:
        raise ValueError(f"Anomaly with id {anomaly_id} not found.")
    
    anomaly = detail["anomaly"]
    anomaly.status = status

    if status == AnomalyStatusEnum.false_positive:
        metric = detail["metric"]
        rollup_res = await db.execute(
            select(DailyRollup).where(
                DailyRollup.metric_id == metric.id,
                DailyRollup.dimension_values == {}
            ).order_by(DailyRollup.date)
        )
        rollups = rollup_res.scalars().all()
        df_valid = compute_timeseries_anomaly_signals(metric, rollups)
        
        if df_valid is not None and not df_valid.empty:
            row = df_valid[df_valid["date"] == anomaly.date]
            if not row.empty:
                norm_z_val = float(row["norm_z"].values[0])
                iso_score_val = float(row["isolation_score"].values[0])

                # Tie-break: if equal or within 1e-6, treat norm_z as dominant
                if norm_z_val >= iso_score_val - 1e-6:
                    # Decay z-score weight
                    metric.z_score_weight = max(0.1, min(0.9, metric.z_score_weight - 0.05))
                else:
                    # Decay isolation weight (increases z_score_weight)
                    metric.z_score_weight = max(0.1, min(0.9, metric.z_score_weight + 0.05))

                await db.flush()

                max_date = df_valid["date"].max()
                cutoff_date = max_date - timedelta(days=14)

                anom_res = await db.execute(
                    select(Anomaly).where(Anomaly.metric_id == metric.id)
                )
                metric_anoms = anom_res.scalars().all()

                w_z = metric.z_score_weight
                w_iso = 1.0 - w_z

                for anom in metric_anoms:
                    if anom.date >= cutoff_date:
                        anom_row = df_valid[df_valid["date"] == anom.date]
                        if not anom_row.empty:
                            a_norm_z = float(anom_row["norm_z"].values[0])
                            a_iso_score = float(anom_row["isolation_score"].values[0])

                            if len(df_valid) < 30:
                                combined = a_norm_z
                            else:
                                combined = w_z * a_norm_z + w_iso * a_iso_score

                            new_severity = 100.0 / (1.0 + np.exp(-12.0 * (combined - 0.5)))
                            anom.severity_score = new_severity

    await db.commit()
    await db.refresh(anomaly)
    return anomaly

async def get_metric_timeseries(
    db: AsyncSession,
    metric_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    segment: Optional[str] = None
) -> Tuple[List[TimeseriesPointSchema], Optional[float]]:
    """
    Returns the rollup points for the requested metric, date range, and segment filter,
    along with the historical scaled MAD calculated over the target series history.
    """
    target_dim_values = {}
    if segment:
        dim_key, dim_val = segment.split(":", 1)
        target_dim_values = {dim_key.strip(): dim_val.strip()}

    # 1. Fetch entire history of rollups for this target series to compute stable historical MAD
    hist_query = select(DailyRollup).where(
        DailyRollup.metric_id == metric_id,
        DailyRollup.dimension_values == target_dim_values,
        DailyRollup.trend.is_not(None)
    ).order_by(DailyRollup.date)
    
    hist_res = await db.execute(hist_query)
    all_rollups = hist_res.scalars().all()
    
    mad_val = None
    if all_rollups:
        residuals = np.array([r.residual for r in all_rollups if r.residual is not None])
        vals = np.array([r.value_total for r in all_rollups])
        mad_val = compute_scaled_mad(residuals, vals)

    # 2. Fetch the filtered rollups for the requested range
    query = select(DailyRollup).where(
        DailyRollup.metric_id == metric_id,
        DailyRollup.dimension_values == target_dim_values
    ).order_by(DailyRollup.date)

    if start_date:
        query = query.where(DailyRollup.date >= start_date)
    if end_date:
        query = query.where(DailyRollup.date <= end_date)

    res = await db.execute(query)
    rollups = res.scalars().all()

    points = []
    for r in rollups:
        points.append(TimeseriesPointSchema(
            date=r.date,
            value_total=r.value_total,
            trend=r.trend,
            seasonal=r.seasonal,
            residual=r.residual,
            dimension_values=r.dimension_values
        ))
    return points, mad_val

async def list_global_anomalies(
    db: AsyncSession,
    status_filter: Optional[str] = None,
    metric_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Returns a list of all detected anomalies joined with Metric names,
    optionally filtered by status or metric_id, ordered by date descending.
    """
    stmt = (
        select(Anomaly, Metric.name.label("metric_name"))
        .join(Metric, Anomaly.metric_id == Metric.id)
    )

    if status_filter and status_filter.lower() != "all":
        stmt = stmt.where(Anomaly.status == status_filter.lower())

    if metric_id is not None:
        stmt = stmt.where(Anomaly.metric_id == metric_id)
        
    if workspace_id is not None:
        stmt = stmt.where(Metric.workspace_id == workspace_id)

    stmt = stmt.order_by(Anomaly.date.desc(), Anomaly.id.desc()).limit(limit)

    res = await db.execute(stmt)
    rows = res.all()

    anomalies = []
    for anom, m_name in rows:
        anomalies.append({
            "id": anom.id,
            "metric_id": anom.metric_id,
            "metric_name": m_name,
            "date": anom.date,
            "severity_score": float(anom.severity_score),
            "anomaly_type": anom.type.value if hasattr(anom.type, "value") else str(anom.type),
            "status": anom.status.value if hasattr(anom.status, "value") else str(anom.status),
            "explanation_excerpt": anom.explanation_text,
        })

    return anomalies

