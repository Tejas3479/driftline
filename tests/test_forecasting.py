import json
from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select, func

from src.db.models import Workspace
from src.ingestion.models import Metric
from src.anomalies.models import DailyRollup
from src.forecasting.models import Forecast
from src.forecasting.service import (
    build_forecasting_features,
    train_quantile_models,
    enforce_quantile_non_crossing,
    reconcile_segment_forecasts,
    generate_multi_step_forecast,
)

def test_feature_derivation_no_double_shift():
    """
    Asserts lag_1 == value.shift(1) directly while rolling_mean_7 uses value.shift(1).rolling(7).mean().
    Guarantees no double-shifting on lag features and no same-day lookahead leakage on rolling features.
    """
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    df = pd.DataFrame({"value": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]}, index=dates)
    
    feats = build_forecasting_features(df)
    
    # Assert lag_1 is exactly value.shift(1)
    pd.testing.assert_series_equal(feats["lag_1"], df["value"].shift(1), check_names=False)
    
    # Assert lag_7 is exactly value.shift(7)
    pd.testing.assert_series_equal(feats["lag_7"], df["value"].shift(7), check_names=False)
    
    # Assert rolling_mean_7 on index 7 (date 2026-01-08, value 80) is mean of previous 7 values (10..70) = 40.0
    # Note: date 2026-01-08's own value (80) MUST NOT be included in its rolling mean
    assert feats.loc[dates[7], "rolling_mean_7"] == 40.0

def test_quantile_crossing_invariant():
    """
    Asserts enforce_quantile_non_crossing guarantees p10 <= p50 <= p90 for scalar and array inputs,
    even when intentional crossing quantiles (e.g. p90 < p10) are passed.
    """
    # Scalar crossing test
    p10, p50, p90 = enforce_quantile_non_crossing(100.0, 50.0, 20.0)
    assert p10 == 20.0
    assert p50 == 50.0
    assert p90 == 100.0
    assert p10 <= p50 <= p90

    # Array crossing test
    raw_p10 = np.array([50.0, 120.0, 10.0])
    raw_p50 = np.array([40.0, 100.0, 20.0])
    raw_p90 = np.array([30.0, 80.0,  30.0])
    
    res_p10, res_p50, res_p90 = enforce_quantile_non_crossing(raw_p10, raw_p50, raw_p90)
    
    assert np.all(res_p10 <= res_p50)
    assert np.all(res_p50 <= res_p90)
    assert np.all(res_p10 == np.array([30.0, 80.0, 10.0]))
    assert np.all(res_p50 == np.array([40.0, 100.0, 20.0]))
    assert np.all(res_p90 == np.array([50.0, 120.0, 30.0]))

def test_60day_insufficient_history_guard():
    """
    Asserts train_quantile_models raises ValueError when history is under 60 days.
    """
    dates = pd.date_range("2026-01-01", periods=50, freq="D")
    df = pd.DataFrame({"value": np.random.randn(50)}, index=dates)
    X = build_forecasting_features(df)
    y = df["value"]
    
    with pytest.raises(ValueError, match="minimum 60 days required"):
        train_quantile_models(X, y, model_backend="lightgbm")

def test_segment_forecast_reconciliation_and_ordering():
    """
    Asserts reconciled segment p50 forecasts sum to total p50 forecast AND preserve p10 <= p50 <= p90 ordering per segment.
    """
    target_date = date(2026, 2, 1)
    
    total_forecasts = {
        target_date: {"p10": 80.0, "p50": 100.0, "p90": 120.0}
    }
    
    # Raw segments sum to 120.0 for p50, but total is 100.0 (r_50 = 100 / 120 = 5/6)
    raw_segments = {
        "channel:paid": {
            target_date: {"p10": 40.0, "p50": 60.0, "p90": 80.0}
        },
        "channel:organic": {
            target_date: {"p10": 50.0, "p50": 60.0, "p90": 70.0}
        },
    }
    
    reconciled = reconcile_segment_forecasts(total_forecasts, raw_segments)
    
    # Check sum invariant: rec_p50(paid) + rec_p50(organic) == total_p50 (100.0)
    rec_paid_p50 = reconciled["channel:paid"][target_date]["p50"]
    rec_org_p50 = reconciled["channel:organic"][target_date]["p50"]
    assert pytest.approx(rec_paid_p50 + rec_org_p50, abs=1e-6) == 100.0
    
    # Check ordering invariant for each segment: p10 <= p50 <= p90
    for seg_key in ["channel:paid", "channel:organic"]:
        sp10 = reconciled[seg_key][target_date]["p10"]
        sp50 = reconciled[seg_key][target_date]["p50"]
        sp90 = reconciled[seg_key][target_date]["p90"]
        assert sp10 <= sp50 <= sp90

