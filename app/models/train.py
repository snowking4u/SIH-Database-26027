from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Train(Base):
    __tablename__ = "train"
    __table_args__ = (
        UniqueConstraint(
            "source_system_id",
            "train_id",
            name="uq_train_source_system_train_id",
        ),
        Index("ix_train_source_system_id", "source_system_id"),
        Index("ix_train_train_id", "train_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[str] = mapped_column(String(100), nullable=False)
    train_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    train_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    schedule_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    loco_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_system_id: Mapped[int] = mapped_column(
        ForeignKey("source_system.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )

    source_system = relationship("SourceSystem", back_populates="trains")
    movements = relationship(
        "TrainMovement",
        back_populates="train",
        passive_deletes=True,
    )
    schedules = relationship(
        "TrainSchedule",
        back_populates="train",
        passive_deletes=True,
    )
    occupancies = relationship(
        "LineOccupancy",
        back_populates="train",
        passive_deletes=True,
    )
    events = relationship(
        "OperationalEvent",
        back_populates="train",
        passive_deletes=True,
    )