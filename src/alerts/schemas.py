from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ChannelEnum(str, Enum):
    in_app = "in_app"
    email = "email"

class AlertRuleCreateSchema(BaseModel):
    metric_id: int
    min_severity: float = Field(..., ge=0.0, le=100.0, description="Minimum severity score threshold (0.0 to 100.0)")
    channels: List[ChannelEnum] = Field(default_factory=lambda: [ChannelEnum.in_app, ChannelEnum.email])

class AlertRuleResponseSchema(BaseModel):
    id: int
    metric_id: int
    min_severity: float
    channels: List[str]

    class Config:
        from_attributes = True

class NotificationResponseSchema(BaseModel):
    id: int
    workspace_id: int
    metric_id: int
    anomaly_id: int
    title: str
    message: str
    severity_score: float
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
