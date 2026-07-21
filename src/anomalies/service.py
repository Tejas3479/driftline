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
        # Get unique values of this dimension in current observations
        dim_values = {
            obs.dimension_values.get(dim_name)
            for obs in observations
            if obs.dimension_values and obs.dimension_values.get(dim_name) is not None
        }
        for dim_val in dim_values:
            filtered_obs = [
                obs for obs in observations
                if obs.dimension_values and obs.dimension_values.get(dim_name) == dim_val
            ]
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

async def detect_and_persist_anomalies(db: AsyncSession, metric_id: int) -> None:
    """
    Computes robust z-scores on residuals using scaled MAD, maps sensitivity,
    classifies anomalies, and performs conditional upsert to freeze older values.
    """
    # 1. Fetch total daily rollups where trend is not null
    rollup_res = await db.execute(
        select(DailyRollup).where(
            DailyRollup.metric_id == metric_id,
            DailyRollup.dimension_values == {},
            DailyRollup.trend.is_not(None)
        ).order_by(DailyRollup.date)
    )
    rollups = rollup_res.scalars().all()
    if len(rollups) < 14:
        return

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
    
    # Sort and reset index
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # 2. Compute MAD and MAD_scaled via shared helper
    residuals = df["residual"].values
    vals = df["value_total"].values
    mad_scaled = compute_scaled_mad(residuals, vals)

    # Early Return for flat/zero series
    if mad_scaled is None:
        return

    # 3. Compute robust z-score
    med_res = np.median(residuals)
    df["robust_z"] = 0.6745 * (df["residual"] - med_res) / mad_scaled

    # 4. Get metric sensitivity threshold
    metric = await get_metric(db, metric_id)
    if not metric:
        return
        
    sensitivity = metric.sensitivity.value if hasattr(metric.sensitivity, 'value') else str(metric.sensitivity)
    if sensitivity == 'low':
        threshold = 3.5
    elif sensitivity == 'high':
        threshold = 1.8
    else:
        threshold = 2.5

    # Scan for flagged dates
    flagged_indices = df[df["robust_z"].abs() > threshold].index.tolist()
    if not flagged_indices:
        return

    max_date = df["date"].max()
    cutoff_date = max_date - timedelta(days=14)

    # Centered 7-day standard deviation of residuals for volatility checking
    rolling_std = df["residual"].rolling(window=7, center=True).std()

    upsert_values = []

    for idx in flagged_indices:
        row = df.iloc[idx]
        d_date = row["date"]
        r_z = float(row["robust_z"])
        res_val = float(row["residual"])

        # Default classification
        classification = "spike" if res_val > 0 else "dip"
        explanation = f"Spike detected with robust z-score {r_z:.2f}." if res_val > 0 else f"Dip detected with robust z-score {r_z:.2f}."

        # Check Level Shift (trailing [t-14, t-1] and leading [t+1, t+14] windows inside boundaries)
        if idx >= 14 and idx < len(df) - 14:
            trend_before = df.iloc[idx - 14:idx]["trend"].mean()
            trend_after = df.iloc[idx + 1:idx + 15]["trend"].mean()
            if pd.notnull(trend_before) and pd.notnull(trend_after):
                diff = abs(trend_before - trend_after)
                if diff > 3.0 * mad_scaled:
                    classification = "level_shift"
                    explanation = f"Level shift detected: trend shifted by {diff:.2f} (threshold: {3.0*mad_scaled:.2f})."

        # Check Volatility (only if not level shift and within centered 7-day boundaries)
        # Volatility implies a sustained variance change, not a single-day event.
        # We verify that adjacent days have robust z-scores elevated (e.g. > 1.0)
        # to distinguish it from a single spike/dip.
        if classification != "level_shift":
            if idx >= 3 and idx < len(df) - 3:
                adjacent_indices = [idx - 1, idx + 1]
                adjacent_elevated = any(
                    abs(df.iloc[adj]["robust_z"]) > 1.0 
                    for adj in adjacent_indices 
                    if 0 <= adj < len(df)
                )
                
                if adjacent_elevated:
                    std_local = rolling_std.iloc[idx]
                    
                    # Exclude ±14 day buffer around idx from historical rolling-std baseline population
                    historical_slice = rolling_std.drop(index=df.index[max(0, idx - 14):min(len(df), idx + 15)])
                    baseline_std = historical_slice.median()
                    
                    if pd.notnull(std_local) and pd.notnull(baseline_std) and baseline_std > 0:
                        if std_local > 3.0 * baseline_std:
                            classification = "volatility"
                            explanation = f"Volatility detected: local std {std_local:.2f} deviates significantly from historical std {baseline_std:.2f}."

        upsert_values.append({
            "metric_id": metric_id,
            "date": d_date,
            "severity_score": abs(r_z),
            "type": classification,
            "z_score": r_z,
            "isolation_score": 0.0,
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

async def get_anomaly_detail(db: AsyncSession, anomaly_id: int) -> Optional[Anomaly]:
    """Retrieve detailed anomaly record."""
    res = await db.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
    return res.scalar_one_or_none()

async def get_metric_timeseries(
    db: AsyncSession,
    metric_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Tuple[List[TimeseriesPointSchema], Optional[float]]:
    """
    Returns the total rollup points for the requested metric and date range,
    along with the historical scaled MAD calculated over the entire metric history.
    """
    # 1. Fetch entire history of total rollups to compute stable historical MAD
    hist_query = select(DailyRollup).where(
        DailyRollup.metric_id == metric_id,
        DailyRollup.dimension_values == {},
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
        DailyRollup.dimension_values == {}
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
