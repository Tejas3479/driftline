from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.db.session import get_db
from src.forecasting.schemas import AccuracyResponseSchema, ForecastResultSchema
from src.forecasting.service import (
    format_forecast_result,
    generate_multi_step_forecast,
    get_forecast_accuracy,
    read_latest_forecast,
)
from src.ingestion.service import verify_metric_access
from src.limiter import limiter

router = APIRouter(tags=["forecasting"], dependencies=[Depends(get_current_user)])

@router.get("/metrics/{id}/forecast", response_model=ForecastResultSchema)
@limiter.limit("30/minute")
async def get_metric_forecast_endpoint(
    request: Request,
    id: int,
    horizon: int = Query(30, ge=1, le=90, description="Forecast horizon in days (7, 14, or 30)"),
    backend: str = Query("lightgbm", pattern="^(lightgbm|xgboost)$", description="Model backend ('lightgbm' or 'xgboost')"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Read-only: returns the most recently generated p10/p50/p90 forecast for the metric.
    Does NOT retrain or mutate any state. Use POST /metrics/{id}/forecast to generate.
    """
    await verify_metric_access(id, session, current_user.workspace_id)
    result = await read_latest_forecast(metric_id=id, session=session, model_backend=backend)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored forecast found for metric {id} with backend '{backend}'. "
                   "Generate one via POST /metrics/{id}/forecast.",
        )
    return result

@router.post("/metrics/{id}/forecast", response_model=ForecastResultSchema)
@limiter.limit("5/minute")
async def generate_metric_forecast_endpoint(
    request: Request,
    id: int,
    horizon: int = Query(30, ge=1, le=90, description="Forecast horizon in days (7, 14, or 30)"),
    backend: str = Query("lightgbm", pattern="^(lightgbm|xgboost)$", description="Model backend ('lightgbm' or 'xgboost')"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates p10/p50/p90 quantile forecasts for metric and persists them, returning
    predictions with low_confidence status.
    """
    await verify_metric_access(id, session, current_user.workspace_id)
    try:
        res = await generate_multi_step_forecast(
            metric_id=id,
            session=session,
            horizon_days=horizon,
            model_backend=backend,
            save_to_db=True,
        )

        return format_forecast_result(id, horizon, res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate forecast: {e!s}")

@router.get("/metrics/{id}/accuracy", response_model=AccuracyResponseSchema)
@limiter.limit("30/minute")
async def get_metric_accuracy_endpoint(
    request: Request,
    id: int,
    horizon: int = Query(7, ge=1, le=90, description="Horizon to evaluate accuracy for"),
    backend: str = Query("lightgbm", pattern="^(lightgbm|xgboost)$", description="Model backend ('lightgbm' or 'xgboost')"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Read-only: returns MAPE, MAE, coverage percentage, and evaluation points read
    from forecast_accuracy_log over the recent 12 weeks. Does NOT run backtests.
    """
    await verify_metric_access(id, session, current_user.workspace_id)
    try:
        acc_dict = await get_forecast_accuracy(
            metric_id=id,
            session=session,
            horizon_days=horizon,
            model_backend=backend,
            auto_run=False,
        )
        return AccuracyResponseSchema(**acc_dict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve forecast accuracy: {e!s}")

@router.post("/metrics/{id}/accuracy", response_model=AccuracyResponseSchema)
@limiter.limit("5/minute")
async def generate_metric_accuracy_endpoint(
    request: Request,
    id: int,
    horizon: int = Query(7, ge=1, le=90, description="Horizon to evaluate accuracy for"),
    backend: str = Query("lightgbm", pattern="^(lightgbm|xgboost)$", description="Model backend ('lightgbm' or 'xgboost')"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Runs the walk-forward backtest for the metric and refreshes forecast_accuracy_log,
    then returns MAPE, MAE, coverage percentage, and evaluation points.
    """
    await verify_metric_access(id, session, current_user.workspace_id)
    try:
        acc_dict = await get_forecast_accuracy(
            metric_id=id,
            session=session,
            horizon_days=horizon,
            model_backend=backend,
            auto_run=True,
        )
        return AccuracyResponseSchema(**acc_dict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate forecast accuracy: {e!s}")
