from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TDMSFailure(Base):
    __tablename__ = "tdms_failure"
    __table_args__ = (
        Index("ix_tdms_failure_asset_id", "asset_id"),
        Index("ix_tdms_failure_inspection_id", "inspection_id"),
        Index("ix_tdms_failure_failure_date", "failure_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inspection_id: Mapped[int | None] = mapped_column(
        ForeignKey("tdms_inspection.id", ondelete="RESTRICT"),
        nullable=True,
    )
    failure_code: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    rectification_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset = relationship("AssetMaster", back_populates="tdms_failures")
    inspection = relationship("TDMSInspection", back_populates="failures")
    maintenances = relationship(
        "TDMSMaintenance",
        back_populates="failure",
        passive_deletes=True,
    )