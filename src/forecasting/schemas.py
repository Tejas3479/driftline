from datetime import date

from pydantic import BaseModel, Field, model_validator


class ForecastPointSchema(BaseModel):
    metric_id: int
    forecast_date: date
    horizon_days: int
    p10: float
    p50: float
    p90: float
    dimension_values: dict[str, str] = Field(default_factory=dict)
    model_version: str

    @model_validator(mode='after')
    def check_non_crossing(self):
        if not (self.p10 <= self.p50 <= self.p90):
            raise ValueError(f"Quantiles must not cross: p10={self.p10}, p50={self.p50}, p90={self.p90}")
        return self

class ForecastResultSchema(BaseModel):
    metric_id: int
    horizon_days: int
    as_of_date: date
    model_version: str
    low_confidence: bool = False
    forecasts: list[ForecastPointSchema]

class ForecastGenerateRequestSchema(BaseModel):
    metric_id: int
    horizon_days: int = Field(default=30, ge=1, le=90)
    model_backend: str = Field(default="lightgbm", pattern="^(lightgbm|xgboost)$")
    save_to_db: bool = True

class AccuracyPointSchema(BaseModel):
    date: date
    predicted_p50: float
    actual: float
    abs_error: float
    abs_pct_error: float | None = None
    in_bounds: bool | None = None
    predicted_p10: float | None = None
    predicted_p90: float | None = None
    used_ml_model: bool = True

class AccuracyResponseSchema(BaseModel):
    metric_id: int
    horizon_days: int
    model_backend: str
    mape: float | None = None
    mae: float | None = None
    coverage_pct: float | None = None
    total_evaluations: int
    ml_evaluations: int
    points: list[AccuracyPointSchema]