def test_held_out_forecast_accuracy():
    """
    Trains on 120 days of synthetic data (trend + weekly sine wave + noise) with the final 30 days held out.
    Asserts out-of-sample p50 MAPE over the held-out 30 days is within 15%.
    """
    np.random.seed(42)
    n_days = 150
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    
    # Trend: 100 + 0.5 * t, Weekly seasonality: 10 * sin(2 * pi * t / 7)
    t = np.arange(n_days)
    synthetic_series = 100.0 + 0.5 * t + 10.0 * np.sin(2 * np.pi * t / 7.0) + np.random.normal(0, 1.0, size=n_days)
    
    df = pd.DataFrame({"value": synthetic_series}, index=dates)
    
    # Split: Train on first 120 days, evaluate on last 30 held-out days
    train_df = df.iloc[:120].copy()
    test_actuals = df.iloc[120:]["value"].values
    
    X_train = build_forecasting_features(train_df)
    y_train = train_df["value"]
    
    model_p10, model_p50, model_p90 = train_quantile_models(X_train, y_train, model_backend="lightgbm")
    
    # Perform recursive multi-step forecasting for 30 steps
    history_vals = list(train_df["value"].values)
    as_of_date = train_df.index.max().date()
    p50_preds = []
    
    for h in range(1, 31):
        target_date = as_of_date + timedelta(days=h)
        target_datetime = pd.to_datetime(target_date)
        s_val = pd.Series(history_vals)
        
        feat_df = pd.DataFrame([{
            "lag_1": float(s_val.iloc[-1]),
            "lag_7": float(s_val.iloc[-7]),
            "lag_14": float(s_val.iloc[-14]),
            "lag_28": float(s_val.iloc[-28]),
            "rolling_mean_7": float(s_val.tail(7).mean()),
            "rolling_mean_28": float(s_val.tail(28).mean()),
            "rolling_std_7": float(s_val.tail(7).std()),
            "day_of_week": target_datetime.dayofweek,
            "day_of_month": target_datetime.day,
            "month": target_datetime.month,
            "trend_index": 100.0 + 0.5 * (120 + h),
        }])
        
        pred_p50 = float(model_p50.predict(feat_df)[0])
        p50_preds.append(pred_p50)
        history_vals.append(pred_p50)
        
    p50_preds = np.array(p50_preds)
    mape = np.mean(np.abs(p50_preds - test_actuals) / test_actuals)
    
    # Assert out-of-sample MAPE is within 15% (0.15)
    assert mape <= 0.15, f"Out-of-sample held-out MAPE {mape:.4f} exceeded 0.15 threshold"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from src.db.session import DATABASE_URL

@pytest.mark.asyncio
async def test_xgboost_and_lightgbm_backends():
    """
    Asserts both LightGBM and XGBoost backends generate valid forecasts for a seeded metric in DB.
    """
    test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    TestAsyncSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
    async with TestAsyncSessionLocal() as db_session:
        res_ws = await db_session.execute(select(Workspace).limit(1))
        ws = res_ws.scalar_one_or_none()
        if not ws:
            ws = Workspace(name="Forecast WS")
            db_session.add(ws)
            await db_session.flush()
        
        metric = Metric(
            workspace_id=ws.id,
            name="Forecast Metric",
            unit="USD",
            direction_good="up_is_good",
            sensitivity="medium",
            grain="daily",
        )
        db_session.add(metric)
        await db_session.flush()
        
        # Add 70 days of rollups
        start_d = date(2026, 1, 1)
        for i in range(70):
            d = start_d + timedelta(days=i)
            val = 100.0 + i * 0.2 + (i % 7) * 2.0
            r = DailyRollup(
                metric_id=metric.id,
                date=d,
                value_total=val,
                trend=100.0 + i * 0.2,
                seasonal=(i % 7) * 2.0,
                residual=0.0,
                dimension_values={},
            )
            db_session.add(r)
        await db_session.flush()
        
        # Test LightGBM backend
        lgb_result = await generate_multi_step_forecast(
            metric.id, db_session, horizon_days=7, model_backend="lightgbm", save_to_db=False
        )
        assert lgb_result["model_version"] == "lightgbm-v1"
        assert len(lgb_result["total_forecasts"]) == 7
        for d, f_dict in lgb_result["total_forecasts"].items():
            assert f_dict["p10"] <= f_dict["p50"] <= f_dict["p90"]
            
        # Test XGBoost backend
        xgb_result = await generate_multi_step_forecast(
            metric.id, db_session, horizon_days=7, model_backend="xgboost", save_to_db=False
        )
        assert xgb_result["model_version"] == "xgboost-v1"
        assert len(xgb_result["total_forecasts"]) == 7
        for d, f_dict in xgb_result["total_forecasts"].items():
            assert f_dict["p10"] <= f_dict["p50"] <= f_dict["p90"]

