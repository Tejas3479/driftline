from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    dimension_values: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}", default=dict)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    model_backend: Mapped[str] = mapped_column(String(50), nullable=False, server_default="lightgbm", default="lightgbm")
    p10: Mapped[float] = mapped_column(Float, nullable=False)
    p50: Mapped[float] = mapped_column(Float, nullable=False)
    p90: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    metric: Mapped["Metric"] = relationship("Metric", back_populates="forecasts", lazy="raise")

    __table_args__ = (
        Index("ix_forecasts_metric_date", "metric_id", "forecast_date"),
        UniqueConstraint("metric_id", "dimension_values", "forecast_date", "horizon_days", "model_backend", name="uq_forecasts_metric_dim_date_horizon_backend"),
    )

class ForecastAccuracyLog(Base):
    __tablename__ = "forecast_accuracy_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7", default=7)
    model_backend: Mapped[str] = mapped_column(String(50), nullable=False, server_default="lightgbm", default="lightgbm")
    predicted_p10: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_p50: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_p90: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual: Mapped[float] = mapped_column(Float, nullable=False)
    abs_error: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0", default=0.0)
    abs_pct_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_bounds: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    used_ml_model: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    metric: Mapped["Metric"] = relationship("Metric", back_populates="forecast_accuracy_logs", lazy="raise")

    __table_args__ = (
        Index("ix_forecast_accuracy_metric_date", "metric_id", "date"),
        UniqueConstraint("metric_id", "date", "horizon_days", "model_backend", name="uq_forecast_accuracy_log_metric_date_horizon_backend"),
    )
