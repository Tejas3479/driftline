import os
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta

from main import app
from src.ingestion.models import Metric, Observation
from src.ingestion.service import create_metric, inspect_and_validate_csv, confirm_and_persist_observations
from src.ingestion.schemas import MetricCreateSchema, DataConfirmSchema
from src.digests.models import Digest
from src.digests.service import generate_weekly_digest
from src.jobs.service import run_daily_pipeline, run_weekly_retrain_and_digest

DEMO_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo_data", "daily_revenue.csv")

@pytest.mark.asyncio
async def test_async_io_scheduler_dispatch():
    """Verifies that AsyncIOScheduler natively schedules and dispatches an async coroutine on the running loop."""
    scheduler = AsyncIOScheduler()
    executed_flag = []

    async def sample_async_job():
        executed_flag.append(True)

    scheduler.add_job(sample_async_job, trigger=DateTrigger(run_date=datetime.now() + timedelta(milliseconds=50)))
    scheduler.start()
    await asyncio.sleep(0.15)
    scheduler.shutdown(wait=False)

    assert len(executed_flag) == 1, "AsyncIOScheduler failed to dispatch and execute the scheduled async job."

@pytest.mark.asyncio
async def test_digest_pdf_generation_and_api(override_db_dependency):
    """
    Ingests demo dataset, runs daily pipeline and weekly retrain & digest,
    and asserts digest row creation, PDF file validity, numbers match, and GET /digests/{id} download API.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create metric
        create_resp = await client.post("/api/v1/metrics", json={
            "workspace_id": 1,
            "name": "Daily Revenue",
            "unit": "USD",
            "direction_good": "up_is_good",
            "sensitivity": "medium",
            "grain": "daily"
        })
        assert create_resp.status_code == 201
        metric_id = create_resp.json()["id"]

        # 2. Ingest demo CSV data
        with open(DEMO_CSV_PATH, "rb") as f:
            csv_bytes = f.read()

        upload_resp = await client.post(
            f"/api/v1/metrics/{metric_id}/data",
            files={"file": ("daily_revenue.csv", csv_bytes, "text/csv")}
        )
        assert upload_resp.status_code == 200
        inferred = upload_resp.json()["inferred_mapping"]
        rows = upload_resp.json()["rows"]

        confirm_resp = await client.post(
            f"/api/v1/metrics/{metric_id}/data/confirm",
            json={
                "date_col": inferred["date_col"],
                "value_col": inferred["value_col"],
                "dimension_cols": inferred["dimension_cols"],
                "rows": rows,
                "replace": True
            }
        )
        assert confirm_resp.status_code == 200

        # 3. Trigger daily pipeline and weekly retrain & digest for the target metric
        from src.db.session import get_db
        async for session in app.dependency_overrides[get_db]():
            daily_res = await run_daily_pipeline(db=session, metric_ids=[metric_id])
            assert len(daily_res) >= 1
            assert daily_res[0]["status"] == "success"

            weekly_digests = await run_weekly_retrain_and_digest(db=session, metric_ids=[metric_id])
            assert len(weekly_digests) >= 1

        target_digest = weekly_digests[0]
        digest_id = target_digest.id

        # 4. Verify Digest database record
        assert target_digest.metric_id == metric_id
        assert target_digest.workspace_id == 1
        assert target_digest.period_start is not None
        assert target_digest.period_end is not None

        # 5. Verify PDF file on disk
        pdf_path = target_digest.pdf_path
        assert os.path.exists(pdf_path), f"Digest PDF file at path '{pdf_path}' does not exist on disk."
        assert os.path.getsize(pdf_path) > 0, f"Digest PDF file at path '{pdf_path}' is empty (0 bytes)."

        with open(pdf_path, "rb") as pdf_file:
            header = pdf_file.read(4)
            assert header == b"%PDF", "Generated file is not a valid PDF document (missing %PDF header)."

        # 6. Verify GET /digests/{id} download API endpoint
        get_resp = await client.get(f"/api/v1/digests/{digest_id}")
        assert get_resp.status_code == 200
        assert get_resp.headers["content-type"] == "application/pdf"
        assert len(get_resp.content) > 0

        # 7. Verify GET /digests list API endpoint
        list_resp = await client.get(f"/api/v1/digests?metric_id={metric_id}")
        assert list_resp.status_code == 200
        digests_list = list_resp.json()
        assert len(digests_list) >= 1
        assert digests_list[0]["id"] == digest_id

        # 8. Verify GET /digests/{id} 404 handling
        missing_resp = await client.get("/api/v1/digests/999999")
        assert missing_resp.status_code == 404
