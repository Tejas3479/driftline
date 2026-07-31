from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, verify_metric_access
from src.auth.models import User
from src.db.session import get_db
from src.forecasting.schemas import ForecastPointSchema, ForecastResultSchema, AccuracyResponseSchema
from src.forecasting.service import generate_multi_step_forecast, get_forecast_accuracy
from src.limiter import limiter

router = APIRouter(tags=["forecasting"], dependencies=[Depends(get_current_user)])

@router.get("/metrics/{id}/forecast", response_model=ForecastResultSchema)
@limiter.limit("5/minute")
async def get_metric_forecast_endpoint(
    request: Request,
    id: int,
    horizon: int = Query(30, ge=1, le=90, description="Forecast horizon in days (7, 14, or 30)"),
    backend: str = Query("lightgbm", pattern="^(lightgbm|xgboost)$", description="Model backend ('lightgbm' or 'xgboost')"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates p10/p50/p90 quantile forecasts for metric and returns predictions with low_confidence status.
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
        
        forecast_points = []
        for target_date, fc_dict in res["total_forecasts"].items():
            h_day = (target_date - res["as_of_date"]).days
            forecast_points.append(
                ForecastPointSchema(
                    metric_id=id,
                    forecast_date=target_date,
                    horizon_days=h_day,
                    p10=fc_dict["p10"],
                    p50=fc_dict["p50"],
                    p90=fc_dict["p90"],
                    dimension_values={},
                    model_version=res["model_version"],
                )
            )
            
        return ForecastResultSchema(
            metric_id=id,
            horizon_days=horizon,
            as_of_date=res["as_of_date"],
            model_version=res["model_version"],
            low_confidence=res["low_confidence"],
            forecasts=forecast_points,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate forecast: {str(e)}")

@router.get("/metrics/{id}/accuracy", response_model=AccuracyResponseSchema)
@limiter.limit("15/minute")
async def get_metric_accuracy_endpoint(
    request: Request,
    id: int,
    horizon: int = Query(7, ge=1, le=90, description="Horizon to evaluate accuracy for"),
    backend: str = Query("lightgbm", pattern="^(lightgbm|xgboost)$", description="Model backend ('lightgbm' or 'xgboost')"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns MAPE, MAE, coverage percentage, and evaluation points from forecast_accuracy_log over recent 12 weeks.
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve forecast accuracy: {str(e)}")
