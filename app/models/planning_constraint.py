from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlanningConstraint(Base):
    """A constraint a planning algorithm must respect.

    These describe requirements derived deterministically from source data
    (e.g. a block requirement). They are NOT optimization decisions or AI
    outputs.
    """

    __tablename__ = "planning_constraint"
    __table_args__ = (
        Index("ix_planning_constraint_planning_task_id", "planning_task_id"),
        Index("ix_planning_constraint_constraint_type", "constraint_type"),
        Index("ix_planning_constraint_hard_constraint", "hard_constraint"),
        Index("ix_planning_constraint_effective_start", "effective_start"),
        Index("ix_planning_constraint_effective_end", "effective_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planning_task_id: Mapped[int] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=False,
    )
    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    constraint_value: Mapped[str] = mapped_column(String(255), nullable=False)
    hard_constraint: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    effective_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    planning_task = relationship("PlanningTask", back_populates="constraints")
    optimization_inputs = relationship(
        "OptimizationInput",
        back_populates="planning_constraint",
        passive_deletes=True,
    )