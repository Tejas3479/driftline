from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.drivers.schemas import AnomalyDriversResponseSchema
import src.drivers.service as service

router = APIRouter()

@router.get("/anomalies/{id}/drivers", response_model=AnomalyDriversResponseSchema)
async def get_anomaly_drivers_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await service.calculate_anomaly_drivers(db, id)
