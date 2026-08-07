import asyncio
import json
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog
from lightgbm import LGBMRegressor
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from xgboost import XGBRegressor

from src.anomalies.models import DailyRollup
from src.anomalies.service import decompose_timeseries
from src.forecasting.models import Forecast, ForecastAccuracyLog
from src.forecasting.schemas import (
    AccuracyPointSchema,
    ForecastPointSchema,
    ForecastResultSchema,
)
from src.ingestion.models import Metric

logger = structlog.get_logger(__name__)

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
        df["trend_index"] = df["trend"].bfill().ffill()
    else:
        df["trend_index"] = np.arange(len(df), dtype=float)
        
    return df

def train_quantile_models(
    X: pd.DataFrame, y: pd.Series, model_backend: str = "lightgbm"
) -> tuple[Any, Any, Any]:
    """
    Trains p10, p50, and p90 quantile regression models on feature matrix X and target y.
    Raises ValueError if trainable history is < 60 days.
    """
    if len(y) < 60:
        raise ValueError("Insufficient history for ML forecasting: minimum 60 days required")
        
    valid_mask = X[FEATURE_COLUMNS].notnull().all(axis=1) & y.notnull()
    X_train = X.loc[valid_mask, FEATURE_COLUMNS]
    y_train = y.loc[valid_mask]
    
    if len(y_train) < 7:
        raise ValueError("Insufficient history for ML forecasting: minimum 60 days required")
        
    if model_backend == "lightgbm":
        model_p10 = LGBMRegressor(
            objective="quantile", alpha=0.10, n_estimators=50, random_state=42, verbose=-1, n_jobs=1
        )
        model_p50 = LGBMRegressor(
            objective="quantile", alpha=0.50, n_estimators=50, random_state=42, verbose=-1, n_jobs=1
        )
        model_p90 = LGBMRegressor(
            objective="quantile", alpha=0.90, n_estimators=50, random_state=42, verbose=-1, n_jobs=1
        )
    elif model_backend == "xgboost":
        model_p10 = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.10, tree_method="hist", n_estimators=50, random_state=42, n_jobs=1
        )
        model_p50 = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.50, tree_method="hist", n_estimators=50, random_state=42, n_jobs=1
        )
        model_p90 = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.90, tree_method="hist", n_estimators=50, random_state=42, n_jobs=1
        )
    else:
        raise ValueError(f"Unsupported model_backend: {model_backend}. Expected 'lightgbm' or 'xgboost'.")
        
    model_p10.fit(X_train, y_train)
    model_p50.fit(X_train, y_train)
    model_p90.fit(X_train, y_train)
    
    return model_p10, model_p50, model_p90

def enforce_quantile_non_crossing(
    p10: float | np.ndarray, p50: float | np.ndarray, p90: float | np.ndarray
) -> tuple[float | np.ndarray, float | np.ndarray, float | np.ndarray]:
    """
    Enforces p10 <= p50 <= p90 quantile non-crossing invariant via quantile rearrangement (sorting).
    """
    is_scalar = np.isscalar(p10)
    p10_arr = np.atleast_1d(p10)
    p50_arr = np.atleast_1d(p50)
    p90_arr = np.atleast_1d(p90)
    
    stacked = np.column_stack([p10_arr, p50_arr, p90_arr])
    crossed_mask = (stacked[:, 0] > stacked[:, 1]) | (stacked[:, 1] > stacked[:, 2])
    if np.any(crossed_mask):
        logger.warning("Quantile crossing detected in %d predictions; applying quantile rearrangement sorting.", np.sum(crossed_mask))
        stacked = np.sort(stacked, axis=1)
        
    res_p10, res_p50, res_p90 = stacked[:, 0], stacked[:, 1], stacked[:, 2]
    
    if is_scalar:
        return float(res_p10[0]), float(res_p50[0]), float(res_p90[0])
    return res_p10, res_p50, res_p90

