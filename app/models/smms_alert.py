from datetime import datetime, timedelta

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Interval, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SMMSAlert(Base):
    __tablename__ = "smms_alert"
    __table_args__ = (
        Index("ix_smms_alert_asset_id", "asset_id"),
        Index("ix_smms_alert_inspection_id", "inspection_id"),
        Index("ix_smms_alert_incidence_date_time", "incidence_date_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inspection_id: Mapped[int | None] = mapped_column(
        ForeignKey("smms_inspection.id", ondelete="RESTRICT"),
        nullable=True,
    )
    alert_type_code: Mapped[str] = mapped_column(String(100), nullable=False)
    alert_feedback_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alert_status_code: Mapped[str] = mapped_column(String(100), nullable=False)
    cause_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    incidence_date_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    rectification_date_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    incidence_duration: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)
    alert_feedback_date_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    maintainer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    maintainer_designation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    maintainer_mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)

    asset = relationship("AssetMaster", back_populates="smms_alerts")
    inspection = relationship("SMMSInspection", back_populates="alerts")
    maintenances = relationship(
        "SMMSMaintenance",
        back_populates="alert",
        passive_deletes=True,
    )