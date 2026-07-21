import enum
from datetime import date, datetime
from typing import Any, Dict, Optional
from sqlalchemy import String, Date, Float, DateTime, ForeignKey, Index, Enum as SQLEnum, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base

class DirectionGoodEnum(str, enum.Enum):
    up_is_good = "up_is_good"
    down_is_good = "down_is_good"

class SensitivityEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class GrainEnum(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"

class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    direction_good: Mapped[DirectionGoodEnum] = mapped_column(SQLEnum(DirectionGoodEnum, name="direction_good_enum", create_type=False), nullable=False)
    sensitivity: Mapped[SensitivityEnum] = mapped_column(SQLEnum(SensitivityEnum, name="sensitivity_enum", create_type=False), nullable=False)
    grain: Mapped[GrainEnum] = mapped_column(SQLEnum(GrainEnum, name="grain_enum", create_type=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class DimensionDef(Base):
    __tablename__ = "dimension_defs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    dimension_values: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_observations_metric_date", "metric_id", "date"),
    )
