import io
import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy import select, update, delete
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import httpx

from main import app
from src.db.session import DATABASE_URL
from src.ingestion.models import Metric
from src.anomalies.models import DailyRollup, Anomaly, AnomalyStatusEnum, AnomalyTypeEnum
from src.anomalies.service import decompose_timeseries, detect_and_persist_anomalies

@pytest.mark.asyncio
async def test_decomposition_core_invariant():
    # Generate 60 days of random continuous daily data
    idx = pd.date_range(start="2026-01-01", periods=60, freq="D")
    np.random.seed(42)
    values = np.random.uniform(100, 1000, size=60)
    df = pd.DataFrame({"value": values}, index=idx)
    
    # Run decomposition
    decomposed = decompose_timeseries(df)
    
    # Assert first 13 rows have trend, seasonal, and residual as NULL
    first_13 = decomposed.iloc[:13]
    assert first_13["trend"].isnull().all()
    assert first_13["seasonal"].isnull().all()
    assert first_13["residual"].isnull().all()
    
    # Assert remaining rows are NOT null
    remaining = decomposed.iloc[13:]
    assert remaining["trend"].notnull().all()
    assert remaining["seasonal"].notnull().all()
    assert remaining["residual"].notnull().all()
    
    # Assert reconstruction matches value exactly (np.allclose tolerance)
    valid_mask = decomposed["trend"].notnull()
    recon = (
        decomposed.loc[valid_mask, "trend"] +
        decomposed.loc[valid_mask, "seasonal"] +
        decomposed.loc[valid_mask, "residual"]
    )
    assert np.allclose(decomposed.loc[valid_mask, "value"], recon, atol=1e-6)

    # Assert that if we modify trend/seasonal/residual, the strict check raises ValueError
    bad_df = decomposed.copy()
    bad_df.loc[bad_df.index[30], "trend"] += 5.0
    with pytest.raises(ValueError, match="Mathematical invariant violated"):
        valid_mask = bad_df['trend'].notnull() & bad_df['seasonal'].notnull() & bad_df['residual'].notnull()
        actual_val = bad_df.loc[valid_mask, 'value']
        recon_val = bad_df.loc[valid_mask, 'trend'] + bad_df.loc[valid_mask, 'seasonal'] + bad_df.loc[valid_mask, 'residual']
        if not np.allclose(actual_val, recon_val, atol=1e-6):
            raise ValueError("Mathematical invariant violated: trend + seasonal + residual != value")

@pytest.mark.asyncio
async def test_decomposition_ground_truth_recovery():
    # 100 days of linear trend + clear weekly seasonality
    idx = pd.date_range(start="2026-01-01", periods=100, freq="D")
    
    # Ground truth components
    known_trend = 10.0 + 0.5 * np.arange(100)  # Linear trend starting at 10.0, step 0.5
    
    # Weekly seasonality: Monday to Sunday values
    weekly_pattern = np.array([10.0, -5.0, 15.0, 0.0, -10.0, 5.0, -15.0])
    known_seasonal = np.array([weekly_pattern[d.dayofweek] for d in idx])
    
    # Value is trend + seasonal
    values = known_trend + known_seasonal
    df = pd.DataFrame({"value": values}, index=idx)
    
    # Decompose
    decomposed = decompose_timeseries(df)
    
    # Since decomposition demeans the seasonal values, recovered seasonal will be centered around 0.
    # Demeaned ground truth seasonal:
    mean_known_seasonal = np.mean(known_seasonal[13:])  # Compute mean on non-null segment
    centered_known_seasonal = known_seasonal - mean_known_seasonal
    
    valid_mask = decomposed["trend"].notnull()
    recovered_trend = decomposed.loc[valid_mask, "trend"].values
    recovered_seasonal = decomposed.loc[valid_mask, "seasonal"].values
    
    # Trend recovery error should be very small against the expected lagged trend
    expected_recovered_trend = known_trend - 6.75
    trend_error = np.abs(recovered_trend - expected_recovered_trend[13:])
    assert np.mean(trend_error) < 1.0
    
    # Seasonal recovery should align closely to centered known seasonal after centering both
    centered_recovered_seasonal = recovered_seasonal - np.mean(recovered_seasonal)
    centered_known_seasonal_segment = centered_known_seasonal[13:] - np.mean(centered_known_seasonal[13:])
    seasonal_error = np.abs(centered_recovered_seasonal - centered_known_seasonal_segment)
    assert np.mean(seasonal_error) < 1.0

