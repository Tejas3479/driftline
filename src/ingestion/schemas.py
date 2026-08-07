from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.ingestion.models import DirectionGoodEnum, GrainEnum, SensitivityEnum


class MetricCreateSchema(BaseModel):
    name: str
    unit: str | None = None
    direction_good: DirectionGoodEnum = DirectionGoodEnum.up_is_good
    sensitivity: SensitivityEnum = SensitivityEnum.medium
    grain: GrainEnum = GrainEnum.daily

class MetricUpdateSchema(BaseModel):
    sensitivity: SensitivityEnum | None = None
    direction_good: DirectionGoodEnum | None = None
    z_score_weight: float | None = Field(None, ge=0.0, le=1.0)

from src.drivers.schemas import StructuralImportanceSchema


class MetricResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    unit: str | None
    direction_good: DirectionGoodEnum
    sensitivity: SensitivityEnum
    grain: GrainEnum
    z_score_weight: float
    structural_importance: list[StructuralImportanceSchema]
    created_at: datetime

class ColumnMappingSchema(BaseModel):
    date_col: str
    value_col: str
    dimension_cols: list[str] = Field(default_factory=list)

class ValidationErrorSchema(BaseModel):
    row_number: int
    column: str
    issue: str
    invalid_value: str | None = None

class ValidationReportSchema(BaseModel):
    is_valid: bool
    total_rows: int
    errors: list[ValidationErrorSchema] = Field(default_factory=list)
    date_gaps: list[str] = Field(default_factory=list)
    inferred_mapping: ColumnMappingSchema

class InspectionResponseSchema(BaseModel):
    metric_id: int
    inferred_mapping: ColumnMappingSchema
    validation_report: ValidationReportSchema
    rows: list[dict[str, Any]]

class DataConfirmSchema(BaseModel):
    date_col: str
    value_col: str
    dimension_cols: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]]
    replace: bool = False

class DataConfirmResponseSchema(BaseModel):
    metric_id: int
    inserted_count: int
    updated_count: int
    total_observations: int
