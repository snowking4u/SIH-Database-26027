from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OptimizationInput(Base):
    """Record which planning inputs were supplied to a particular run.

    A single run may contain many input records. No numerical AI features are
    stored here; this is a structured reference/contract only.
    """

    __tablename__ = "optimization_input"
    __table_args__ = (
        Index("ix_optimization_input_optimization_run_id", "optimization_run_id"),
        Index("ix_optimization_input_planning_task_id", "planning_task_id"),
        Index(
            "ix_optimization_input_candidate_block_window_id",
            "candidate_block_window_id",
        ),
        Index("ix_optimization_input_input_role", "input_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    optimization_run_id: Mapped[int] = mapped_column(
        ForeignKey("optimization_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    planning_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=True,
    )
    candidate_block_window_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_block_window.id", ondelete="RESTRICT"),
        nullable=True,
    )
    planning_constraint_id: Mapped[int | None] = mapped_column(
        ForeignKey("planning_constraint.id", ondelete="RESTRICT"),
        nullable=True,
    )
    planning_resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("planning_resource.id", ondelete="RESTRICT"),
        nullable=True,
    )
    task_dependency_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_dependency.id", ondelete="RESTRICT"),
        nullable=True,
    )
    input_role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    optimization_run = relationship(
        "OptimizationRun", back_populates="inputs"
    )
    planning_task = relationship(
        "PlanningTask", back_populates="optimization_inputs"
    )
    candidate_block_window = relationship(
        "CandidateBlockWindow", back_populates="optimization_inputs"
    )
    planning_constraint = relationship(
        "PlanningConstraint", back_populates="optimization_inputs"
    )
    planning_resource = relationship(
        "PlanningResource", back_populates="optimization_inputs"
    )
    task_dependency = relationship(
        "TaskDependency", back_populates="optimization_inputs"
    )
