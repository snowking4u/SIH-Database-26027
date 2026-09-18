from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TrainMovement(Base):
    __tablename__ = "train_movement"
    __table_args__ = (
        Index("ix_train_movement_train_id", "train_id"),
        Index("ix_train_movement_station_code", "station_code"),
        Index("ix_train_movement_movement_datetime", "movement_datetime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(
        ForeignKey("train.id", ondelete="RESTRICT"),
        nullable=False,
    )
    station_code: Mapped[str] = mapped_column(String(50), nullable=False)
    movement_flag: Mapped[str] = mapped_column(String(1), nullable=False)
    movement_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    line_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    train = relationship("Train", back_populates="movements")