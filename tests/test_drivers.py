import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from main import app
from src.db.session import DATABASE_URL
from src.ingestion.models import Metric, Observation
from src.anomalies.models import Anomaly, DailyRollup
from src.drivers.service import calculate_anomaly_drivers, train_and_persist_structural_importance

@pytest.mark.asyncio
async def test_driver_mathematical_invariant():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Create metric with direction up_is_good
        metric_res = await client.post("/metrics", json={
            "name": "Invariant Test Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        # Seed 60 days of data with non-flat weekly seasonality across 2 dimensions
        # Channel (organic/paid) and Plan (starter/enterprise)
        weekly_pattern = [10.0, -5.0, 15.0, 0.0, -10.0, 5.0, -15.0]
        rows = []
        start_d = date(2026, 1, 1)

        for i in range(60):
            d = start_d + timedelta(days=i)
            s_val = weekly_pattern[d.weekday()]

            # Channel organic = 100 + s_val, paid = 50 + s_val
            # Plan starter = 80 + s_val, enterprise = 70 + s_val
            # Total sum per day = 150 + 2*s_val
            rows.append({"date": d.isoformat(), "revenue": 100.0 + s_val, "channel": "organic", "plan": "starter"})
            rows.append({"date": d.isoformat(), "revenue": 50.0 + s_val, "channel": "paid", "plan": "enterprise"})

        # Confirm ingestion
        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel", "plan"],
            "rows": rows,
            "replace": True
        })

        # Query rollups on day 35 (date 2026-02-05)
        target_date = start_d + timedelta(days=35)
        
        test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            # Fetch total rollup
            tot_res = await session.execute(
                select(DailyRollup).where(
                    DailyRollup.metric_id == metric_id,
                    DailyRollup.date == target_date,
                    DailyRollup.dimension_values == {}
                )
            )
            total_rollup = tot_res.scalars().one()
            total_delta = total_rollup.value_total - (total_rollup.trend + total_rollup.seasonal)

            # Fetch channel segment rollups
            channel_res = await session.execute(
                select(DailyRollup).where(
                    DailyRollup.metric_id == metric_id,
                    DailyRollup.date == target_date,
                    DailyRollup.dimension_values != {}
                )
            )
            seg_rollups = channel_res.scalars().all()

            channel_deltas = []
            plan_deltas = []

            for r in seg_rollups:
                if "channel" in r.dimension_values:
                    delta = r.value_total - (r.trend + r.seasonal)
                    channel_deltas.append(delta)
                elif "plan" in r.dimension_values:
                    delta = r.value_total - (r.trend + r.seasonal)
                    plan_deltas.append(delta)

            # Assert mathematical invariant: sum of channel segment deltas == total_delta
            assert len(channel_deltas) == 2
            assert abs(sum(channel_deltas) - total_delta) < 1e-5

            # Assert mathematical invariant: sum of plan segment deltas == total_delta
            assert len(plan_deltas) == 2
            assert abs(sum(plan_deltas) - total_delta) < 1e-5

        await test_engine.dispose()

@pytest.mark.asyncio
async def test_driver_young_segment_handling():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Young Segment Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)

        for i in range(60):
            d = start_d + timedelta(days=i)
            # Main segment (organic) exists for all 60 days
            rows.append({"date": d.isoformat(), "revenue": 100.0, "channel": "organic"})
            
            # Young segment (referral) starts late on day 50 (only 10 days of history on day 60)
            if i >= 50:
                rows.append({"date": d.isoformat(), "revenue": 20.0, "channel": "referral"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": rows,
            "replace": True
        })

        test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            # Query existing anomaly created during ingestion confirmation
            res = await session.execute(select(Anomaly).where(Anomaly.metric_id == metric_id))
            anoms = res.scalars().all()
            assert len(anoms) >= 1
            anomaly_id = anoms[0].id

            # Call calculate_anomaly_drivers
            driver_res = await calculate_anomaly_drivers(session, anomaly_id)
            
            # Referral segment has trend=None on day 55 (only 5 days old < 14 min_periods)
            # Assert referral is excluded from ranked_segments
            ranked = driver_res["ranked_segments"]
            segment_vals = [s["segment_value"] for s in ranked]
            assert "organic" in segment_vals
            assert "referral" not in segment_vals

        await test_engine.dispose()

