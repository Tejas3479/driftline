from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from src.anomalies.models import AnomalyTypeEnum, AnomalyStatusEnum

class TimeseriesPointSchema(BaseModel):
    date: date
    value_total: float
    trend: Optional[float] = None
    seasonal: Optional[float] = None
    residual: Optional[float] = None
    dimension_values: Dict[str, str]

class TimeseriesResponseSchema(BaseModel):
    metric_id: int
    mad: Optional[float] = None
    points: List[TimeseriesPointSchema]

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
    explanation_text: Optional[str]
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
    explanation_excerpt: Optional[str] = None

