from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from src.ingestion.models import DirectionGoodEnum, SensitivityEnum, GrainEnum

class MetricCreateSchema(BaseModel):
    name: str
    unit: Optional[str] = None
    direction_good: DirectionGoodEnum = DirectionGoodEnum.up_is_good
    sensitivity: SensitivityEnum = SensitivityEnum.medium
    grain: GrainEnum = GrainEnum.daily

class MetricUpdateSchema(BaseModel):
    sensitivity: Optional[SensitivityEnum] = None
    direction_good: Optional[DirectionGoodEnum] = None
    z_score_weight: Optional[float] = Field(None, ge=0.0, le=1.0)

from src.drivers.schemas import StructuralImportanceSchema

class MetricResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    unit: Optional[str]
    direction_good: DirectionGoodEnum
    sensitivity: SensitivityEnum
    grain: GrainEnum
    z_score_weight: float
    structural_importance: List[StructuralImportanceSchema]
    created_at: datetime

class ColumnMappingSchema(BaseModel):
    date_col: str
    value_col: str
    dimension_cols: List[str] = Field(default_factory=list)

class ValidationErrorSchema(BaseModel):
    row_number: int
    column: str
    issue: str
    invalid_value: Optional[str] = None

class ValidationReportSchema(BaseModel):
    is_valid: bool
    total_rows: int
    errors: List[ValidationErrorSchema] = Field(default_factory=list)
    date_gaps: List[str] = Field(default_factory=list)
    inferred_mapping: ColumnMappingSchema

class InspectionResponseSchema(BaseModel):
    metric_id: int
    inferred_mapping: ColumnMappingSchema
    validation_report: ValidationReportSchema
    rows: List[Dict[str, Any]]

class DataConfirmSchema(BaseModel):
    date_col: str
    value_col: str
    dimension_cols: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]]
    replace: bool = False

class DataConfirmResponseSchema(BaseModel):
    metric_id: int
    inserted_count: int
    updated_count: int
    total_observations: int