@pytest.mark.asyncio
async def test_driver_anomaly_injection():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={
            "name": "Injection Driver Metric",
            "direction_good": "up_is_good",
            "sensitivity": "medium"
        })
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)

        for i in range(60):
            d = start_d + timedelta(days=i)
            # Huge drop on day 35 ONLY in organic
            val_organic = 20.0 if i == 35 else 100.0
            val_paid = 100.0
            rows.append({"date": d.isoformat(), "revenue": val_organic, "channel": "organic"})
            rows.append({"date": d.isoformat(), "revenue": val_paid, "channel": "paid"})

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
        assert len(anoms) >= 1

        target_anom = [a for a in anoms if a["date"] == "2026-02-05"][0]
        anom_id = target_anom["id"]

        # Call GET /anomalies/{id}/drivers
        drivers_res = await client.get(f"/anomalies/{anom_id}/drivers")
        assert drivers_res.status_code == 200
        data = drivers_res.json()

        ranked = data["ranked_segments"]
        assert len(ranked) >= 1
        top = ranked[0]
        assert data["primary_dimension"] == "channel"
        assert top["dimension"] == "channel"
        assert top["segment_value"] == "organic"
        assert abs(top["contribution_pct"] - 1.0) < 0.05
        assert "Declined" in data["explanation_text"]
        assert "organic" in data["explanation_text"]