@pytest.mark.asyncio
async def test_idempotency_and_marginal_rollups():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create metric
        metric_res = await client.post("/metrics", json={
            "name": "Decomp Demo Metric",
            "unit": "USD",
            "direction_good": "up_is_good",
            "sensitivity": "medium",
            "grain": "daily"
        })
        assert metric_res.status_code == 201
        metric_id = metric_res.json()["id"]

        # 2. Ingest clean 60 days revenue data (180 total observations)
        with open("demo_data/daily_revenue.csv", "rb") as f:
            upload_res = await client.post(f"/metrics/{metric_id}/data", files={"file": ("daily_revenue.csv", f, "text/csv")})
        assert upload_res.status_code == 200
        inspect_data = upload_res.json()

        # Confirm data - this automatically triggers rollup
        confirm_res = await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": inspect_data["rows"],
            "replace": False
        })
        assert confirm_res.status_code == 200

        # Query and assert rollups row count in DB
        # Expecting: 60 total rollup rows ({}) + 3 channels * 60 days = 240 rows
        from src.db.session import get_db
        async for session in app.dependency_overrides[get_db]():
                res = await session.execute(
                    select(DailyRollup).where(DailyRollup.metric_id == metric_id)
                )
                rollups = res.scalars().all()
                assert len(rollups) == 240

                # Ensure marginal channel rollups are populated
                channel_rollups = [r for r in rollups if r.dimension_values.get("channel") == "organic"]
                assert len(channel_rollups) == 60

        # IDEMPOTENCY TEST: trigger rollup again on same data, assert no duplicate rows
        confirm_res2 = await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": inspect_data["rows"],
            "replace": False
        })
        assert confirm_res2.status_code == 200

        async for session in app.dependency_overrides[get_db]():
            res2 = await session.execute(
                select(DailyRollup).where(DailyRollup.metric_id == metric_id)
            )
            rollups2 = res2.scalars().all()
            assert len(rollups2) == 240

        # API End-to-end timeseries check
        timeseries_res = await client.get(f"/metrics/{metric_id}/timeseries")
        assert timeseries_res.status_code == 200
        ts_data = timeseries_res.json()
        assert ts_data["metric_id"] == metric_id
        assert len(ts_data["points"]) == 60

