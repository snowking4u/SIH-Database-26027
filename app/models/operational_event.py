from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OperationalEvent(Base):
    __tablename__ = "operational_event"
    __table_args__ = (
        Index("ix_operational_event_train_id", "train_id"),
        Index("ix_operational_event_station_code", "station_code"),
        Index("ix_operational_event_event_datetime", "event_datetime"),
        Index("ix_operational_event_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int | None] = mapped_column(
        ForeignKey("train.id", ondelete="RESTRICT"),
        nullable=True,
    )
    station_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    train = relationship("Train", back_populates="events")