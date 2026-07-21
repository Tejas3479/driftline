from sqlalchemy import String, Float, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base

class AnomalyDriver(Base):
    __tablename__ = "anomaly_drivers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int] = mapped_column(ForeignKey("anomalies.id", ondelete="CASCADE"), nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension_value: Mapped[str] = mapped_column(String(255), nullable=False)
    contribution_value: Mapped[float] = mapped_column(Float, nullable=False)
    contribution_pct: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
