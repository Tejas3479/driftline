from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class SegmentContributionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: str
    segment_value: str
    actual_value: float
    expected_value: float
    delta: float
    contribution_pct: float

class StructuralImportanceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature: str
    importance: float

class AnomalyDriversResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anomaly_id: int
    metric_id: int
    explanation_text: str
    ranked_segments: List[SegmentContributionSchema]
    structural_importance: List[StructuralImportanceSchema]
