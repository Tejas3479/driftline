import json
from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

class ForecastPointSchema(BaseModel):
    metric_id: int
    forecast_date: date
    horizon_days: int
    p10: float
    p50: float
    p90: float
    dimension_values: Dict[str, str] = Field(default_factory=dict)
    model_version: str

    @field_validator("p10", "p50", "p90")
    def check_non_crossing(cls, v, info):
        return v

class ForecastResultSchema(BaseModel):
    metric_id: int
    horizon_days: int
    as_of_date: date
    model_version: str
    forecasts: List[ForecastPointSchema]

class ForecastGenerateRequestSchema(BaseModel):
    metric_id: int
    horizon_days: int = Field(default=30, ge=1, le=90)
    model_backend: str = Field(default="lightgbm", pattern="^(lightgbm|xgboost)$")
    save_to_db: bool = True
