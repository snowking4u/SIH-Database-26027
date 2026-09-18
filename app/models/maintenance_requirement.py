from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MaintenanceRequirement(Base):
    """One normalized maintenance requirement from TMS, TDMS or SMMS.

    planned_date is source-captured information only (not an AI
    recommendation). required_duration_minutes is source-derived work
    duration when available (never optimized).
    """

    __tablename__ = "maintenance_requirement"
    __table_args__ = (
        UniqueConstraint(
            "source_system_id",
            "source_record_type",
            "source_record_id",
            name="uq_maintenance_requirement_source",
        ),
        Index("ix_maintenance_requirement_asset_id", "asset_id"),
        Index("ix_maintenance_requirement_source_system_id", "source_system_id"),
        Index("ix_maintenance_requirement_defect_failure_id", "defect_failure_id"),
        Index("ix_maintenance_requirement_planned_date", "planned_date"),
        Index("ix_maintenance_requirement_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_system_id: Mapped[int] = mapped_column(
        ForeignKey("source_system.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    defect_failure_id: Mapped[int | None] = mapped_column(
        ForeignKey("defect_failure.id", ondelete="RESTRICT"),
        nullable=True,
    )
    maintenance_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    planned_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    asset = relationship("AssetMaster", back_populates="maintenance_requirements")
    source_system = relationship(
        "SourceSystem", back_populates="maintenance_requirements"
    )
    defect_failure = relationship("DefectFailure", back_populates="maintenance_requirements")
    block_requirements = relationship(
        "BlockRequirement",
        back_populates="maintenance_requirement",
        passive_deletes=True,
    )
    planning_tasks = relationship(
        "PlanningTask",
        back_populates="maintenance_requirement",
        passive_deletes=True,
    )