def reconcile_segment_forecasts(
    total_forecasts: dict[date, dict[str, float]],
    segment_forecasts_map: dict[str, dict[date, dict[str, float]]]
) -> dict[str, dict[date, dict[str, float]]]:
    """
    Reconciles per-segment forecasts with total forecasts using p50 scaling with uncertainty band-width preservation:
      - p50 is scaled by r_50 = total_p50 / sum(raw_p50_s)
      - Raw uncertainty half-widths delta_p10 = raw_p50 - raw_p10 and delta_p90 = raw_p90 - raw_p50 are preserved
      - Reconciled p10 = rec_p50 - delta_p10, Reconciled p90 = rec_p50 + delta_p90
    """
    if not segment_forecasts_map:
        return {}
        
    reconciled_map: dict[str, dict[date, dict[str, float]]] = {
        seg_key: {} for seg_key in segment_forecasts_map
    }
    
    dim_groups: dict[str, list[str]] = {}
    for seg_key in segment_forecasts_map:
        dim = seg_key.split(":")[0] if ":" in seg_key else "default"
        dim_groups.setdefault(dim, []).append(seg_key)
        
    for target_date, total_dict in total_forecasts.items():
        total_p50 = total_dict["p50"]
        
        for dim, seg_keys in dim_groups.items():
            seg_p50_sum = sum(segment_forecasts_map[s][target_date]["p50"] for s in seg_keys)
            
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
                
                delta_p10 = max(0.0, raw_p50 - raw_p10)
                delta_p90 = max(0.0, raw_p90 - raw_p50)
                
                if is_equal_alloc:
                    rec_p50 = total_p50 * r_50
                else:
                    rec_p50 = raw_p50 * r_50
                    
                rec_p10 = rec_p50 - delta_p10
                rec_p90 = rec_p50 + delta_p90
                
                rec_p10, rec_p50, rec_p90 = enforce_quantile_non_crossing(rec_p10, rec_p50, rec_p90)
                
                reconciled_map[s][target_date] = {
                    "p10": float(rec_p10),
                    "p50": float(rec_p50),
                    "p90": float(rec_p90),
                }
                
    return reconciled_map


def format_forecast_result(metric_id: int, horizon: int, res: dict[str, Any]) -> ForecastResultSchema:
    forecast_points = []
    for target_date, fc_dict in res["total_forecasts"].items():
        h_day = (target_date - res["as_of_date"]).days
        forecast_points.append(
            ForecastPointSchema(
                metric_id=metric_id,
                forecast_date=target_date,
                horizon_days=h_day,
                p10=fc_dict["p10"],
                p50=fc_dict["p50"],
                p90=fc_dict["p90"],
                dimension_values={},
                model_version=res["model_version"],
            )
        )
        
    return ForecastResultSchema(
        metric_id=metric_id,
        horizon_days=horizon,
        as_of_date=res["as_of_date"],
        model_version=res["model_version"],
        low_confidence=res["low_confidence"],
        forecasts=forecast_points,
    )

