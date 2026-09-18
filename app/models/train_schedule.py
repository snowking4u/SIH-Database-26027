from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TrainSchedule(Base):
    __tablename__ = "train_schedule"
    __table_args__ = (
        Index("ix_train_schedule_train_id", "train_id"),
        Index("ix_train_schedule_station_code", "station_code"),
        Index("ix_train_schedule_sequence_number", "sequence_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(
        ForeignKey("train.id", ondelete="RESTRICT"),
        nullable=False,
    )
    station_code: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_departure: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_run_through: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    line_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_schedule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    train = relationship("Train", back_populates="schedules")