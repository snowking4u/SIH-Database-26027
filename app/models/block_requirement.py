from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BlockRequirement(Base):
    """Operational block requirement of a maintenance task.

    This is NOT a final block plan and NOT an approved railway block. It
    describes what operational access a maintenance task requires.
    """

    __tablename__ = "block_requirement"
    __table_args__ = (
        Index("ix_block_requirement_maintenance_requirement_id", "maintenance_requirement_id"),
        Index("ix_block_requirement_station_code", "station_code"),
        Index("ix_block_requirement_line_number", "line_number"),
        Index("ix_block_requirement_earliest_start", "earliest_start"),
        Index("ix_block_requirement_latest_end", "latest_end"),
        Index("ix_block_requirement_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    maintenance_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_requirement.id", ondelete="RESTRICT"),
        nullable=False,
    )
    station_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    block_type: Mapped[str] = mapped_column(String(50), nullable=False)
    required_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    earliest_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latest_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    power_block_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    traffic_block_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    resource_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    maintenance_requirement = relationship(
        "MaintenanceRequirement", back_populates="block_requirements"
    )
    planning_tasks = relationship(
        "PlanningTask",
        back_populates="block_requirement",
        passive_deletes=True,
    )
    candidate_windows = relationship(
        "CandidateBlockWindow",
        back_populates="block_requirement",
        passive_deletes=True,
    )