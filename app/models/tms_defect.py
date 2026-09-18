from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TMSDefect(Base):
    __tablename__ = "tms_defect"
    __table_args__ = (
        Index("ix_tms_defect_asset_id", "asset_id"),
        Index("ix_tms_defect_inspection_id", "inspection_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("tms_inspection.id", ondelete="RESTRICT"),
        nullable=False,
    )
    defect_code: Mapped[str] = mapped_column(String(100), nullable=False)
    defect_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detected_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset = relationship("AssetMaster", back_populates="tms_defects")
    inspection = relationship("TMSInspection", back_populates="defects")
    maintenances = relationship(
        "TMSMaintenance",
        back_populates="defect",
        passive_deletes=True,
    )