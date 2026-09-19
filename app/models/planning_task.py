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


class PlanningTask(Base):
    """A maintenance activity represented as a planning-ready task.

    Created deterministically from maintenance_requirement (and optionally
    block_requirement). duration_minutes is the known/normalized source-derived
    duration and is never optimized or invented. No AI/optimization fields.
    """

    __tablename__ = "planning_task"
    __table_args__ = (
        UniqueConstraint(
            "maintenance_requirement_id",
            name="uq_planning_task_maintenance_requirement",
        ),
        Index("ix_planning_task_block_requirement_id", "block_requirement_id"),
        Index("ix_planning_task_asset_id", "asset_id"),
        Index("ix_planning_task_task_code", "task_code"),
        Index("ix_planning_task_status", "status"),
        Index("ix_planning_task_earliest_start", "earliest_start"),
        Index("ix_planning_task_latest_end", "latest_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    maintenance_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_requirement.id", ondelete="RESTRICT"),
        nullable=False,
    )
    block_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("block_requirement.id", ondelete="RESTRICT"),
        nullable=True,
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset_master.id", ondelete="RESTRICT"),
        nullable=False,
    )
    task_code: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    earliest_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latest_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    location_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    maintenance_requirement = relationship(
        "MaintenanceRequirement", back_populates="planning_tasks"
    )
    block_requirement = relationship("BlockRequirement", back_populates="planning_tasks")
    asset = relationship("AssetMaster", back_populates="planning_tasks")
    constraints = relationship(
        "PlanningConstraint",
        back_populates="planning_task",
        passive_deletes=True,
    )
    candidate_windows = relationship(
        "CandidateBlockWindow",
        back_populates="planning_task",
        passive_deletes=True,
    )
    task_resources = relationship(
        "TaskResource",
        back_populates="planning_task",
        passive_deletes=True,
    )
    predecessor_dependencies = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.predecessor_task_id",
        back_populates="predecessor",
        passive_deletes=True,
    )
    successor_dependencies = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.successor_task_id",
        back_populates="successor",
        passive_deletes=True,
    )
    optimization_inputs = relationship(
        "OptimizationInput",
        back_populates="planning_task",
        passive_deletes=True,
    )
    optimization_outputs = relationship(
        "OptimizationOutput",
        back_populates="planning_task",
        passive_deletes=True,
    )
    block_plan_tasks = relationship(
        "BlockPlanTask",
        back_populates="planning_task",
        passive_deletes=True,
    )
    priority = relationship(
        "PlanningPriority",
        back_populates="planning_task",
        uselist=False,
        passive_deletes=True,
    )