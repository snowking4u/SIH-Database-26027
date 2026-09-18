from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AssetMaster(Base):
    __tablename__ = "asset_master"
    __table_args__ = (
        UniqueConstraint(
            "source_system_id",
            "source_asset_id",
            name="uq_asset_master_source_system_asset",
        ),
        Index("ix_asset_master_source_system_id", "source_system_id"),
        Index("ix_asset_master_location_id", "location_id"),
        Index("ix_asset_master_source_asset_id", "source_asset_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_system_id: Mapped[int] = mapped_column(
        ForeignKey("source_system.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_asset_id: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_subtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location_master.id", ondelete="SET NULL"),
        nullable=True,
    )
    installation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_system = relationship("SourceSystem", back_populates="assets")
    location = relationship("LocationMaster", back_populates="assets")
    parameters = relationship(
        "AssetParameter",
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tms_inspections = relationship(
        "TMSInspection",
        back_populates="asset",
        passive_deletes=True,
    )
    tms_defects = relationship(
        "TMSDefect",
        back_populates="asset",
        passive_deletes=True,
    )
    tms_maintenances = relationship(
        "TMSMaintenance",
        back_populates="asset",
        passive_deletes=True,
    )
    tdms_inspections = relationship(
        "TDMSInspection",
        back_populates="asset",
        passive_deletes=True,
    )
    tdms_failures = relationship(
        "TDMSFailure",
        back_populates="asset",
        passive_deletes=True,
    )
    tdms_maintenances = relationship(
        "TDMSMaintenance",
        back_populates="asset",
        passive_deletes=True,
    )
    smms_inspections = relationship(
        "SMMSInspection",
        back_populates="asset",
        passive_deletes=True,
    )
    smms_alerts = relationship(
        "SMMSAlert",
        back_populates="asset",
        passive_deletes=True,
    )
    smms_maintenances = relationship(
        "SMMSMaintenance",
        back_populates="asset",
        passive_deletes=True,
    )
    defect_failures = relationship(
        "DefectFailure",
        back_populates="asset",
        passive_deletes=True,
    )
    maintenance_requirements = relationship(
        "MaintenanceRequirement",
        back_populates="asset",
        passive_deletes=True,
    )
    planning_tasks = relationship(
        "PlanningTask",
        back_populates="asset",
        passive_deletes=True,
    )
