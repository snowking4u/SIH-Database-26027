from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AvailableWindow(Base):
    __tablename__ = "available_window"
    __table_args__ = (
        Index("ix_available_window_station_code", "station_code"),
        Index("ix_available_window_line_number", "line_number"),
        Index("ix_available_window_window_start", "window_start"),
        Index("ix_available_window_window_end", "window_end"),
        Index("ix_available_window_window_status", "window_status"),
        Index(
            "ix_available_window_sc_line_start_end",
            "station_code",
            "line_number",
            "window_start",
            "window_end",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_code: Mapped[str] = mapped_column(String(50), nullable=False)
    line_number: Mapped[str] = mapped_column(String(50), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    window_status: Mapped[str] = mapped_column(String(50), nullable=False)
    calculation_source: Mapped[str] = mapped_column(String(200), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("train_schedule.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_occupancy_id: Mapped[int | None] = mapped_column(
        ForeignKey("line_occupancy.id", ondelete="RESTRICT"),
        nullable=True,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_schedule = relationship("TrainSchedule")
    source_occupancy = relationship("LineOccupancy")
    candidate_windows = relationship(
        "CandidateBlockWindow",
        back_populates="available_window",
        passive_deletes=True,
    )