@pytest.mark.asyncio
async def test_jsonb_upsert_semantics():
    """
    Asserts re-running forecast updates existing rows in DB rather than creating duplicates.
    """
    test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    TestAsyncSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
    async with TestAsyncSessionLocal() as db_session:
        res_ws = await db_session.execute(select(Workspace).limit(1))
        ws = res_ws.scalar_one_or_none()
        if not ws:
            ws = Workspace(name="Upsert WS")
            db_session.add(ws)
            await db_session.flush()
        
        metric = Metric(
            workspace_id=ws.id,
            name="Upsert Metric",
            unit="USD",
            direction_good="up_is_good",
            sensitivity="medium",
            grain="daily",
        )
        db_session.add(metric)
        await db_session.flush()
        
        start_d = date(2026, 1, 1)
        for i in range(65):
            d = start_d + timedelta(days=i)
            r = DailyRollup(
                metric_id=metric.id,
                date=d,
                value_total=150.0 + i,
                trend=150.0 + i,
                seasonal=0.0,
                residual=0.0,
                dimension_values={},
            )
            db_session.add(r)
        await db_session.flush()
        
        # Run 1
        res1 = await generate_multi_step_forecast(
            metric.id, db_session, horizon_days=7, model_backend="lightgbm", save_to_db=True
        )
        
        stmt = select(func.count()).select_from(Forecast).where(Forecast.metric_id == metric.id)
        count1 = (await db_session.execute(stmt)).scalar()
        assert count1 == 7
        
        # Run 2 (re-run forecast for same metric and dates)
        res2 = await generate_multi_step_forecast(
            metric.id, db_session, horizon_days=7, model_backend="lightgbm", save_to_db=True
        )
        
        count2 = (await db_session.execute(stmt)).scalar()
        # Assert row count remains 7 (upsert updated existing rows, no duplicates created)
        assert count2 == 7

@pytest.mark.asyncio
async def test_backtest_does_not_pollute_live_forecasts_table():
    """
    Asserts running walk-forward backtest calls save_to_db=False and leaves the live forecasts table untouched.
    """
    test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    TestAsyncSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
    async with TestAsyncSessionLocal() as db_session:
        res_ws = await db_session.execute(select(Workspace).limit(1))
        ws = res_ws.scalar_one_or_none()
        if not ws:
            ws = Workspace(name="Clean WS")
            db_session.add(ws)
            await db_session.flush()
            
        metric = Metric(
            workspace_id=ws.id,
            name="Clean Forecast Metric",
            unit="USD",
            direction_good="up_is_good",
            sensitivity="medium",
            grain="daily",
        )
        db_session.add(metric)
        await db_session.flush()
        
        start_d = date(2026, 1, 1)
        for i in range(75):
            d = start_d + timedelta(days=i)
            r = DailyRollup(
                metric_id=metric.id,
                date=d,
                value_total=200.0 + i,
                trend=200.0 + i,
                seasonal=0.0,
                residual=0.0,
                dimension_values={},
            )
            db_session.add(r)
        await db_session.flush()
        
        # Check initial live forecasts count is 0
        stmt = select(func.count()).select_from(Forecast).where(Forecast.metric_id == metric.id)
        count_before = (await db_session.execute(stmt)).scalar()
        assert count_before == 0
        
        # Run walk-forward backtest
        from src.forecasting.service import run_walk_forward_backtest
        await run_walk_forward_backtest(metric.id, db_session, horizon_days=7, max_weeks=4)
        
        # Assert live forecasts count is STILL 0 (backtest did NOT pollute live forecasts table)
        count_after = (await db_session.execute(stmt)).scalar()
        assert count_after == 0

