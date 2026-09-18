from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LineOccupancy(Base):
    __tablename__ = "line_occupancy"
    __table_args__ = (
        Index("ix_line_occupancy_station_code", "station_code"),
        Index("ix_line_occupancy_line_number", "line_number"),
        Index("ix_line_occupancy_occupancy_start", "occupancy_start"),
        Index("ix_line_occupancy_train_id", "train_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_code: Mapped[str] = mapped_column(String(50), nullable=False)
    line_number: Mapped[str] = mapped_column(String(50), nullable=False)
    occupancy_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    occupancy_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    occupancy_status: Mapped[str] = mapped_column(String(50), nullable=False)
    train_id: Mapped[int | None] = mapped_column(
        ForeignKey("train.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    train = relationship("Train", back_populates="occupancies")