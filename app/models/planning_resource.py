from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlanningResource(Base):
    """A resource that may be required/available for maintenance planning.

    Resources may be centrally maintained or originate from a source system
    (source_system_id is nullable for project-managed resources). This is a
    structured planning input, not an optimization output.
    """

    __tablename__ = "planning_resource"
    __table_args__ = (
        Index("ix_planning_resource_resource_type", "resource_type"),
        Index("ix_planning_resource_status", "status"),
        Index("ix_planning_resource_location_code", "location_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_code: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    location_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_system_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_system.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    source_system = relationship(
        "SourceSystem", back_populates="planning_resources"
    )
    task_resources = relationship(
        "TaskResource",
        back_populates="planning_resource",
        passive_deletes=True,
    )
    optimization_inputs = relationship(
        "OptimizationInput",
        back_populates="planning_resource",
        passive_deletes=True,
    )