async def generate_multi_step_forecast(
    metric_id: int,
    session: AsyncSession,
    horizon_days: int = 30,
    model_backend: str = "lightgbm",
    save_to_db: bool = True,
    cutoff_date: date | None = None,
) -> dict[str, Any]:
    """
    Generates 7, 14, and 30-day quantile forecasts for total metric and per-segment metrics.
    If history < 60 days, falls back to seasonal-naive with trend adjustment and sets low_confidence = True.
    If history >= 60 days, fits ML quantile models and sets low_confidence = False.
    Respects save_to_db parameter to prevent live database pollution during backtest runs.
    """
    # 1. Query metric
    stmt_metric = select(Metric).where(Metric.id == metric_id)
    res_metric = await session.execute(stmt_metric)
    metric = res_metric.scalar_one_or_none()
    if not metric:
        raise ValueError(f"Metric {metric_id} not found")
        
    # 2. Query rollups (optionally truncated by cutoff_date for backtest folds)
    stmt_rollups = select(DailyRollup).where(DailyRollup.metric_id == metric_id)
    if cutoff_date is not None:
        stmt_rollups = stmt_rollups.where(DailyRollup.date <= cutoff_date)
    stmt_rollups = stmt_rollups.order_by(DailyRollup.date.asc())
    
    res_rollups = await session.execute(stmt_rollups)
    all_rollups = list(res_rollups.scalars().all())
    
    total_rollups = [r for r in all_rollups if not r.dimension_values or r.dimension_values == {}]
    if len(total_rollups) == 0:
        raise ValueError(f"Metric {metric_id} has 0 days of rollup history.")
        
    def _prep_total_df():
        df = pd.DataFrame([
            {
                "date": pd.to_datetime(r.date),
                "value": float(r.value_total),
                "trend": float(r.trend) if r.trend is not None else np.nan,
            }
            for r in total_rollups
        ]).set_index("date").sort_index()
        
        f_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq="D")
        df = df.reindex(f_idx)
        df["value"] = df["value"].interpolate(method="linear").bfill().ffill()
        return df, f_idx

    df_total, full_idx = await asyncio.to_thread(_prep_total_df)
    
    if "trend" not in df_total.columns or df_total["trend"].isnull().all():
        df_total = await asyncio.to_thread(decompose_timeseries, df_total)
        
    as_of_date = df_total.index.max().date()
    history_len = len(df_total)
    
    total_forecasts: dict[date, dict[str, float]] = {}
    low_confidence = False
    
    # Check history length gate for Cold-Start Fallback vs ML Path
    if history_len < 60:
        # COLD-START FALLBACK PATH: Seasonal-naive with trend adjustment
        low_confidence = True
        model_version = "naive-seasonal-v1"
        
        values = df_total["value"].values
        mean_val = float(np.mean(values)) if len(values) > 0 else 100.0
        residuals = df_total["value"] - df_total["trend"].fillna(df_total["value"])
        residual_std = float(np.std(residuals)) if len(residuals) > 0 else 0.1 * mean_val
        if np.isnan(residual_std) or residual_std < 0.05 * abs(mean_val):
            residual_std = 0.05 * abs(mean_val)
            
        last_trend = float(df_total["trend"].dropna().iloc[-1]) if not df_total["trend"].dropna().empty else mean_val
        last_14_trends = df_total["trend"].dropna().tail(14)
        if len(last_14_trends) >= 2:
            trend_slope = float(last_14_trends.iloc[-1] - last_14_trends.iloc[0]) / (len(last_14_trends) - 1)
        else:
            trend_slope = 0.0
            
        for h in range(1, horizon_days + 1):
            target_date = as_of_date + timedelta(days=h)
            
            # value_{t-7} (fallback to value_{t-1} if history < 7)
            if history_len >= 7:
                val_t7 = float(values[-7])
            else:
                val_t7 = float(values[-1])
                
            trend_t7 = max(last_trend, 1e-4)
            trend_t = last_trend + trend_slope * h
            trend_ratio = trend_t / trend_t7 if trend_t7 != 0 else 1.0
            
            p50_naive = val_t7 * trend_ratio
            p10_naive = p50_naive - 1.28 * residual_std
            p90_naive = p50_naive + 1.28 * residual_std
            
            p10_naive, p50_naive, p90_naive = enforce_quantile_non_crossing(p10_naive, p50_naive, p90_naive)
            
            total_forecasts[target_date] = {
                "p10": float(p10_naive),
                "p50": float(p50_naive),
                "p90": float(p90_naive),
            }
            
        reconciled_segment_forecasts_map = {}
    else:
        # FULL ML MODEL PATH
        low_confidence = False
        model_version = f"{model_backend}-v1"
        
        X_total = build_forecasting_features(df_total)
        y_total = df_total["value"]
        
        model_p10, model_p50, model_p90 = await asyncio.to_thread(
            train_quantile_models, X_total, y_total, model_backend
        )
        
        last_14_trends = df_total["trend"].dropna().tail(14)
        if len(last_14_trends) >= 2:
            trend_slope = float(last_14_trends.iloc[-1] - last_14_trends.iloc[0]) / (len(last_14_trends) - 1)
        else:
            trend_slope = 0.0
        last_trend = float(df_total["trend"].dropna().iloc[-1]) if not df_total["trend"].dropna().empty else float(y_total.iloc[-1])
        
        list(df_total["value"].values)
        list(df_total.index)
        
        def _run_total_predictions():
            local_total = {}
            hist_vals = list(df_total["value"].values)
            hist_dates = list(df_total.index)
            
            for h in range(1, horizon_days + 1):
                target_date = as_of_date + timedelta(days=h)
                target_datetime = pd.to_datetime(target_date)
                
                s_val = pd.Series(hist_vals)
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
                
                local_total[target_date] = {
                    "p10": float(p10),
                    "p50": float(p50),
                    "p90": float(p90),
                }
                hist_vals.append(float(p50))
                hist_dates.append(target_datetime)
            return local_total
            
        total_forecasts = await asyncio.to_thread(_run_total_predictions)

        # Process per-segment forecasts
        segment_rollups_map: dict[str, list[DailyRollup]] = {}
        for r in all_rollups:
            if r.dimension_values and r.dimension_values != {}:
                sorted_dim = json.dumps(r.dimension_values, sort_keys=True)
                segment_rollups_map.setdefault(sorted_dim, []).append(r)
                
        raw_segment_forecasts_map: dict[str, dict[date, dict[str, float]]] = {}
        
        for seg_key, s_rollups in segment_rollups_map.items():
            if len(s_rollups) < 60:
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
                
            def _prep_and_train_seg():
                df = pd.DataFrame([
                    {
                        "date": pd.to_datetime(r.date),
                        "value": float(r.value_total),
                        "trend": float(r.trend) if r.trend is not None else np.nan,
                    }
                    for r in s_rollups
                ]).set_index("date").sort_index()
                
                df = df.reindex(full_idx)
                df["value"] = df["value"].interpolate(method="linear").bfill().ffill()
                
                X_s = build_forecasting_features(df)
                y_s = df["value"]
                
                sm10, sm50, sm90 = train_quantile_models(X_s, y_s, model_backend)
                return df, sm10, sm50, sm90
                
            df_seg, s_m10, s_m50, s_m90 = await asyncio.to_thread(_prep_and_train_seg)
            
            def _run_seg_predictions():
                seg_history_vals = list(df_seg["value"].values)
                seg_forecasts = {}
                
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
                return seg_forecasts

            raw_segment_forecasts_map[seg_key] = await asyncio.to_thread(_run_seg_predictions)

        reconciled_segment_forecasts_map = reconcile_segment_forecasts(
            total_forecasts, raw_segment_forecasts_map
        )
        
    all_forecast_records = []
    for target_date, fc_dict in total_forecasts.items():
        h_day = (target_date - as_of_date).days
        all_forecast_records.append({
            "metric_id": metric_id,
            "dimension_values": {},
            "forecast_date": target_date,
            "horizon_days": h_day,
            "model_backend": model_backend,
            "p10": fc_dict["p10"],
            "p50": fc_dict["p50"],
            "p90": fc_dict["p90"],
            "model_version": model_version,
        })
        
    for seg_key_json, seg_fc in reconciled_segment_forecasts_map.items():
        dim_values = json.loads(seg_key_json) if isinstance(seg_key_json, str) else seg_key_json
        for target_date, fc_dict in seg_fc.items():
            h_day = (target_date - as_of_date).days
            all_forecast_records.append({
                "metric_id": metric_id,
                "dimension_values": dim_values,
                "forecast_date": target_date,
                "horizon_days": h_day,
                "model_backend": model_backend,
                "p10": fc_dict["p10"],
                "p50": fc_dict["p50"],
                "p90": fc_dict["p90"],
                "model_version": model_version,
            })
            
    # Persist ONLY if save_to_db is True (prevent live DB pollution during backtest runs)
    if save_to_db and all_forecast_records:
        for record in all_forecast_records:
            stmt_upsert = insert(Forecast).values(**record)
            stmt_upsert = stmt_upsert.on_conflict_do_update(
                constraint="uq_forecasts_metric_dim_date_horizon_backend",
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
        "model_backend": model_backend,
        "model_version": model_version,
        "low_confidence": low_confidence,
        "total_forecasts": total_forecasts,
        "segment_forecasts": reconciled_segment_forecasts_map,
        "records_count": len(all_forecast_records),
    }

