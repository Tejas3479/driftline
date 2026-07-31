from datetime import datetime
from typing import List
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    metrics: Mapped[List["Metric"]] = relationship(
        "Metric", back_populates="workspace", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="workspace", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    digests: Mapped[List["Digest"]] = relationship(
        "Digest", back_populates="workspace", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="workspace", lazy="raise",
        cascade="all, delete-orphan", passive_deletes=True
    )
