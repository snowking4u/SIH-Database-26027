from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TMSMaintenance(Base):
    __tablename__ = "tms_maintenance"
    __table_args__ = (
        Index("ix_tms_maintenance_asset_id", "asset_id"),
        Index("ix_tms_maintenance_defect_id", "defect_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    defect_id: Mapped[int] = mapped_column(
        ForeignKey("tms_defect.id", ondelete="RESTRICT"),
        nullable=False,
    )
    maintenance_type: Mapped[str] = mapped_column(String(100), nullable=False)
    planned_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset = relationship("AssetMaster", back_populates="tms_maintenances")
    defect = relationship("TMSDefect", back_populates="maintenances")