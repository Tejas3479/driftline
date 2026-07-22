import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import Metric
from src.anomalies.models import DailyRollup
from src.anomalies.service import decompose_timeseries
from src.forecasting.models import Forecast
from src.forecasting.schemas import ForecastPointSchema, ForecastResultSchema

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "rolling_std_7",
    "day_of_week",
    "day_of_month",
    "month",
    "trend_index",
]

def build_forecasting_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds feature matrix from continuous daily time series DataFrame.
    DataFrame must have a DatetimeIndex or Date index and a 'value' column.
    
    Feature definitions:
      - lag_k: value.shift(k)
      - rolling_mean_w: value.shift(1).rolling(w).mean() (trailing only, no leakage)
      - rolling_std_w: value.shift(1).rolling(w).std() (trailing only, no leakage)
      - Calendar: day_of_week, day_of_month, month
      - trend_index: decomposition trend if present, else numeric integer day index
    """
    df = df.copy()
    
    # Direct lag features
    df["lag_1"] = df["value"].shift(1)
    df["lag_7"] = df["value"].shift(7)
    df["lag_14"] = df["value"].shift(14)
    df["lag_28"] = df["value"].shift(28)
    
    # Trailing rolling features (explicit shift(1) before rolling to prevent same-day leakage)
    df["rolling_mean_7"] = df["value"].shift(1).rolling(7, min_periods=1).mean()
    df["rolling_mean_28"] = df["value"].shift(1).rolling(28, min_periods=1).mean()
    df["rolling_std_7"] = df["value"].shift(1).rolling(7, min_periods=1).std().fillna(0.0)
    
    # Calendar features derived from date index
    if isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
    else:
        dates = pd.to_datetime(df.index)
        
    df["day_of_week"] = dates.dayofweek
    df["day_of_month"] = dates.day
    df["month"] = dates.month
    
    # Trend feature
    if "trend" in df.columns and df["trend"].notnull().any():
        # Fill leading NaNs in trend with first valid trend value
        df["trend_index"] = df["trend"].bfill().ffill()
    else:
        df["trend_index"] = np.arange(len(df), dtype=float)
        
    return df

def train_quantile_models(
    X: pd.DataFrame, y: pd.Series, model_backend: str = "lightgbm"
) -> Tuple[Any, Any, Any]:
    """
    Trains p10, p50, and p90 quantile regression models on feature matrix X and target y.
    Raises ValueError if trainable history is < 60 days.
    """
    if len(y) < 60:
        raise ValueError("Insufficient history for ML forecasting: minimum 60 days required")
        
    # Drop rows where lag_28 or target is NaN
    valid_mask = X[FEATURE_COLUMNS].notnull().all(axis=1) & y.notnull()
    X_train = X.loc[valid_mask, FEATURE_COLUMNS]
    y_train = y.loc[valid_mask]
    
    if len(y_train) < 7:
        raise ValueError("Insufficient history for ML forecasting: minimum 60 days required")
        
    if model_backend == "lightgbm":
        model_p10 = LGBMRegressor(
            objective="quantile", alpha=0.10, n_estimators=200, random_state=42, verbose=-1, n_jobs=-1
        )
        model_p50 = LGBMRegressor(
            objective="quantile", alpha=0.50, n_estimators=200, random_state=42, verbose=-1, n_jobs=-1
        )
        model_p90 = LGBMRegressor(
            objective="quantile", alpha=0.90, n_estimators=200, random_state=42, verbose=-1, n_jobs=-1
        )
    elif model_backend == "xgboost":
        model_p10 = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.10, tree_method="hist", n_estimators=200, random_state=42
        )
        model_p50 = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.50, tree_method="hist", n_estimators=200, random_state=42
        )
        model_p90 = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.90, tree_method="hist", n_estimators=200, random_state=42
        )
    else:
        raise ValueError(f"Unsupported model_backend: {model_backend}. Expected 'lightgbm' or 'xgboost'.")
        
    model_p10.fit(X_train, y_train)
    model_p50.fit(X_train, y_train)
    model_p90.fit(X_train, y_train)
    
    return model_p10, model_p50, model_p90

def enforce_quantile_non_crossing(
    p10: Union[float, np.ndarray], p50: Union[float, np.ndarray], p90: Union[float, np.ndarray]
) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray], Union[float, np.ndarray]]:
    """
    Enforces p10 <= p50 <= p90 quantile non-crossing invariant via quantile rearrangement (sorting).
    """
    is_scalar = np.isscalar(p10)
    p10_arr = np.atleast_1d(p10)
    p50_arr = np.atleast_1d(p50)
    p90_arr = np.atleast_1d(p90)
    
    stacked = np.column_stack([p10_arr, p50_arr, p90_arr])
    
    # Check if any row violated non-crossing
    crossed_mask = (stacked[:, 0] > stacked[:, 1]) | (stacked[:, 1] > stacked[:, 2])
    if np.any(crossed_mask):
        logger.warning("Quantile crossing detected in %d predictions; applying quantile rearrangement sorting.", np.sum(crossed_mask))
        stacked = np.sort(stacked, axis=1)
        
    res_p10, res_p50, res_p90 = stacked[:, 0], stacked[:, 1], stacked[:, 2]
    
    if is_scalar:
        return float(res_p10[0]), float(res_p50[0]), float(res_p90[0])
    return res_p10, res_p50, res_p90

def reconcile_segment_forecasts(
    total_forecasts: Dict[date, Dict[str, float]],
    segment_forecasts_map: Dict[str, Dict[date, Dict[str, float]]]
) -> Dict[str, Dict[date, Dict[str, float]]]:
    """
    Reconciles per-segment forecasts with total forecasts using p50 scaling with uncertainty band-width preservation:
      - p50 is scaled by r_50 = total_p50 / sum(raw_p50_s)
      - Raw uncertainty half-widths delta_p10 = raw_p50 - raw_p10 and delta_p90 = raw_p90 - raw_p50 are preserved
      - Reconciled p10 = rec_p50 - delta_p10, Reconciled p90 = rec_p50 + delta_p90
    
    Guarantees:
      1. sum(rec_p50_s) == total_p50
      2. rec_p10 <= rec_p50 <= rec_p90 per segment automatically by construction!
    """
    if not segment_forecasts_map:
        return {}
        
    reconciled_map: Dict[str, Dict[date, Dict[str, float]]] = {
        seg_key: {} for seg_key in segment_forecasts_map
    }
    
    # Group segment keys by dimension (e.g. 'channel:paid' -> dimension 'channel')
    dim_groups: Dict[str, List[str]] = {}
    for seg_key in segment_forecasts_map:
        dim = seg_key.split(":")[0] if ":" in seg_key else "default"
        dim_groups.setdefault(dim, []).append(seg_key)
        
    # Reconcile each target date across each dimension group
    for target_date, total_dict in total_forecasts.items():
        total_p50 = total_dict["p50"]
        
        for dim, seg_keys in dim_groups.items():
            seg_p50_sum = sum(segment_forecasts_map[s][target_date]["p50"] for s in seg_keys)
            
            # Scale-relative denominator guard: if sum is < 1% of total magnitude or < 1e-4, allocate equally
            if abs(seg_p50_sum) < 0.01 * abs(total_p50) or abs(seg_p50_sum) < 1e-4:
                r_50 = 1.0 / len(seg_keys)
                is_equal_alloc = True
            else:
                r_50 = total_p50 / seg_p50_sum
                is_equal_alloc = False
                
            for s in seg_keys:
                raw_p10 = segment_forecasts_map[s][target_date]["p10"]
                raw_p50 = segment_forecasts_map[s][target_date]["p50"]
                raw_p90 = segment_forecasts_map[s][target_date]["p90"]
                
                # Raw uncertainty band half-widths
                delta_p10 = max(0.0, raw_p50 - raw_p10)
                delta_p90 = max(0.0, raw_p90 - raw_p50)
                
                # Reconciled p50
                if is_equal_alloc:
                    rec_p50 = total_p50 * r_50
                else:
                    rec_p50 = raw_p50 * r_50
                    
                # Reconciled p10 and p90 keeping uncertainty band half-widths
                rec_p10 = rec_p50 - delta_p10
                rec_p90 = rec_p50 + delta_p90
                
                # Guarantee non-crossing
                rec_p10, rec_p50, rec_p90 = enforce_quantile_non_crossing(rec_p10, rec_p50, rec_p90)
                
                reconciled_map[s][target_date] = {
                    "p10": float(rec_p10),
                    "p50": float(rec_p50),
                    "p90": float(rec_p90),
                }
                
    return reconciled_map

async def generate_multi_step_forecast(
    metric_id: int,
    session: AsyncSession,
    horizon_days: int = 30,
    model_backend: str = "lightgbm",
    save_to_db: bool = True
) -> Dict[str, Any]:
    """
    Generates 7, 14, and 30-day quantile forecasts for total metric and per-segment metrics.
    Reconciles per-segment forecasts to match total forecast p50.
    Persists forecasts to DB using PostgreSQL ON CONFLICT DO UPDATE upsert semantics.
    """
    # 1. Query metric
    stmt_metric = select(Metric).where(Metric.id == metric_id)
    res_metric = await session.execute(stmt_metric)
    metric = res_metric.scalar_one_or_none()
    if not metric:
        raise ValueError(f"Metric {metric_id} not found")
        
    # 2. Query total daily rollups (dimension_values == {})
    stmt_rollups = (
        select(DailyRollup)
        .where(DailyRollup.metric_id == metric_id)
        .order_by(DailyRollup.date.asc())
    )
    res_rollups = await session.execute(stmt_rollups)
    all_rollups = list(res_rollups.scalars().all())
    
    total_rollups = [r for r in all_rollups if not r.dimension_values or r.dimension_values == {}]
    if len(total_rollups) < 60:
        raise ValueError(f"Metric {metric_id} has {len(total_rollups)} days of history, minimum 60 required for ML forecasting.")
        
    # Convert total rollups to DataFrame
    df_total = pd.DataFrame([
        {
            "date": pd.to_datetime(r.date),
            "value": float(r.value_total),
            "trend": float(r.trend) if r.trend is not None else np.nan,
        }
        for r in total_rollups
    ]).set_index("date").sort_index()
    
    # Fill any calendar gaps in time series
    full_idx = pd.date_range(start=df_total.index.min(), end=df_total.index.max(), freq="D")
    df_total = df_total.reindex(full_idx)
    df_total["value"] = df_total["value"].interpolate(method="linear").bfill().ffill()
    
    # Calculate trend decomposition if missing
    if "trend" not in df_total.columns or df_total["trend"].isnull().all():
        df_total = decompose_timeseries(df_total)
        
    # 3. Train total quantile models
    X_total = build_forecasting_features(df_total)
    y_total = df_total["value"]
    
    model_p10, model_p50, model_p90 = train_quantile_models(X_total, y_total, model_backend=model_backend)
    
    # Calculate trend slope over last 14 days for future trend projection
    last_14_trends = df_total["trend"].dropna().tail(14)
    if len(last_14_trends) >= 2:
        trend_slope = float(last_14_trends.iloc[-1] - last_14_trends.iloc[0]) / (len(last_14_trends) - 1)
    else:
        trend_slope = 0.0
    last_trend = float(df_total["trend"].dropna().iloc[-1]) if not df_total["trend"].dropna().empty else float(y_total.iloc[-1])
    
    # 4. Perform recursive multi-step forecasting for total metric (h = 1..30)
    as_of_date = df_total.index.max().date()
    history_values = list(df_total["value"].values)
    history_dates = list(df_total.index)
    
    total_forecasts: Dict[date, Dict[str, float]] = {}
    
    for h in range(1, horizon_days + 1):
        target_date = as_of_date + timedelta(days=h)
        target_datetime = pd.to_datetime(target_date)
        
        # Build feature vector for step h using single shared p50 trajectory
        s_val = pd.Series(history_values)
        
        lag_1 = float(s_val.iloc[-1])
        lag_7 = float(s_val.iloc[-7]) if len(s_val) >= 7 else lag_1
        lag_14 = float(s_val.iloc[-14]) if len(s_val) >= 14 else lag_7
        lag_28 = float(s_val.iloc[-28]) if len(s_val) >= 28 else lag_14
        
        rolling_mean_7 = float(s_val.tail(7).mean())
        rolling_mean_28 = float(s_val.tail(28).mean())
        rolling_std_7 = float(s_val.tail(7).std()) if len(s_val) >= 7 else 0.0
        if np.isnan(rolling_std_7):
            rolling_std_7 = 0.0
            
        day_of_week = target_datetime.dayofweek
        day_of_month = target_datetime.day
        month = target_datetime.month
        trend_index = last_trend + trend_slope * h
        
        feat_df = pd.DataFrame([{
            "lag_1": lag_1,
            "lag_7": lag_7,
            "lag_14": lag_14,
            "lag_28": lag_28,
            "rolling_mean_7": rolling_mean_7,
            "rolling_mean_28": rolling_mean_28,
            "rolling_std_7": rolling_std_7,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "month": month,
            "trend_index": trend_index,
        }])[FEATURE_COLUMNS]
        
        raw_p10 = float(model_p10.predict(feat_df)[0])
        raw_p50 = float(model_p50.predict(feat_df)[0])
        raw_p90 = float(model_p90.predict(feat_df)[0])
        
        p10, p50, p90 = enforce_quantile_non_crossing(raw_p10, raw_p50, raw_p90)
        
        total_forecasts[target_date] = {
            "p10": float(p10),
            "p50": float(p50),
            "p90": float(p90),
        }
        
        # Append p50 prediction to history values as shared pseudo-actual for step h+1
        history_values.append(float(p50))
        history_dates.append(target_datetime)

    # 5. Process per-segment forecasts
    segment_rollups_map: Dict[str, List[DailyRollup]] = {}
    for r in all_rollups:
        if r.dimension_values and r.dimension_values != {}:
            # Sort keys for consistent serialization
            sorted_dim = json.dumps(r.dimension_values, sort_keys=True)
            segment_rollups_map.setdefault(sorted_dim, []).append(r)
            
    raw_segment_forecasts_map: Dict[str, Dict[date, Dict[str, float]]] = {}
    
    for seg_key, s_rollups in segment_rollups_map.items():
        if len(s_rollups) < 60:
            # For young segments with < 60 days history, fall back to historical volume fraction of total
            total_hist_mean = df_total["value"].mean()
            seg_hist_mean = np.mean([float(r.value_total) for r in s_rollups])
            ratio = seg_hist_mean / total_hist_mean if total_hist_mean != 0 else 1.0 / len(segment_rollups_map)
            
            raw_segment_forecasts_map[seg_key] = {
                t_date: {
                    "p10": total_forecasts[t_date]["p10"] * ratio,
                    "p50": total_forecasts[t_date]["p50"] * ratio,
                    "p90": total_forecasts[t_date]["p90"] * ratio,
                }
                for t_date in total_forecasts
            }
            continue
            
        df_seg = pd.DataFrame([
            {
                "date": pd.to_datetime(r.date),
                "value": float(r.value_total),
                "trend": float(r.trend) if r.trend is not None else np.nan,
            }
            for r in s_rollups
        ]).set_index("date").sort_index()
        
        df_seg = df_seg.reindex(full_idx)
        df_seg["value"] = df_seg["value"].interpolate(method="linear").bfill().ffill()
        
        X_seg = build_forecasting_features(df_seg)
        y_seg = df_seg["value"]
        
        s_m10, s_m50, s_m90 = train_quantile_models(X_seg, y_seg, model_backend=model_backend)
        
        seg_history_vals = list(df_seg["value"].values)
        seg_forecasts: Dict[date, Dict[str, float]] = {}
        
        for h in range(1, horizon_days + 1):
            target_date = as_of_date + timedelta(days=h)
            target_datetime = pd.to_datetime(target_date)
            
            s_val = pd.Series(seg_history_vals)
            
            lag_1 = float(s_val.iloc[-1])
            lag_7 = float(s_val.iloc[-7]) if len(s_val) >= 7 else lag_1
            lag_14 = float(s_val.iloc[-14]) if len(s_val) >= 14 else lag_7
            lag_28 = float(s_val.iloc[-28]) if len(s_val) >= 28 else lag_14
            
            rolling_mean_7 = float(s_val.tail(7).mean())
            rolling_mean_28 = float(s_val.tail(28).mean())
            rolling_std_7 = float(s_val.tail(7).std()) if len(s_val) >= 7 else 0.0
            if np.isnan(rolling_std_7):
                rolling_std_7 = 0.0
                
            day_of_week = target_datetime.dayofweek
            day_of_month = target_datetime.day
            month = target_datetime.month
            trend_index = float(s_val.iloc[-1])
            
            feat_df = pd.DataFrame([{
                "lag_1": lag_1,
                "lag_7": lag_7,
                "lag_14": lag_14,
                "lag_28": lag_28,
                "rolling_mean_7": rolling_mean_7,
                "rolling_mean_28": rolling_mean_28,
                "rolling_std_7": rolling_std_7,
                "day_of_week": day_of_week,
                "day_of_month": day_of_month,
                "month": month,
                "trend_index": trend_index,
            }])[FEATURE_COLUMNS]
            
            s_raw_10 = float(s_m10.predict(feat_df)[0])
            s_raw_50 = float(s_m50.predict(feat_df)[0])
            s_raw_90 = float(s_m90.predict(feat_df)[0])
            
            sp10, sp50, sp90 = enforce_quantile_non_crossing(s_raw_10, s_raw_50, s_raw_90)
            
            seg_forecasts[target_date] = {
                "p10": float(sp10),
                "p50": float(sp50),
                "p90": float(sp90),
            }
            seg_history_vals.append(float(sp50))
            
        raw_segment_forecasts_map[seg_key] = seg_forecasts

    # 6. Reconcile per-segment forecasts
    reconciled_segment_forecasts_map = reconcile_segment_forecasts(
        total_forecasts, raw_segment_forecasts_map
    )
    
    # 7. Format forecast points and persist to DB
    model_version = f"{model_backend}-v1"
    all_forecast_records = []
    
    # Total metric records
    for target_date, fc_dict in total_forecasts.items():
        h_day = (target_date - as_of_date).days
        all_forecast_records.append({
            "metric_id": metric_id,
            "dimension_values": {},
            "forecast_date": target_date,
            "horizon_days": h_day,
            "p10": fc_dict["p10"],
            "p50": fc_dict["p50"],
            "p90": fc_dict["p90"],
            "model_version": model_version,
        })
        
    # Segment metric records
    for seg_key_json, seg_fc in reconciled_segment_forecasts_map.items():
        dim_values = json.loads(seg_key_json) if isinstance(seg_key_json, str) else seg_key_json
        for target_date, fc_dict in seg_fc.items():
            h_day = (target_date - as_of_date).days
            all_forecast_records.append({
                "metric_id": metric_id,
                "dimension_values": dim_values,
                "forecast_date": target_date,
                "horizon_days": h_day,
                "p10": fc_dict["p10"],
                "p50": fc_dict["p50"],
                "p90": fc_dict["p90"],
                "model_version": model_version,
            })
            
    if save_to_db and all_forecast_records:
        for record in all_forecast_records:
            # Use PostgreSQL ON CONFLICT DO UPDATE
            stmt_upsert = insert(Forecast).values(**record)
            stmt_upsert = stmt_upsert.on_conflict_do_update(
                constraint="uq_forecasts_metric_dim_date_horizon",
                set_={
                    "p10": stmt_upsert.excluded.p10,
                    "p50": stmt_upsert.excluded.p50,
                    "p90": stmt_upsert.excluded.p90,
                    "model_version": stmt_upsert.excluded.model_version,
                    "generated_at": func.now(),
                },
            )
            await session.execute(stmt_upsert)
        await session.commit()
        
    return {
        "metric_id": metric_id,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "model_version": model_version,
        "total_forecasts": total_forecasts,
        "segment_forecasts": reconciled_segment_forecasts_map,
        "records_count": len(all_forecast_records),
    }
