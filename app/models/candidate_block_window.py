from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CandidateBlockWindow(Base):
    """Deterministic candidate match between a planning task and an available window.

    The row records "this task CAN potentially fit into this available window"
    under explicit hard feasibility rules. It is NOT a recommended window, an
    optimal window, a final block, an approved block, or an AI decision.

    ``candidate_duration_minutes`` is the source-derived required duration.
    A value of ``0`` is the deterministic sentinel used only for the
    ``MISSING_DURATION`` review case (no duration is ever invented).
    """

    __tablename__ = "candidate_block_window"
    __table_args__ = (
        UniqueConstraint(
            "planning_task_id",
            "available_window_id",
            name="uq_candidate_block_window_task_window",
        ),
        CheckConstraint(
            "candidate_end > candidate_start",
            name="ck_candidate_block_window_end_gt_start",
        ),
        CheckConstraint(
            "candidate_duration_minutes >= 0",
            name="ck_candidate_block_window_duration_non_negative",
        ),
        Index("ix_candidate_block_window_planning_task_id", "planning_task_id"),
        Index("ix_candidate_block_window_block_requirement_id", "block_requirement_id"),
        Index("ix_candidate_block_window_available_window_id", "available_window_id"),
        Index("ix_candidate_block_window_feasible", "feasible"),
        Index("ix_candidate_block_window_feasibility_status", "feasibility_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planning_task_id: Mapped[int] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=False,
    )
    block_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("block_requirement.id", ondelete="RESTRICT"),
        nullable=True,
    )
    available_window_id: Mapped[int] = mapped_column(
        ForeignKey("available_window.id", ondelete="RESTRICT"),
        nullable=False,
    )
    candidate_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    candidate_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    candidate_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    feasible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    feasibility_status: Mapped[str] = mapped_column(String(50), nullable=False)
    feasibility_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    planning_task = relationship(
        "PlanningTask", back_populates="candidate_windows"
    )
    block_requirement = relationship(
        "BlockRequirement", back_populates="candidate_windows"
    )
    available_window = relationship(
        "AvailableWindow", back_populates="candidate_windows"
    )
    optimization_inputs = relationship(
        "OptimizationInput",
        back_populates="candidate_block_window",
        passive_deletes=True,
    )
    optimization_outputs = relationship(
        "OptimizationOutput",
        back_populates="candidate_block_window",
        passive_deletes=True,
    )
    block_plan_tasks = relationship(
        "BlockPlanTask",
        back_populates="candidate_block_window",
        passive_deletes=True,
    )