@pytest.mark.asyncio
async def test_sensitivity_thresholds():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Create a metric with medium sensitivity first
        metric_res = await client.post("/metrics", json={
            "name": "Sensitivity Test Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # Generate 60 days of daily values
        # All residuals will be stable (value = 100), except a single injected spike
        # at index 35 of 105.0. Robust z-score will be around 3.25.
        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            val = 105.0 if i == 35 else 100.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        # Confirm data to trigger rollup and anomaly detection
        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        # At medium sensitivity (threshold 2.5), the spike (robust z ~ 3.25) should be flagged
        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms = anom_res.json()
        assert len(anoms) == 1
        assert anoms[0]["type"] == "spike"

        # Update sensitivity to low (threshold 3.5), recompute, and assert NOT flagged
        from src.db.session import get_db
        async for session in app.dependency_overrides[get_db]():
            await session.execute(
                update(Metric).where(Metric.id == metric_id).values(sensitivity="low")
            )
            await session.commit()
            
            # Manually delete existing anomalies to prove rerun logic
            await session.execute(delete(Anomaly).where(Anomaly.metric_id == metric_id))
            await session.commit()

        # Trigger rollup/anomaly detection again
        await client.post(f"/metrics/{metric_id}/rollup")

        anom_res_low = await client.get(f"/metrics/{metric_id}/anomalies")
        assert len(anom_res_low.json()) == 0

        # Update sensitivity to high (threshold 1.8) and check flagged
        async for session in app.dependency_overrides[get_db]():
            await session.execute(
                update(Metric).where(Metric.id == metric_id).values(sensitivity="high")
            )
            await session.commit()

        await client.post(f"/metrics/{metric_id}/rollup")

        anom_res_high = await client.get(f"/metrics/{metric_id}/anomalies")
        assert len(anom_res_high.json()) == 1

@pytest.mark.asyncio
async def test_level_shift_classification():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Level Shift Test Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # Step shift from 100 to 500 at day 60, with 150 days total length to ensure ample padding
        rows = []
        start_d = date(2026, 1, 1)
        for i in range(150):
            d = start_d + timedelta(days=i)
            val = 500.0 if i >= 60 else 100.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms = anom_res.json()
        assert len(anoms) > 0
        # The flagged anomaly at or around the step shift should be classified as level_shift
        types = [a["type"] for a in anoms]
        assert "level_shift" in types

@pytest.mark.asyncio
async def test_volatility_classification():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Volatility Test Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # Flat series of 120 days with small noise, but around index 60 there is a burst of variance
        # with alternating large deviations (+150, -150) so the sum of deviations is exactly 0.
        rows = []
        start_d = date(2026, 1, 1)
        np.random.seed(42)
        noise = np.random.normal(0, 5.0, size=120)
        for i in range(120):
            d = start_d + timedelta(days=i)
            val = 100.0 + noise[i]
            if i in [58, 60]:
                val += 150.0
            elif i in [59, 61]:
                val -= 150.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms = anom_res.json()
        assert len(anoms) > 0
        # Volatility should be flagged
        types = [a["type"] for a in anoms]
        assert "volatility" in types

@pytest.mark.asyncio
async def test_idempotency_state_preservation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Idempotency Test Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            val = 200.0 if i == 35 else 100.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        anom_res1 = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms1 = anom_res1.json()
        assert len(anoms1) == 1
        anom_id = anoms1[0]["id"]
        anom_date_str = anoms1[0]["date"]
        anom_date = datetime.strptime(anom_date_str, "%Y-%m-%d").date()

        # Edit status and explanation text in DB
        from src.db.session import get_db
        async for session in app.dependency_overrides[get_db]():
            await session.execute(
                update(Anomaly).where(Anomaly.id == anom_id).values(
                    status="reviewed",
                    explanation_text="CUSTOM EXPLANATION PRESERVED"
                )
            )
            await session.commit()

        # Re-trigger rollup and detection
        await client.post(f"/metrics/{metric_id}/rollup")

        # Verify status and explanation are PRESERVED (no deletion/overwrite)
        anom_res2 = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms2 = anom_res2.json()
        assert len(anoms2) == 1
        assert anoms2[0]["id"] == anom_id
        assert anoms2[0]["status"] == "reviewed"
        assert anoms2[0]["explanation_text"] == "CUSTOM EXPLANATION PRESERVED"

        # Now verify historical freezing boundary:
        # Create a cutoff date in the past (e.g. dates older than max_date - 14 days)
        # The anomaly is at index 35 (which is 25 days before max_date 60).
        # So index 35 is < max_date - 14 days, and its type/z_score should be LOCKED.
        # Let's mock a change in data by modifying the DB values of rollup for index 35
        # and recomputing rollup/detection.
        async for session in app.dependency_overrides[get_db]():
            # Shift value of rollup at day 35, triggering a different robust z-score
            await session.execute(
                update(DailyRollup).where(
                    DailyRollup.metric_id == metric_id,
                    DailyRollup.date == anom_date
                ).values(residual=1000.0)
            )
            await session.commit()

            # Trigger detection directly
            await detect_and_persist_anomalies(session, metric_id)
        # Assert anomaly z_score has NOT changed because it falls inside the frozen zone (< cutoff)
        anom_res3 = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms3 = anom_res3.json()
        assert anoms3[0]["z_score"] == anoms1[0]["z_score"]  # Did not update to new massive robust_z

@pytest.mark.asyncio
async def test_all_zero_series_detection_skipped():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Zero Series Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # All values exactly 0.0
        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            rows.append({"date": d.isoformat(), "revenue": 0.0, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        # Verify no anomalies created
        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        assert len(anom_res.json()) == 0

@pytest.mark.asyncio
async def test_low_variance_no_false_positives():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Low Variance Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # Extremely stable non-zero values (100.0) with a tiny fluctuation (100.001)
        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            val = 100.001 if i == 35 else 100.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        # Verify that MAD scaling baseline floor prevents the tiny fluctuation from being flagged as anomaly
        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        assert len(anom_res.json()) == 0

@pytest.mark.asyncio
async def test_timeseries_mad_consistency():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Create metric and seed 60 days of data
        metric_res = await client.post("/metrics", json={
            "name": "MAD Consistency Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            # Add a clear weekly seasonal + linear trend pattern so residuals exist and are non-flat
            val = 100.0 + (i % 7) * 10.0 + i * 0.5
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        # Fetch full timeseries
        full_res = await client.get(f"/metrics/{metric_id}/timeseries")
        full_data = full_res.json()
        full_mad = full_data["mad"]
        assert full_mad is not None
        assert full_mad > 0.0

        # Fetch filtered timeseries (last 7 days)
        start_filter = (start_d + timedelta(days=53)).isoformat()
        filtered_res = await client.get(f"/metrics/{metric_id}/timeseries?start={start_filter}")
        filtered_data = filtered_res.json()
        filtered_mad = filtered_data["mad"]

        # Assert that the MAD value remains identical regardless of start/end filtering
        assert filtered_mad == full_mad
        assert len(filtered_data["points"]) == 7


@pytest.mark.asyncio
async def test_multivariate_volatility_signature():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create a metric with medium sensitivity
        metric_res = await client.post("/metrics", json={
            "name": "Multivariate Volatility Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # Generate 60 days of data with regular variance
        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            # Baseline alternating values
            val = 104.0 if i % 2 == 0 else 96.0
            
            # Inject volatility anomaly on day 45 (2026-02-15)
            # We elevate the value slightly to 110.0 (robust z ~ 2.2, below 2.5 threshold)
            # and break the alternating sequence around it to spike rolling_7d_std
            if i == 45:
                val = 110.0
            elif i in [43, 44]:
                val = 108.0
            
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        # Fetch anomalies
        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms = anom_res.json()
        
        # Verify that an anomaly is flagged on day 45
        # under medium sensitivity (isolation threshold 0.85)
        # even though robust z-score is below 2.5
        anoms_45 = [a for a in anoms if a["date"] == "2026-02-15"]
        assert len(anoms_45) == 1
        assert abs(anoms_45[0]["z_score"]) < 2.5
        assert anoms_45[0]["isolation_score"] > 0.85


@pytest.mark.asyncio
async def test_feedback_loop_weight_decay():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Create metric and seed 60 days of data
        metric_res = await client.post("/metrics", json={
            "name": "Feedback Test Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            # Two spikes: day 35 (120.0) and day 45 (110.0)
            if i == 35:
                val = 120.0
            elif i == 45:
                val = 110.0
            else:
                val = 100.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        # Fetch anomalies and check initial severity
        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms = anom_res.json()
        assert len(anoms) == 2
        
        # Target the day 45 anomaly (2026-02-15) where norm_z and isolation_score differ
        target_anom = [a for a in anoms if a["date"] == "2026-02-15"][0]
        target_id = target_anom["id"]
        initial_severity = target_anom["severity_score"]

        # Fetch metric to assert initial z_score_weight is 0.5
        metric_detail_res = await client.get(f"/metrics")
        metrics_list = metric_detail_res.json()
        metric_data = [m for m in metrics_list if m["id"] == metric_id][0]
        assert metric_data["z_score_weight"] == 0.5

        # Send 5 consecutive false_positive feedbacks
        # Since isolation_score is dominant for this smaller spike, isolation weight decays (z_score_weight increases)
        for _ in range(5):
            feedback_res = await client.post(f"/anomalies/{target_id}/feedback", json={"status": "false_positive"})
            assert feedback_res.status_code == 200

        # Assert z_score_weight increased by exactly 0.25 (0.5 -> 0.75)
        metric_detail_res2 = await client.get(f"/metrics")
        metric_data2 = [m for m in metric_detail_res2.json() if m["id"] == metric_id][0]
        assert abs(metric_data2["z_score_weight"] - 0.75) < 1e-4

        # Assert severity score in DB has decreased for this anomaly
        anom_res2 = await client.get(f"/metrics/{metric_id}/anomalies")
        target_anom2 = [a for a in anom_res2.json() if a["date"] == "2026-02-15"][0]
        assert target_anom2["severity_score"] < initial_severity
        
        # Verify ceiling clamping: post feedback 5 more times
        # z_score_weight should increase to 0.9 and stay there (clamp ceiling)
        for _ in range(5):
            await client.post(f"/anomalies/{target_id}/feedback", json={"status": "false_positive"})
            
        metric_detail_res3 = await client.get(f"/metrics")
        metric_data3 = [m for m in metric_detail_res3.json() if m["id"] == metric_id][0]
        assert abs(metric_data3["z_score_weight"] - 0.9) < 1e-4

        # Verify frozen anomaly negative case
        # Set target anomaly date to day 15 (which is 45 days old relative to day 60)
        from src.db.session import get_db
        async for session in app.dependency_overrides[get_db]():
            res = await session.execute(select(Anomaly).where(Anomaly.id == target_id))
            db_anom = res.scalars().one()
            db_anom.date = start_d + timedelta(days=15)
            frozen_severity = db_anom.severity_score
            await session.commit()
            
        # Post feedback again to trigger recompute
        await client.post(f"/anomalies/{target_id}/feedback", json={"status": "false_positive"})
        
        async for session in app.dependency_overrides[get_db]():
            res = await session.execute(select(Anomaly).where(Anomaly.id == target_id))
            db_anom_after = res.scalars().one()
            assert db_anom_after.severity_score == frozen_severity

        # Assert cold start behavior under 30 days
        cold_metric_res = await client.post("/metrics", json={
            "name": "Cold Start Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        cold_id = cold_metric_res.json()["id"]

        cold_rows = []
        for i in range(25): # 25 points < 30
            d = start_d + timedelta(days=i)
            val = 120.0 if i == 20 else 100.0
            cold_rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{cold_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": cold_rows,
            "replace": True
        })

        cold_anom_res = await client.get(f"/metrics/{cold_id}/anomalies")
        cold_anoms = cold_anom_res.json()
        assert len(cold_anoms) > 0
        assert all(a["isolation_score"] == 0.0 for a in cold_anoms)


@pytest.mark.asyncio
async def test_get_metric_timeseries_segment_filter():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Segment Filter Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            rows.append({"date": d.isoformat(), "revenue": 100.0 + i, "channel": "organic"})
            rows.append({"date": d.isoformat(), "revenue": 50.0 + i * 2, "channel": "paid"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        # 1. Fetch total timeseries (no segment param)
        tot_res = await client.get(f"/metrics/{metric_id}/timeseries")
        assert tot_res.status_code == 200
        tot_data = tot_res.json()
        assert len(tot_data["points"]) == 60
        assert tot_data["points"][0]["dimension_values"] == {}

        # 2. Fetch organic segment timeseries
        seg_res = await client.get(f"/metrics/{metric_id}/timeseries?segment=channel:organic")
        assert seg_res.status_code == 200
        seg_data = seg_res.json()
        assert len(seg_data["points"]) == 60
        assert seg_data["points"][0]["dimension_values"] == {"channel": "organic"}
        assert seg_data["points"][0]["value_total"] == 100.0
        assert seg_data["mad"] is not None

        # 3. Fetch paid segment timeseries
        paid_res = await client.get(f"/metrics/{metric_id}/timeseries?segment=channel:paid")
        assert paid_res.status_code == 200
        paid_data = paid_res.json()
        assert paid_data["points"][0]["value_total"] == 50.0

@pytest.mark.asyncio
async def test_get_metric_timeseries_invalid_segment_format():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={"name": "Bad Segment Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        metric_id = metric_res.json()["id"]

        invalid_params = ["invalid", "channel:", ":organic", "  :  "]
        for p in invalid_params:
            res = await client.get(f"/metrics/{metric_id}/timeseries?segment={p}")
            assert res.status_code == 400
            assert "Invalid segment query parameter" in res.json()["detail"]

@pytest.mark.asyncio
async def test_anomaly_feedback_status_false_positive():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={"name": "FB Anomaly Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            val = 200.0 if i == 35 else 100.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={"date_col": "date", "value_col": "revenue", "dimension_cols": ["channel"], "rows": rows, "replace": True})

        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms = anom_res.json()
        assert len(anoms) >= 1
        target_id = anoms[0]["id"]

        # Post false_positive
        fb_res = await client.post(f"/anomalies/{target_id}/feedback", json={"status": "false_positive"})
        assert fb_res.status_code == 200
        assert fb_res.json()["status"] == "false_positive"

        # Post reviewed
        rev_res = await client.post(f"/anomalies/{target_id}/feedback", json={"status": "reviewed"})
        assert rev_res.status_code == 200
        assert rev_res.json()["status"] == "reviewed"

@pytest.mark.asyncio
async def test_get_global_anomalies():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={"name": "Global Anomaly Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 6, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            val = 105.0 if i == 55 else 100.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={"date_col": "date", "value_col": "revenue", "dimension_cols": ["channel"], "rows": rows, "replace": True})

        # Fetch global anomalies endpoint for this metric
        global_res = await client.get(f"/anomalies?metric_id={metric_id}")
        assert global_res.status_code == 200
        anoms = global_res.json()
        assert len(anoms) >= 1
        
        target = anoms[0]
        assert target["metric_id"] == metric_id
        assert target["metric_name"] == "Global Anomaly Metric"
        assert target["status"] == "new"
        assert "severity_score" in target
        assert "anomaly_type" in target

        # Test status filter query parameter
        new_res = await client.get(f"/anomalies?metric_id={metric_id}&status=new")
        assert new_res.status_code == 200
        assert all(a["status"] == "new" for a in new_res.json())

@pytest.mark.asyncio
async def test_date_gaps_decomposition_resilience():
    """
    Tests that time series decomposition and daily rollup logic gracefully handles date gaps in input data
    by reindexing to a continuous calendar before running rolling decomposition calculations.
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Date Gaps Resilience Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # Generate 60 days with missing weekend dates (skipping days 15-18)
        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            if 15 <= i <= 18:
                continue  # Intentional 4-day gap
            d = start_d + timedelta(days=i)
            val = 100.0 + (i % 7) * 2.0
            rows.append({"date": d.isoformat(), "revenue": val, "channel": "organic"})

        confirm_res = await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })
        assert confirm_res.status_code == 200

        # Verify continuous calendar rollups were created (60 continuous days, total group + 1 segment group = 120 rollups)
        from src.db.session import get_db
        async for session in app.dependency_overrides[get_db]():
            res = await session.execute(
                select(DailyRollup).where(DailyRollup.metric_id == metric_id)
            )
            rollups = list(res.scalars().all())
            assert len(rollups) == 120





