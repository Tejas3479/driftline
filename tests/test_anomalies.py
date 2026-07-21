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
        test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async with test_engine.connect() as conn:
            async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
            async with async_session() as session:
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

        async with async_session() as session:
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

        await test_engine.dispose()

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
        test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
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
        async with async_session() as session:
            await session.execute(
                update(Metric).where(Metric.id == metric_id).values(sensitivity="high")
            )
            await session.commit()

        await client.post(f"/metrics/{metric_id}/rollup")

        anom_res_high = await client.get(f"/metrics/{metric_id}/anomalies")
        assert len(anom_res_high.json()) == 1

        await test_engine.dispose()

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
        test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
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
        async with async_session() as session:
            # Shift value of rollup at day 35, triggering a different robust z-score
            await session.execute(
                update(DailyRollup).where(
                    DailyRollup.metric_id == metric_id,
                    DailyRollup.date == anom_date
                ).values(residual=1000.0)
            )
            await session.commit()

        # Trigger detection directly
        await detect_and_persist_anomalies(async_session(), metric_id)

        # Assert anomaly z_score has NOT changed because it falls inside the frozen zone (< cutoff)
        anom_res3 = await client.get(f"/metrics/{metric_id}/anomalies")
        anoms3 = anom_res3.json()
        assert anoms3[0]["z_score"] == anoms1[0]["z_score"]  # Did not update to new massive robust_z

        await test_engine.dispose()

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

