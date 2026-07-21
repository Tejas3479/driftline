from datetime import date
from typing import Dict, List, Optional
from pydantic import BaseModel

class TimeseriesPointSchema(BaseModel):
    date: date
    value_total: float
    trend: Optional[float] = None
    seasonal: Optional[float] = None
    residual: Optional[float] = None
    dimension_values: Dict[str, str]

class TimeseriesResponseSchema(BaseModel):
    metric_id: int
    points: List[TimeseriesPointSchema]
