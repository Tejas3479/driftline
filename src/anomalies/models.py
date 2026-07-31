import enum
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, Float, Text, DateTime, ForeignKey, Index, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from src.db.base import Base

class AnomalyTypeEnum(str, enum.Enum):
    spike = "spike"
    dip = "dip"
    level_shift = "level_shift"
    volatility = "volatility"

class AnomalyStatusEnum(str, enum.Enum):
    new = "new"
    reviewed = "reviewed"
    resolved = "resolved"
    false_positive = "false_positive"

class DailyRollup(Base):
    __tablename__ = "daily_rollups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value_total: Mapped[float] = mapped_column(Float, nullable=False)
    trend: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    seasonal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    residual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dimension_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default='{}')

    # Relationships
    metric: Mapped["Metric"] = relationship("Metric", back_populates="daily_rollups", lazy="raise")

    __table_args__ = (
        Index("ix_daily_rollups_metric_date", "metric_id", "date"),
        Index("uq_daily_rollups_metric_date_dims", "metric_id", "date", "dimension_values", unique=True),
    )

class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[AnomalyTypeEnum] = mapped_column(SQLEnum(AnomalyTypeEnum, name="anomaly_type_enum", create_type=False), nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    isolation_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[AnomalyStatusEnum] = mapped_column(
        SQLEnum(AnomalyStatusEnum, name="anomaly_status_enum", create_type=False),
        default=AnomalyStatusEnum.new,
        server_default=AnomalyStatusEnum.new.value,
        nullable=False
    )
    explanation_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    metric: Mapped["Metric"] = relationship("Metric", back_populates="anomalies", lazy="raise")
    drivers: Mapped[list["AnomalyDriver"]] = relationship(
        "AnomalyDriver", back_populates="anomaly", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    notification: Mapped[Optional["Notification"]] = relationship(
        "Notification", back_populates="anomaly", uselist=False, lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_anomalies_metric_date", "metric_id", "date"),
        Index("uq_anomalies_metric_date", "metric_id", "date", unique=True),
    )
