from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.ingestion.schemas import (
    MetricCreateSchema,
    MetricResponseSchema,
    InspectionResponseSchema,
    DataConfirmSchema,
    DataConfirmResponseSchema,
)
import src.ingestion.service as service

router = APIRouter()

@router.get("/metrics", response_model=List[MetricResponseSchema])
async def list_metrics_endpoint(
    db: AsyncSession = Depends(get_db)
):
    return await service.list_metrics(db)

@router.post("/metrics", response_model=MetricResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_metric_endpoint(
    schema: MetricCreateSchema,
    db: AsyncSession = Depends(get_db)
):
    return await service.create_metric(db, schema)

@router.post("/metrics/{id}/data", response_model=InspectionResponseSchema)
async def upload_and_inspect_data_endpoint(
    id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    metric = await service.get_metric(db, id)
    if not metric:
        raise HTTPException(status_code=404, detail=f"Metric with id {id} not found.")
    
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
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await service.confirm_and_persist_observations(db, id, schema)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
