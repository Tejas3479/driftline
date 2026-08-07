import enum
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    direction_good: Mapped[DirectionGoodEnum] = mapped_column(SQLEnum(DirectionGoodEnum, name="direction_good_enum", create_type=False), nullable=False)
    sensitivity: Mapped[SensitivityEnum] = mapped_column(SQLEnum(SensitivityEnum, name="sensitivity_enum", create_type=False), nullable=False)
    grain: Mapped[GrainEnum] = mapped_column(SQLEnum(GrainEnum, name="grain_enum", create_type=False), nullable=False)
    z_score_weight: Mapped[float] = mapped_column(Float, default=0.5, server_default="0.5", nullable=False)
    structural_importance: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="metrics", lazy="raise")
    dimension_defs: Mapped[list["DimensionDef"]] = relationship(
        "DimensionDef", back_populates="metric", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    observations: Mapped[list["Observation"]] = relationship(
        "Observation", back_populates="metric", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    daily_rollups: Mapped[list["DailyRollup"]] = relationship(
        "DailyRollup", back_populates="metric", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(
        "Anomaly", back_populates="metric", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    forecasts: Mapped[list["Forecast"]] = relationship(
        "Forecast", back_populates="metric", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    forecast_accuracy_logs: Mapped[list["ForecastAccuracyLog"]] = relationship(
        "ForecastAccuracyLog", back_populates="metric", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    alert_rule: Mapped[Optional["AlertRule"]] = relationship(
        "AlertRule", back_populates="metric", uselist=False, lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    digests: Mapped[list["Digest"]] = relationship(
        "Digest", back_populates="metric", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
class DimensionDef(Base):
    __tablename__ = "dimension_defs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    metric: Mapped["Metric"] = relationship("Metric", back_populates="dimension_defs", lazy="raise")

class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    dimension_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    metric: Mapped["Metric"] = relationship("Metric", back_populates="observations", lazy="raise")

    __table_args__ = (
        Index("ix_observations_metric_date", "metric_id", "date"),
    )
