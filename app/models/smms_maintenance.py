from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SMMSMaintenance(Base):
    __tablename__ = "smms_maintenance"
    __table_args__ = (
        Index("ix_smms_maintenance_asset_id", "asset_id"),
        Index("ix_smms_maintenance_alert_id", "alert_id"),
        Index("ix_smms_maintenance_planned_date", "planned_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("smms_alert.id", ondelete="RESTRICT"),
        nullable=True,
    )
    maintenance_type: Mapped[str] = mapped_column(String(100), nullable=False)
    planned_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset = relationship("AssetMaster", back_populates="smms_maintenances")
    alert = relationship("SMMSAlert", back_populates="maintenances")