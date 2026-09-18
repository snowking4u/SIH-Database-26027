from decimal import Decimal

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LocationMaster(Base):
    __tablename__ = "location_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zone_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    division_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    division_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    section_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    station_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    station_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    line_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    km_start: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    km_end: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    assets = relationship(
        "AssetMaster",
        back_populates="location",
        passive_deletes=True,
    )
