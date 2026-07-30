from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.auth.models import User
from src.auth.dependencies import get_current_user, verify_metric_access
from src.ingestion.schemas import (
    MetricCreateSchema,
    MetricResponseSchema,
    InspectionResponseSchema,
    DataConfirmSchema,
    DataConfirmResponseSchema,
)
import src.ingestion.service as service

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/metrics", response_model=List[MetricResponseSchema])
async def list_metrics_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.list_metrics(db, current_user.workspace_id)

@router.post("/metrics", response_model=MetricResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_metric_endpoint(
    schema: MetricCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce metric belongs to current user's workspace
    return await service.create_metric(db, schema, current_user.workspace_id)

@router.post("/metrics/{id}/data", response_model=InspectionResponseSchema)
async def upload_and_inspect_data_endpoint(
    id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metric = await verify_metric_access(id, db, current_user.workspace_id)
    
    file_bytes = await file.read()
    result = service.inspect_and_validate_csv(metric, file_bytes)
    return {
        "metric_id": id,
        "inferred_mapping": result["inferred_mapping"],
        "validation_report": result["validation_report"],
        "rows": result["rows"]
    }

@router.post("/metrics/{id}/data/confirm", response_model=DataConfirmResponseSchema)
async def confirm_data_endpoint(
    id: int,
    schema: DataConfirmSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_metric_access(id, db, current_user.workspace_id)
    try:
        result = await service.confirm_and_persist_observations(db, id, schema)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
