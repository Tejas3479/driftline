from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from src.anomalies.models import AnomalyStatusEnum, AnomalyTypeEnum


class TimeseriesPointSchema(BaseModel):
    date: date
    value_total: float
    trend: float | None = None
    seasonal: float | None = None
    residual: float | None = None
    dimension_values: dict[str, str]

class TimeseriesResponseSchema(BaseModel):
    metric_id: int
    mad: float | None = None
    points: list[TimeseriesPointSchema]

class AnomalyResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_id: int
    date: date
    severity_score: float
    type: AnomalyTypeEnum
    z_score: float
    isolation_score: float
    status: AnomalyStatusEnum
    explanation_text: str | None
    created_at: datetime

class AnomalyDetailResponseSchema(AnomalyResponseSchema):
    pass

class AnomalyFeedbackSchema(BaseModel):
    status: AnomalyStatusEnum

class GlobalAnomalyResponseSchema(BaseModel):
    id: int
    metric_id: int
    metric_name: str
    date: date
    severity_score: float
    anomaly_type: str
    status: str
    explanation_excerpt: str | None = None

