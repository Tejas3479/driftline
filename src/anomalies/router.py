from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.anomalies.models import AnomalyTypeEnum, AnomalyStatusEnum
from src.anomalies.schemas import TimeseriesResponseSchema, AnomalyResponseSchema, AnomalyDetailResponseSchema
import src.anomalies.service as service

router = APIRouter()

@router.get("/metrics/{id}/timeseries", response_model=TimeseriesResponseSchema)
async def get_metric_timeseries_endpoint(
    id: int,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    points, mad = await service.get_metric_timeseries(db, id, start, end)
    return {
        "metric_id": id,
        "mad": mad,
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

@router.get("/metrics/{id}/anomalies", response_model=List[AnomalyResponseSchema])
async def list_anomalies_endpoint(
    id: int,
    status: Optional[AnomalyStatusEnum] = Query(None),
    severity_min: Optional[float] = Query(None),
    type: Optional[AnomalyTypeEnum] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    metric = await service.get_metric(db, id)
    if not metric:
        raise HTTPException(status_code=404, detail=f"Metric with id {id} not found.")
    return await service.get_anomalies(db, id, status, severity_min, type)

@router.get("/anomalies/{id}", response_model=AnomalyDetailResponseSchema)
async def get_anomaly_detail_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    anomaly = await service.get_anomaly_detail(db, id)
    if not anomaly:
        raise HTTPException(status_code=404, detail=f"Anomaly with id {id} not found.")
    return anomaly
