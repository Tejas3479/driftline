from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.anomalies.schemas import TimeseriesResponseSchema
import src.anomalies.service as service

router = APIRouter()

@router.get("/metrics/{id}/timeseries", response_model=TimeseriesResponseSchema)
async def get_metric_timeseries_endpoint(
    id: int,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    points = await service.get_metric_timeseries(db, id, start, end)
    return {
        "metric_id": id,
        "points": points
    }

@router.post("/metrics/{id}/rollup", status_code=status.HTTP_200_OK)
async def trigger_metric_rollup_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        await service.run_daily_rollup_and_decomposition(db, id)
        return {"status": "success", "detail": f"Rollup and decomposition completed for metric {id}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
