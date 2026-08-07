import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit import audit_log
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.db.session import get_db
from src.ingestion import service
from src.ingestion.schemas import (
    DataConfirmResponseSchema,
    DataConfirmSchema,
    InspectionResponseSchema,
    MetricCreateSchema,
    MetricResponseSchema,
    MetricUpdateSchema,
)
from src.ingestion.service import verify_metric_access
from src.limiter import limiter

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/metrics", response_model=list[MetricResponseSchema])
@limiter.limit("60/minute")
async def list_metrics_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.list_metrics(db, current_user.workspace_id)

@router.post("/metrics", response_model=MetricResponseSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_metric_endpoint(
    request: Request,
    schema: MetricCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce metric belongs to current user's workspace
    metric = await service.create_metric(db, schema, current_user.workspace_id)
    audit_log("metric.created", user_id=current_user.id, workspace_id=current_user.workspace_id,
             resource_type="metric", resource_id=metric.id, details={"name": schema.name})
    return metric

@router.patch("/metrics/{id}", response_model=MetricResponseSchema)
@limiter.limit("20/minute")
async def update_metric_endpoint(
    request: Request,
    id: int,
    schema: MetricUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metric = await verify_metric_access(id, db, current_user.workspace_id)
    result = await service.update_metric(db, metric, schema)
    audit_log("metric.updated", user_id=current_user.id, workspace_id=current_user.workspace_id,
             resource_type="metric", resource_id=id, details=schema.model_dump(exclude_unset=True))
    return result

@router.delete("/metrics/{id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_metric_endpoint(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metric = await verify_metric_access(id, db, current_user.workspace_id)
    await service.delete_metric(db, metric)
    audit_log("metric.deleted", user_id=current_user.id, workspace_id=current_user.workspace_id,
             resource_type="metric", resource_id=id)

@router.post("/metrics/{id}/data", response_model=InspectionResponseSchema)
@limiter.limit("20/minute")
async def upload_and_inspect_data_endpoint(
    request: Request,
    id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metric = await verify_metric_access(id, db, current_user.workspace_id)
    
    MAX_UPLOAD_BYTES = 50 * 1024 * 1024 # 50 MB
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")
        
    file_bytes = bytearray()
    while chunk := await file.read(1024 * 1024):  # 1MB chunks
        file_bytes.extend(chunk)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")
    file_bytes = bytes(file_bytes)
    result = await asyncio.to_thread(service.inspect_and_validate_csv, metric, file_bytes)
    return {
        "metric_id": id,
        "inferred_mapping": result["inferred_mapping"],
        "validation_report": result["validation_report"],
        "rows": result["rows"]
    }

@router.post("/metrics/{id}/data/confirm", response_model=DataConfirmResponseSchema)
@limiter.limit("20/minute")
async def confirm_data_endpoint(
    request: Request,
    id: int,
    schema: DataConfirmSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_metric_access(id, db, current_user.workspace_id)
    try:
        result = await service.confirm_and_persist_observations(db, id, schema)
        audit_log("metric.data_confirmed", user_id=current_user.id, workspace_id=current_user.workspace_id,
                 resource_type="metric", resource_id=id, details={"rows_inserted": result.get("rows_inserted", 0)})
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
