from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExecutionOutcome(Base):
    """What actually happened after a plan was executed.

    STEP 10 never invents execution results; records are supplied explicitly.
    """

    __tablename__ = "execution_outcome"
    __table_args__ = (
        CheckConstraint(
            "actual_start IS NULL OR actual_end IS NULL OR actual_start < actual_end",
            name="ck_execution_outcome_actual_start_lt_end",
        ),
        CheckConstraint(
            "actual_duration_minutes IS NULL OR actual_duration_minutes >= 0",
            name="ck_execution_outcome_actual_duration_non_negative",
        ),
        Index("ix_execution_outcome_block_plan_id", "block_plan_id"),
        Index("ix_execution_outcome_block_plan_task_id", "block_plan_task_id"),
        Index("ix_execution_outcome_execution_status", "execution_status"),
        Index("ix_execution_outcome_actual_start", "actual_start"),
        Index("ix_execution_outcome_actual_end", "actual_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_plan_id: Mapped[int] = mapped_column(
        ForeignKey("block_plan.id", ondelete="RESTRICT"),
        nullable=False,
    )
    block_plan_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("block_plan_task.id", ondelete="RESTRICT"),
        nullable=True,
    )
    execution_status: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    block_plan = relationship("BlockPlan", back_populates="execution_outcomes")
    block_plan_task = relationship(
        "BlockPlanTask", back_populates="execution_outcomes"
    )