@pytest.mark.asyncio
async def test_cold_start_fallback_and_low_confidence_flag():
    """
    Asserts a metric with <60 days history triggers seasonal-naive cold-start fallback and low_confidence=True,
    while a metric with >=60 days uses ML model path and low_confidence=False.
    """
    test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    TestAsyncSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
    async with TestAsyncSessionLocal() as db_session:
        res_ws = await db_session.execute(select(Workspace).limit(1))
        ws = res_ws.scalar_one_or_none()
        if not ws:
            ws = Workspace(name="ColdStart WS")
            db_session.add(ws)
            await db_session.flush()
            
        # 1. Young Metric (< 60 days history)
        young_metric = Metric(
            workspace_id=ws.id,
            name="Young Metric",
            unit="USD",
            direction_good="up_is_good",
            sensitivity="medium",
            grain="daily",
        )
        db_session.add(young_metric)
        await db_session.flush()
        
        start_d = date(2026, 1, 1)
        for i in range(40):  # 40 days history < 60 days
            d = start_d + timedelta(days=i)
            r = DailyRollup(
                metric_id=young_metric.id,
                date=d,
                value_total=100.0 + (i % 7) * 5.0,
                trend=100.0,
                seasonal=0.0,
                residual=0.0,
                dimension_values={},
            )
            db_session.add(r)
        await db_session.flush()
        
        young_res = await generate_multi_step_forecast(young_metric.id, db_session, horizon_days=7, save_to_db=False)
        assert young_res["low_confidence"] is True
        assert young_res["model_version"] == "naive-seasonal-v1"
        for d, f_dict in young_res["total_forecasts"].items():
            assert f_dict["p10"] <= f_dict["p50"] <= f_dict["p90"]
            
        # 2. Mature Metric (>= 60 days history)
        mature_metric = Metric(
            workspace_id=ws.id,
            name="Mature Metric",
            unit="USD",
            direction_good="up_is_good",
            sensitivity="medium",
            grain="daily",
        )
        db_session.add(mature_metric)
        await db_session.flush()
        
        for i in range(70):  # 70 days history >= 60 days
            d = start_d + timedelta(days=i)
            r = DailyRollup(
                metric_id=mature_metric.id,
                date=d,
                value_total=100.0 + i * 0.5,
                trend=100.0 + i * 0.5,
                seasonal=0.0,
                residual=0.0,
                dimension_values={},
            )
            db_session.add(r)
        await db_session.flush()
        
        mature_res = await generate_multi_step_forecast(mature_metric.id, db_session, horizon_days=7, save_to_db=False)
        assert mature_res["low_confidence"] is False
        assert mature_res["model_version"] == "lightgbm-v1"
        for d, f_dict in mature_res["total_forecasts"].items():
            assert f_dict["p10"] <= f_dict["p50"] <= f_dict["p90"]

@pytest.mark.asyncio
async def test_forecast_accuracy_endpoint():
    """
    Tests GET /metrics/{id}/forecast and GET /metrics/{id}/accuracy endpoints via httpx.AsyncClient.
    """
    import httpx
    from main import app
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Create metric
        m_res = await client.post("/metrics", json={"name": "API Forecast Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        metric_id = m_res.json()["id"]
        
        # Confirm 80 days of continuous data
        start_d = date(2026, 1, 1)
        rows = []
        for i in range(80):
            d = start_d + timedelta(days=i)
            val = 200.0 + i * 0.5 + (i % 7) * 3.0
            rows.append({"date": d.isoformat(), "revenue": val})
            
        confirm_res = await client.post(f"/metrics/{metric_id}/data/confirm", json={"date_col": "date", "value_col": "revenue", "rows": rows})
        assert confirm_res.status_code == 200
        
        # Query GET /metrics/{id}/forecast
        fc_res = await client.get(f"/metrics/{metric_id}/forecast?horizon=14")
        assert fc_res.status_code == 200
        fc_data = fc_res.json()
        assert fc_data["metric_id"] == metric_id
        assert fc_data["horizon_days"] == 14
        assert fc_data["low_confidence"] is False
        assert len(fc_data["forecasts"]) == 14
        
        # Query GET /metrics/{id}/accuracy
        acc_res = await client.get(f"/metrics/{metric_id}/accuracy?horizon=7")
        assert acc_res.status_code == 200
        acc_data = acc_res.json()
        assert acc_data["metric_id"] == metric_id
        assert acc_data["mape"] is not None
        assert acc_data["mape"] >= 0.0
        assert acc_data["coverage_pct"] is not None
        assert 0.0 <= acc_data["coverage_pct"] <= 1.0
        assert len(acc_data["points"]) > 0
        
        print(f"\n>>> DEMO METRIC OBSERVED BACKTEST MAPE: {acc_data['mape']:.4f} ({acc_data['mape']*100:.2f}%) <<<")

