from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
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


class BlockPlanTask(Base):
    """A planning task placed into a block plan.

    STEP 10 never calculates or optimizes these values; records are supplied
    explicitly. One planning task may appear at most once per block plan.
    """

    __tablename__ = "block_plan_task"
    __table_args__ = (
        UniqueConstraint(
            "block_plan_id",
            "planning_task_id",
            name="uq_block_plan_task_plan_task",
        ),
        CheckConstraint(
            "planned_start < planned_end",
            name="ck_block_plan_task_start_lt_end",
        ),
        CheckConstraint(
            "planned_duration_minutes > 0",
            name="ck_block_plan_task_duration_positive",
        ),
        Index("ix_block_plan_task_block_plan_id", "block_plan_id"),
        Index("ix_block_plan_task_planning_task_id", "planning_task_id"),
        Index(
            "ix_block_plan_task_candidate_block_window_id",
            "candidate_block_window_id",
        ),
        Index("ix_block_plan_task_planned_start", "planned_start"),
        Index("ix_block_plan_task_planned_end", "planned_end"),
        Index("ix_block_plan_task_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_plan_id: Mapped[int] = mapped_column(
        ForeignKey("block_plan.id", ondelete="RESTRICT"),
        nullable=False,
    )
    planning_task_id: Mapped[int] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=False,
    )
    candidate_block_window_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_block_window.id", ondelete="RESTRICT"),
        nullable=True,
    )
    planned_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    block_plan = relationship("BlockPlan", back_populates="block_plan_tasks")
    planning_task = relationship(
        "PlanningTask", back_populates="block_plan_tasks"
    )
    candidate_block_window = relationship(
        "CandidateBlockWindow", back_populates="block_plan_tasks"
    )
    execution_outcomes = relationship(
        "ExecutionOutcome",
        back_populates="block_plan_task",
        passive_deletes=True,
    )
