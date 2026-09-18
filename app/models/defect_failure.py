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


class DefectFailure(Base):
    """One normalized defect/failure/alert record from TMS, TDMS or SMMS.

    Provenance is preserved via (source_system_id, source_record_type,
    source_record_id). No polymorphic database FK is used because
    source_record_id may reference different source tables per type.
    """

    __tablename__ = "defect_failure"
    __table_args__ = (
        UniqueConstraint(
            "source_system_id",
            "source_record_type",
            "source_record_id",
            name="uq_defect_failure_source",
        ),
        Index("ix_defect_failure_asset_id", "asset_id"),
        Index("ix_defect_failure_source_system_id", "source_system_id"),
        Index("ix_defect_failure_source_record_type", "source_record_type"),
        Index("ix_defect_failure_detected_at", "detected_at"),
        Index("ix_defect_failure_status", "status"),
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
    defect_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    defect_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    rectified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    asset = relationship("AssetMaster", back_populates="defect_failures")
    source_system = relationship(
        "SourceSystem", back_populates="defect_failures"
    )
    maintenance_requirements = relationship(
        "MaintenanceRequirement",
        back_populates="defect_failure",
        passive_deletes=True,
    )