@pytest.mark.asyncio
async def test_explanation_text_direction_flipping():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Case A: up_is_good + revenue drop -> Declined
        metric_a_res = await client.post("/metrics", json={"name": "Revenue Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        id_a = metric_a_res.json()["id"]

        # Case B: down_is_good + churn spike -> Declined (performance decline)
        metric_b_res = await client.post("/metrics", json={"name": "Churn Rate Metric", "direction_good": "down_is_good", "sensitivity": "medium"})
        id_b = metric_b_res.json()["id"]

        # Case C: down_is_good + churn drop -> Improved
        metric_c_res = await client.post("/metrics", json={"name": "Churn Good Metric", "direction_good": "down_is_good", "sensitivity": "medium"})
        id_c = metric_c_res.json()["id"]

        start_d = date(2026, 1, 1)

        # Seed data
        def make_rows(spike_val):
            rows = []
            for i in range(60):
                d = start_d + timedelta(days=i)
                val = spike_val if i == 35 else 100.0
                rows.append({"date": d.isoformat(), "val": val, "channel": "organic"})
            return rows

        await client.post(f"/metrics/{id_a}/data/confirm", json={"date_col": "date", "value_col": "val", "dimension_cols": ["channel"], "rows": make_rows(20.0), "replace": True})
        await client.post(f"/metrics/{id_b}/data/confirm", json={"date_col": "date", "value_col": "val", "dimension_cols": ["channel"], "rows": make_rows(200.0), "replace": True})
        await client.post(f"/metrics/{id_c}/data/confirm", json={"date_col": "date", "value_col": "val", "dimension_cols": ["channel"], "rows": make_rows(20.0), "replace": True})

        anom_a = (await client.get(f"/metrics/{id_a}/anomalies")).json()[0]
        anom_b = (await client.get(f"/metrics/{id_b}/anomalies")).json()[0]
        anom_c = (await client.get(f"/metrics/{id_c}/anomalies")).json()[0]

        drv_a = (await client.get(f"/anomalies/{anom_a['id']}/drivers")).json()
        drv_b = (await client.get(f"/anomalies/{anom_b['id']}/drivers")).json()
        drv_c = (await client.get(f"/anomalies/{anom_c['id']}/drivers")).json()

        assert drv_a["explanation_text"].startswith("Declined")
        assert drv_b["explanation_text"].startswith("Declined")
        assert drv_c["explanation_text"].startswith("Improved")

        # Unsigned percentage checks: no + or - sign in percentage string
        assert "(+" not in drv_a["explanation_text"] and "(-" not in drv_a["explanation_text"]
        assert "(+" not in drv_b["explanation_text"] and "(-" not in drv_b["explanation_text"]
        assert "(+" not in drv_c["explanation_text"] and "(-" not in drv_c["explanation_text"]

@pytest.mark.asyncio
async def test_catboost_structural_importance():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={"name": "CatBoost Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)

        for i in range(60):
            d = start_d + timedelta(days=i)
            rows.append({"date": d.isoformat(), "revenue": 100.0, "channel": "organic", "region": "us"})
            rows.append({"date": d.isoformat(), "revenue": 50.0, "channel": "paid", "region": "eu"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={"date_col": "date", "value_col": "revenue", "dimension_cols": ["channel", "region"], "rows": rows, "replace": True})

        test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # 1. Happy path: train CatBoost
            importance = await train_and_persist_structural_importance(session, metric_id)
            assert len(importance) >= 2
            feats = [item["feature"] for item in importance]
            assert "channel" in feats
            assert "region" in feats

        # 2. Test history guard (<30 days)
        cold_res = await client.post("/metrics", json={"name": "Cold Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        cold_id = cold_res.json()["id"]
        cold_rows = [{"date": (start_d + timedelta(days=i)).isoformat(), "revenue": 100.0, "channel": "organic"} for i in range(20)]
        await client.post(f"/metrics/{cold_id}/data/confirm", json={"date_col": "date", "value_col": "revenue", "dimension_cols": ["channel"], "rows": cold_rows, "replace": True})

        async with async_session() as session:
            cold_importance = await train_and_persist_structural_importance(session, cold_id)
            assert cold_importance == []

        await test_engine.dispose()

@pytest.mark.asyncio
async def test_multi_segment_anomalies_explanation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/metrics", json={"name": "Multi Segment Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)

        for i in range(60):
            d = start_d + timedelta(days=i)
            # Both organic and paid drop on day 35
            val_organic = 20.0 if i == 35 else 100.0
            val_paid = 10.0 if i == 35 else 50.0
            rows.append({"date": d.isoformat(), "revenue": val_organic, "channel": "organic"})
            rows.append({"date": d.isoformat(), "revenue": val_paid, "channel": "paid"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={"date_col": "date", "value_col": "revenue", "dimension_cols": ["channel"], "rows": rows, "replace": True})

        anom_res = await client.get(f"/metrics/{metric_id}/anomalies")
        target_anom = [a for a in anom_res.json() if a["date"] == "2026-02-05"][0]

        drivers_res = await client.get(f"/anomalies/{target_anom['id']}/drivers")
        text = drivers_res.json()["explanation_text"]

        assert "Other channel segments also experienced significant shifts." in text

@pytest.mark.asyncio
async def test_segment_comparison_spec_and_filtering():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create metric with 2 dimensions (channel, plan)
        metric_res = await client.post("/metrics", json={"name": "Segment Comparison Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        metric_id = metric_res.json()["id"]

        rows = []
        start_d = date(2026, 1, 1)
        for i in range(60):
            d = start_d + timedelta(days=i)
            rows.append({"date": d.isoformat(), "revenue": 100.0 + i, "channel": "organic", "plan": "starter"})
            rows.append({"date": d.isoformat(), "revenue": 50.0 + i, "channel": "paid", "plan": "enterprise"})
            rows.append({"date": d.isoformat(), "revenue": 25.0 + i, "channel": "referral", "plan": "starter"})

        await client.post(f"/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel", "plan"],
            "rows": rows,
            "replace": True
        })

        # 2. Test default dimension & range=all
        spec_res = await client.get(f"/metrics/{metric_id}/segment-comparison")
        assert spec_res.status_code == 200
        spec = spec_res.json()
        
        assert "$schema" in spec
        assert "facet" in spec
        assert "data" in spec

        # Extract values whether inline under data.values or top-level datasets
        def extract_records(s):
            if "values" in s.get("data", {}):
                return s["data"]["values"]
            if "datasets" in s:
                name = s.get("data", {}).get("name")
                if name and name in s["datasets"]:
                    return s["datasets"][name]
                return list(s["datasets"].values())[0]
            return []

        values = extract_records(spec)
        assert len(values) > 0
        seg_vals = set(v["segment_value"] for v in values)
        assert seg_vals == {"organic", "paid", "referral"}

        # Verify shared y-scale domain in encoding
        y_scale = spec["spec"]["encoding"]["y"]["scale"]["domain"]
        assert isinstance(y_scale, list) and len(y_scale) == 2
        assert y_scale[0] <= 25.0 # y_min around 25.0 minus padding

        # 3. Test range=7d server-side date filtering
        spec_7d_res = await client.get(f"/metrics/{metric_id}/segment-comparison?dimension=channel&range=7d")
        assert spec_7d_res.status_code == 200
        spec_7d = spec_7d_res.json()
        values_7d = extract_records(spec_7d)
        assert len(values_7d) > 0
        
        max_date = date(2026, 3, 1) # day 59 is 2026-03-01
        cutoff_7d = max_date - timedelta(days=7)
        
        for v in values_7d:
            v_date = date.fromisoformat(v["date"])
            assert v_date >= cutoff_7d

        # 4. Test invalid dimension query (400)
        invalid_dim_res = await client.get(f"/metrics/{metric_id}/segment-comparison?dimension=invalid_dim")
        assert invalid_dim_res.status_code == 400
        assert "Unknown dimension 'invalid_dim'" in invalid_dim_res.json()["detail"]

        # 5. Test metric without dimensions (400)
        nodim_res = await client.post("/metrics", json={"name": "No Dim Metric", "direction_good": "up_is_good", "sensitivity": "medium"})
        nodim_id = nodim_res.json()["id"]
        
        nodim_spec_res = await client.get(f"/metrics/{nodim_id}/segment-comparison")
        assert nodim_spec_res.status_code == 400
        assert "has no configured dimensions" in nodim_spec_res.json()["detail"]


