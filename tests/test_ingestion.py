import io

import httpx
import pytest

from main import app


@pytest.mark.asyncio
async def test_clean_csv_upload_and_confirmation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create metric
        metric_res = await client.post("/api/v1/metrics", json={
            "name": "Daily Revenue Test",
            "unit": "USD",
            "direction_good": "up_is_good",
            "sensitivity": "medium",
            "grain": "daily"
        })
        assert metric_res.status_code == 201
        metric_id = metric_res.json()["id"]

        # 2. Upload demo CSV
        with open("demo_data/daily_revenue.csv", "rb") as f:
            upload_res = await client.post(f"/api/v1/metrics/{metric_id}/data", files={"file": ("daily_revenue.csv", f, "text/csv")})
        assert upload_res.status_code == 200
        inspect_data = upload_res.json()

        assert inspect_data["validation_report"]["is_valid"] is True
        assert inspect_data["validation_report"]["total_rows"] == 180
        assert inspect_data["inferred_mapping"]["date_col"] == "date"
        assert inspect_data["inferred_mapping"]["value_col"] == "revenue"
        assert "channel" in inspect_data["inferred_mapping"]["dimension_cols"]

        # 3. Confirm ingestion
        confirm_res = await client.post(f"/api/v1/metrics/{metric_id}/data/confirm", json={
            "date_col": inspect_data["inferred_mapping"]["date_col"],
            "value_col": inspect_data["inferred_mapping"]["value_col"],
            "dimension_cols": inspect_data["inferred_mapping"]["dimension_cols"],
            "rows": inspect_data["rows"],
            "replace": True
        })
        assert confirm_res.status_code == 200
        confirm_data = confirm_res.json()
        assert confirm_data["inserted_count"] == 180
        assert confirm_data["total_observations"] == 180

@pytest.mark.asyncio
async def test_csv_validation_report_catches_errors_and_gaps():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/api/v1/metrics", json={"name": "Validation Test Metric"})
        assert metric_res.status_code == 201
        metric_id = metric_res.json()["id"]

        csv_content = """date,channel,revenue
2026-01-01,organic,5000
INVALID_DATE,organic,5100
2026-01-01,organic,5200
2026-01-04,organic,5300
"""
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        upload_res = await client.post(f"/api/v1/metrics/{metric_id}/data", files={"file": ("test_err.csv", file_obj, "text/csv")})
        assert upload_res.status_code == 200
        report = upload_res.json()["validation_report"]

        assert report["is_valid"] is False
        issues = [e["issue"] for e in report["errors"]]
        assert any("unparseable date" in issue.lower() for issue in issues)
        assert any("duplicate" in issue.lower() for issue in issues)
        assert len(report["date_gaps"]) > 0

@pytest.mark.asyncio
async def test_append_vs_replace_semantics():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metric_res = await client.post("/api/v1/metrics", json={"name": "Append Test Metric"})
        assert metric_res.status_code == 201
        metric_id = metric_res.json()["id"]

        initial_csv = """date,channel,revenue
2026-01-01,organic,1000
2026-01-02,organic,1100
"""
        upload_res1 = await client.post(f"/api/v1/metrics/{metric_id}/data", files={"file": ("init.csv", io.BytesIO(initial_csv.encode("utf-8")), "text/csv")})
        data1 = upload_res1.json()

        confirm_res1 = await client.post(f"/api/v1/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": data1["rows"],
            "replace": False
        })
        assert confirm_res1.json()["total_observations"] == 2

        additional_csv = """date,channel,revenue
2026-01-03,organic,1200
2026-01-04,organic,1300
"""
        upload_res2 = await client.post(f"/api/v1/metrics/{metric_id}/data", files={"file": ("add.csv", io.BytesIO(additional_csv.encode("utf-8")), "text/csv")})
        data2 = upload_res2.json()

        confirm_res2 = await client.post(f"/api/v1/metrics/{metric_id}/data/confirm", json={
            "date_col": "date",
            "value_col": "revenue",
            "dimension_cols": ["channel"],
            "rows": data2["rows"],
            "replace": False
        })
        confirm_data2 = confirm_res2.json()
        assert confirm_data2["inserted_count"] == 2
        assert confirm_data2["total_observations"] == 4
