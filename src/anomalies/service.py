import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import Metric, DimensionDef, Observation
from src.anomalies.models import DailyRollup
from src.anomalies.schemas import TimeseriesPointSchema

def decompose_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Decomposes a time series with a complete continuous date index and a 'value' column.
    Returns a copy of the DataFrame with additional columns: 'trend', 'seasonal', 'residual'.
    
    Formula:
      trend_t     = rolling(28, min_periods=14).mean()
      detrended_t = value_t - trend_t
      seasonal_d  = mean(detrended_t for all t sharing day_of_week == d)
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
    
    # Seasonal constants (7 day-of-week means)
    seasonal_map = df.groupby('day_of_week')['detrended'].mean().to_dict()
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

async def get_metric_timeseries(
    db: AsyncSession,
    metric_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[TimeseriesPointSchema]:
    """
    Returns the total rollup points for the requested metric and date range.
    Total rollup points have dimension_values == {}.
    """
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
    return points
