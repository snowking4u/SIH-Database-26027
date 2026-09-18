from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AssetParameter(Base):
    __tablename__ = "asset_parameter"
    __table_args__ = (
        Index("ix_asset_parameter_asset_id", "asset_id"),
        Index("ix_asset_parameter_source_system_id", "source_system_id"),
        Index("ix_asset_parameter_code", "parameter_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_system_id: Mapped[int] = mapped_column(
        ForeignKey("source_system.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parameter_code: Mapped[str] = mapped_column(String(100), nullable=False)
    parameter_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    parameter_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recorded_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    asset = relationship("AssetMaster", back_populates="parameters")
    source_system = relationship("SourceSystem", back_populates="parameters")
