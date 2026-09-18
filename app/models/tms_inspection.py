from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TMSInspection(Base):
    __tablename__ = "tms_inspection"
    __table_args__ = (
        Index("ix_tms_inspection_asset_id", "asset_id"),
        Index("ix_tms_inspection_inspection_date", "inspection_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inspection_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    inspection_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parameter_code: Mapped[str] = mapped_column(String(100), nullable=False)
    parameter_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset = relationship("AssetMaster", back_populates="tms_inspections")
    defects = relationship(
        "TMSDefect",
        back_populates="inspection",
        passive_deletes=True,
    )