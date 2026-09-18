from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SourceSystem(Base):
    __tablename__ = "source_system"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    system_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    assets = relationship(
        "AssetMaster",
        back_populates="source_system",
        passive_deletes=True,
    )
    parameters = relationship(
        "AssetParameter",
        back_populates="source_system",
        passive_deletes=True,
    )
    trains = relationship(
        "Train",
        back_populates="source_system",
        passive_deletes=True,
    )
    defect_failures = relationship(
        "DefectFailure",
        back_populates="source_system",
        passive_deletes=True,
    )
    maintenance_requirements = relationship(
        "MaintenanceRequirement",
        back_populates="source_system",
        passive_deletes=True,
    )
    planning_resources = relationship(
        "PlanningResource",
        back_populates="source_system",
        passive_deletes=True,
    )
