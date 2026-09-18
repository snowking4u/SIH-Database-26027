from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BlockPlan(Base):
    """A complete planning proposal/version.

    Creating a plan record does NOT mean the plan is approved. Approval is
    represented only by an explicit human ``controller_decision``.
    """

    __tablename__ = "block_plan"
    __table_args__ = (
        Index("ix_block_plan_optimization_run_id", "optimization_run_id"),
        Index("ix_block_plan_plan_date", "plan_date"),
        Index("ix_block_plan_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    optimization_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("optimization_run.id", ondelete="RESTRICT"),
        nullable=True,
    )
    plan_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    planning_horizon_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planning_horizon_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    optimization_run = relationship(
        "OptimizationRun", back_populates="block_plans"
    )
    block_plan_tasks = relationship(
        "BlockPlanTask",
        back_populates="block_plan",
        passive_deletes=True,
    )
    validations = relationship(
        "PlanValidation",
        back_populates="block_plan",
        passive_deletes=True,
    )
    decisions = relationship(
        "ControllerDecision",
        back_populates="block_plan",
        passive_deletes=True,
    )
    execution_outcomes = relationship(
        "ExecutionOutcome",
        back_populates="block_plan",
        passive_deletes=True,
    )