async def run_walk_forward_backtest(
    metric_id: int,
    session: AsyncSession,
    horizon_days: int = 7,
    model_backend: str = "lightgbm",
    max_weeks: int = 12,
) -> dict[str, Any]:
    """
    Executes expanding-window walk-forward backtest across up to 12 weekly history folds.
    Calls the EXACT same generate_multi_step_forecast pipeline with save_to_db=False.
    Enforces max(train_dates) < min(prediction_dates) to prevent future data leakage.
    Derives used_ml_model directly from fold low_confidence flag.
    Upserts evaluation results to forecast_accuracy_log in DB.
    """
    # 1. Query total rollups
    stmt = (
        select(DailyRollup)
        .where(DailyRollup.metric_id == metric_id)
        .order_by(DailyRollup.date.asc())
    )
    res = await session.execute(stmt)
    all_rollups = list(res.scalars().all())
    
    total_rollups = [r for r in all_rollups if not r.dimension_values or r.dimension_values == {}]
    if len(total_rollups) == 0:
        raise ValueError(f"Metric {metric_id} has no rollups for backtesting.")
        
    rollup_date_map = {r.date: float(r.value_total) for r in total_rollups}
    sorted_dates = sorted(rollup_date_map.keys())
    max_date = sorted_dates[-1]
    
    mean_historical_val = float(np.mean(list(rollup_date_map.values())))
    
    accuracy_records = []
    
    # 2. Iterate up to max_weeks 7-day prediction folds
    for k in range(1, max_weeks + 1):
        pred_end_date = max_date - timedelta(days=7 * (k - 1))
        pred_start_date = pred_end_date - timedelta(days=6)
        cutoff_date = pred_start_date - timedelta(days=1)
        
        # Check available training history up to cutoff_date
        train_dates = [d for d in sorted_dates if d <= cutoff_date]
        if len(train_dates) < 14:
            # Need at least 14 days to compute basic trend decomposition
            break
            
        # EXPLICIT LEAKAGE INVARIANT ASSERTION
        assert max(train_dates) < pred_start_date, (
            f"Future leakage invariant violated in fold {k}: "
            f"max train date {max(train_dates)} >= prediction start {pred_start_date}"
        )
        
        # Call exact live multi-step pipeline with save_to_db=False
        fold_res = await generate_multi_step_forecast(
            metric_id=metric_id,
            session=session,
            horizon_days=7,
            model_backend=model_backend,
            save_to_db=False,
            cutoff_date=cutoff_date,
        )
        
        # Derive used_ml_model directly from fold response (single source of truth)
        used_ml_model = not fold_res["low_confidence"]
        
        for day_offset in range(7):
            target_d = pred_start_date + timedelta(days=day_offset)
            if target_d not in rollup_date_map or target_d not in fold_res["total_forecasts"]:
                continue
                
            actual_val = rollup_date_map[target_d]
            pred_p50 = fold_res["total_forecasts"][target_d]["p50"]
            pred_p10 = fold_res["total_forecasts"][target_d]["p10"]
            pred_p90 = fold_res["total_forecasts"][target_d]["p90"]
            
            abs_err = abs(pred_p50 - actual_val)
            
            # Scale-relative zero guard on actual value for abs_pct_error
            if actual_val >= 0.01 * abs(mean_historical_val) and actual_val > 1e-4:
                abs_pct_err = abs_err / actual_val
            else:
                abs_pct_err = None
                
            in_b = (pred_p10 <= actual_val <= pred_p90)
            
            accuracy_records.append({
                "metric_id": metric_id,
                "date": target_d,
                "horizon_days": horizon_days,
                "model_backend": model_backend,
                "predicted_p10": pred_p10,
                "predicted_p50": pred_p50,
                "predicted_p90": pred_p90,
                "actual": actual_val,
                "abs_error": abs_err,
                "abs_pct_error": abs_pct_err,
                "in_bounds": in_b,
                "used_ml_model": used_ml_model,
            })
            
    # 3. Upsert records to forecast_accuracy_log table
    if accuracy_records:
        for rec in accuracy_records:
            stmt_upsert = insert(ForecastAccuracyLog).values(**rec)
            stmt_upsert = stmt_upsert.on_conflict_do_update(
                constraint="uq_forecast_accuracy_log_metric_date_horizon_backend",
                set_={
                    "predicted_p10": stmt_upsert.excluded.predicted_p10,
                    "predicted_p50": stmt_upsert.excluded.predicted_p50,
                    "predicted_p90": stmt_upsert.excluded.predicted_p90,
                    "actual": stmt_upsert.excluded.actual,
                    "abs_error": stmt_upsert.excluded.abs_error,
                    "abs_pct_error": stmt_upsert.excluded.abs_pct_error,
                    "in_bounds": stmt_upsert.excluded.in_bounds,
                    "used_ml_model": stmt_upsert.excluded.used_ml_model,
                    "created_at": func.now(),
                },
            )
            await session.execute(stmt_upsert)
        await session.commit()
        
    return {
        "metric_id": metric_id,
        "horizon_days": horizon_days,
        "model_backend": model_backend,
        "total_evaluations": len(accuracy_records),
    }

