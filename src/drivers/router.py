from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.db.session import get_db
from src.drivers import service
from src.drivers.schemas import AnomalyDriversResponseSchema
from src.ingestion.service import verify_metric_access
from src.limiter import limiter

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/anomalies/{id}/drivers", response_model=AnomalyDriversResponseSchema)
@limiter.limit("10/minute")
async def get_anomaly_drivers_endpoint(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.calculate_anomaly_drivers(db, id, current_user.workspace_id)

@router.get("/metrics/{id}/segment-comparison")
@limiter.limit("10/minute")
async def get_segment_comparison_endpoint(
    request: Request,
    id: int,
    dimension: str | None = Query(None, description="Dimension name to compare segments for"),
    range: str | None = Query("all", pattern="^(7d|30d|90d|1y|all)$", description="Date range filter anchored to max date"),
    start_date: date | None = Query(None, description="Explicit start date filter"),
    end_date: date | None = Query(None, description="Explicit end date filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    await verify_metric_access(id, db, current_user.workspace_id)
    try:
        return await service.generate_segment_comparison_spec(
            db=db,
            metric_id=id,
            dimension=dimension,
            range_token=range,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate segment comparison: {e!s}")

