from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

class DigestResponseSchema(BaseModel):
    id: int
    workspace_id: int
    metric_id: Optional[int] = None
    period_start: date
    period_end: date
    pdf_path: str
    generated_at: datetime

    class Config:
        from_attributes = True

class DigestGenerateRequestSchema(BaseModel):
    metric_id: int
    workspace_id: Optional[int] = 1
