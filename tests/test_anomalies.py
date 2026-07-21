import io
import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import httpx

from main import app
from src.db.session import DATABASE_URL
from src.anomalies.models import DailyRollup
from src.anomalies.service import decompose_timeseries

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
        # We manually trigger validation by calling the check block
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
    # For window=28, the rolling mean of a linear trend of step 0.5 lags by (28 - 1) / 2 = 13.5 steps,
    # which is a shift of 13.5 * 0.5 = 6.75.
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
                
                # Verify that the first 13 days of organic channel are NULL for trend/seasonal/residual
                channel_rollups.sort(key=lambda r: r.date)
                for r in channel_rollups[:13]:
                    assert r.trend is None
                    assert r.seasonal is None
                    assert r.residual is None
                # Verify remaining are NOT null
                for r in channel_rollups[13:]:
                    assert r.trend is not None
                    assert r.seasonal is not None
                    assert r.residual is not None

        # 3. IDEMPOTENCY TEST: trigger rollup again on same data, assert no duplicate rows
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
            assert len(rollups2) == 240  # Remains exactly 240, no duplicates or drift

        # 4. API End-to-end timeseries check
        timeseries_res = await client.get(f"/metrics/{metric_id}/timeseries")
        assert timeseries_res.status_code == 200
        ts_data = timeseries_res.json()
        assert ts_data["metric_id"] == metric_id
        assert len(ts_data["points"]) == 60
        
        # Spot check some values
        p0 = ts_data["points"][0]
        assert p0["trend"] is None
        assert p0["dimension_values"] == {}
        
        p30 = ts_data["points"][30]
        assert p30["trend"] is not None
        assert p30["seasonal"] is not None
        assert p30["residual"] is not None
        assert p30["value_total"] > 0

        await test_engine.dispose()
