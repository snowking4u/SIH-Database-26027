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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaskDependency(Base):
    """Ordering/dependency relationship between planning tasks.

    A task must never depend on itself. Dependency records describe required
    ordering only; no automatic dependency optimization is performed here.
    """

    __tablename__ = "task_dependency"
    __table_args__ = (
        UniqueConstraint(
            "predecessor_task_id",
            "successor_task_id",
            "dependency_type",
            name="uq_task_dependency_predecessor_successor_type",
        ),
        CheckConstraint(
            "predecessor_task_id <> successor_task_id",
            name="ck_task_dependency_predecessor_ne_successor",
        ),
        CheckConstraint(
            "lag_minutes >= 0",
            name="ck_task_dependency_lag_minutes_non_negative",
        ),
        Index("ix_task_dependency_predecessor_task_id", "predecessor_task_id"),
        Index("ix_task_dependency_successor_task_id", "successor_task_id"),
        Index("ix_task_dependency_dependency_type", "dependency_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    predecessor_task_id: Mapped[int] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=False,
    )
    successor_task_id: Mapped[int] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(String(50), nullable=False)
    lag_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), default=0
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    predecessor = relationship(
        "PlanningTask",
        foreign_keys=[predecessor_task_id],
        back_populates="predecessor_dependencies",
    )
    successor = relationship(
        "PlanningTask",
        foreign_keys=[successor_task_id],
        back_populates="successor_dependencies",
    )
    optimization_inputs = relationship(
        "OptimizationInput",
        back_populates="task_dependency",
        passive_deletes=True,
    )