from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

class DigestResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    metric_id: Optional[int] = None
    period_start: date
    period_end: date
    pdf_path: str
    generated_at: datetime

    @field_validator("pdf_path")
    @classmethod
    def sanitize_pdf_path(cls, v: str) -> str:
        import os
        return os.path.basename(v) if v else v

class DigestGenerateRequestSchema(BaseModel):
    metric_id: int
    workspace_id: Optional[int] = 1
