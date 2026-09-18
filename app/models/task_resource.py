from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaskResource(Base):
    """Link between a planning task and a planning resource.

    allocation_status records resource assignment data only (REQUIRED /
    AVAILABLE / ALLOCATED / UNAVAILABLE). It does NOT represent an optimized
    final schedule.
    """

    __tablename__ = "task_resource"
    __table_args__ = (
        UniqueConstraint(
            "planning_task_id",
            "planning_resource_id",
            name="uq_task_resource_planning_task_resource",
        ),
        Index("ix_task_resource_planning_task_id", "planning_task_id"),
        Index("ix_task_resource_planning_resource_id", "planning_resource_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planning_task_id: Mapped[int] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=False,
    )
    planning_resource_id: Mapped[int] = mapped_column(
        ForeignKey("planning_resource.id", ondelete="RESTRICT"),
        nullable=False,
    )
    required_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    planning_task = relationship("PlanningTask", back_populates="task_resources")
    planning_resource = relationship(
        "PlanningResource", back_populates="task_resources"
    )