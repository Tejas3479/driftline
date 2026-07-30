from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class DigestResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    metric_id: Optional[int] = None
    period_start: date
    period_end: date
    pdf_path: str
    generated_at: datetime

class DigestGenerateRequestSchema(BaseModel):
    metric_id: int
    workspace_id: Optional[int] = 1
