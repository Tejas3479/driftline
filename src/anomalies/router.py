from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.auth.dependencies import get_current_user, verify_metric_access
from src.auth.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.anomalies.models import AnomalyTypeEnum, AnomalyStatusEnum
from src.anomalies.schemas import TimeseriesResponseSchema, AnomalyResponseSchema, AnomalyDetailResponseSchema, AnomalyFeedbackSchema, GlobalAnomalyResponseSchema
import src.anomalies.service as service

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/anomalies", response_model=List[GlobalAnomalyResponseSchema])
async def list_global_anomalies_endpoint(
    status: Optional[str] = Query(None, description="Status filter e.g. new, reviewed, resolved, false_positive"),
    metric_id: Optional[int] = Query(None, description="Metric ID filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.list_global_anomalies(db, status_filter=status, metric_id=metric_id, workspace_id=current_user.workspace_id)


@router.get("/metrics/{id}/timeseries", response_model=TimeseriesResponseSchema)
async def get_metric_timeseries_endpoint(
    id: int,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    segment: Optional[str] = Query(None, description="Segment filter formatted as dimension:value"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_metric_access(id, db, current_user.workspace_id)
    if segment is not None:
        if ":" not in segment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid segment query parameter format. Expected 'dimension:value'"
            )
        dim_key, dim_val = segment.split(":", 1)
        if not dim_key.strip() or not dim_val.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid segment query parameter. Dimension and value cannot be empty"
            )

    points, mad = await service.get_metric_timeseries(db, id, start, end, segment)
    return {
        "metric_id": id,
        "mad": mad,
        "points": points
    }

@router.post("/metrics/{id}/rollup", status_code=status.HTTP_200_OK)
async def trigger_metric_rollup_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_metric_access(id, db, current_user.workspace_id)
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_metric_access(id, db, current_user.workspace_id)
    return await service.get_anomalies(db, id, status, severity_min, type)

@router.get("/anomalies/{id}", response_model=AnomalyDetailResponseSchema)
async def get_anomaly_detail_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    anomaly = await service.get_anomaly_detail(db, id, current_user.workspace_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail=f"Anomaly with id {id} not found.")
    return anomaly

@router.post("/anomalies/{id}/feedback", response_model=AnomalyDetailResponseSchema)
async def record_anomaly_feedback_endpoint(
    id: int,
    schema: AnomalyFeedbackSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return await service.record_anomaly_feedback(db, id, schema.status, current_user.workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