async def get_forecast_accuracy(
    metric_id: int,
    session: AsyncSession,
    horizon_days: int = 7,
    model_backend: str = "lightgbm",
    auto_run: bool = False,
) -> dict[str, Any]:
    """
    Computes aggregate accuracy metrics (MAPE, MAE, coverage_pct) over the recent 12-week window.
    Runs walk-forward backtest once if no logs exist yet.
    """
    stmt = (
        select(ForecastAccuracyLog)
        .where(
            ForecastAccuracyLog.metric_id == metric_id,
            ForecastAccuracyLog.horizon_days == horizon_days,
            ForecastAccuracyLog.model_backend == model_backend,
        )
        .order_by(ForecastAccuracyLog.date.asc())
    )
    res = await session.execute(stmt)
    logs = list(res.scalars().all())
    
    if len(logs) == 0 and auto_run:
        await run_walk_forward_backtest(
            metric_id=metric_id,
            session=session,
            horizon_days=horizon_days,
            model_backend=model_backend,
        )
        res = await session.execute(stmt)
        logs = list(res.scalars().all())
        
    if len(logs) == 0:
        return {
            "metric_id": metric_id,
            "horizon_days": horizon_days,
            "model_backend": model_backend,
            "mape": None,
            "mae": None,
            "coverage_pct": None,
            "total_evaluations": 0,
            "ml_evaluations": 0,
            "points": [],
        }
        
    # Scope aggregation to recent 12-week window (date >= max_date - 84 days)
    max_log_date = max(l.date for l in logs)
    cutoff_log_date = max_log_date - timedelta(days=84)
    recent_logs = [l for l in logs if l.date >= cutoff_log_date]
    
    ml_logs = [l for l in recent_logs if l.used_ml_model]
    valid_pct_logs = [l for l in recent_logs if l.abs_pct_error is not None]
    
    mape = float(np.mean([l.abs_pct_error for l in valid_pct_logs])) if len(valid_pct_logs) > 0 else None
    mae = float(np.mean([l.abs_error for l in recent_logs])) if len(recent_logs) > 0 else None
    
    ml_bounds = [l.in_bounds for l in ml_logs if l.in_bounds is not None]
    coverage_pct = float(np.mean([1.0 if b else 0.0 for b in ml_bounds])) if len(ml_bounds) > 0 else None
    
    points_schema = [
        AccuracyPointSchema(
            date=l.date,
            predicted_p50=l.predicted_p50,
            actual=l.actual,
            abs_error=l.abs_error,
            abs_pct_error=l.abs_pct_error,
            in_bounds=l.in_bounds,
            predicted_p10=l.predicted_p10,
            predicted_p90=l.predicted_p90,
            used_ml_model=l.used_ml_model,
        )
        for l in recent_logs
    ]
    
    return {
        "metric_id": metric_id,
        "horizon_days": horizon_days,
        "model_backend": model_backend,
        "mape": mape,
        "mae": mae,
        "coverage_pct": coverage_pct,
        "total_evaluations": len(recent_logs),
        "ml_evaluations": len(ml_logs),
        "points": points_schema,
    }
