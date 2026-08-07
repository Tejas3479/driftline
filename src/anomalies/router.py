from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.anomalies import service
from src.anomalies.models import AnomalyStatusEnum, AnomalyTypeEnum
from src.anomalies.schemas import (
    AnomalyDetailResponseSchema,
    AnomalyFeedbackSchema,
    AnomalyResponseSchema,
    GlobalAnomalyResponseSchema,
    TimeseriesResponseSchema,
)
from src.audit import audit_log
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.db.session import get_db
from src.ingestion.service import verify_metric_access
from src.limiter import limiter

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/anomalies", response_model=list[GlobalAnomalyResponseSchema])
@limiter.limit("60/minute")
async def list_global_anomalies_endpoint(
    request: Request,
    status: str | None = Query(None, description="Status filter e.g. new, reviewed, resolved, false_positive"),
    metric_id: int | None = Query(None, description="Metric ID filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.list_global_anomalies(db, status_filter=status, metric_id=metric_id, workspace_id=current_user.workspace_id)


@router.get("/metrics/{id}/timeseries", response_model=TimeseriesResponseSchema)
@limiter.limit("60/minute")
async def get_metric_timeseries_endpoint(
    request: Request,
    id: int,
    start: date | None = Query(None),
    end: date | None = Query(None),
    segment: str | None = Query(None, description="Segment filter formatted as dimension:value"),
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

@router.get("/metrics/{id}/anomalies", response_model=list[AnomalyResponseSchema])
@limiter.limit("60/minute")
async def list_anomalies_endpoint(
    request: Request,
    id: int,
    status: AnomalyStatusEnum | None = Query(None),
    severity_min: float | None = Query(None),
    type: AnomalyTypeEnum | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_metric_access(id, db, current_user.workspace_id)
    return await service.get_anomalies(db, id, status, severity_min, type)

@router.get("/anomalies/{id}", response_model=AnomalyDetailResponseSchema)
@limiter.limit("60/minute")
async def get_anomaly_detail_endpoint(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    detail = await service.get_anomaly_detail(db, id, current_user.workspace_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Anomaly with id {id} not found.")
    return detail["anomaly"]

@router.post("/anomalies/{id}/feedback", response_model=AnomalyDetailResponseSchema)
async def record_anomaly_feedback_endpoint(
    id: int,
    schema: AnomalyFeedbackSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await service.record_anomaly_feedback(db, id, schema.status, current_user.workspace_id)
        audit_log("anomaly.feedback", user_id=current_user.id, workspace_id=current_user.workspace_id,
                 resource_type="anomaly", resource_id=id, details={"new_status": schema.status})
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
