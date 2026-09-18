from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# JSONB on PostgreSQL, portable JSON elsewhere (e.g. SQLite test harness).
PayloadType = JSON().with_variant(JSONB(), "postgresql")


class OptimizationOutput(Base):
    """Storage contract for the result produced by a future optimization engine.

    STEP 10 never populates this with an algorithmically optimized result.
    Arbitrary model-specific metadata belongs inside ``output_payload``; no
    fixed AI/score/rank columns are defined.
    """

    __tablename__ = "optimization_output"
    __table_args__ = (
        Index("ix_optimization_output_optimization_run_id", "optimization_run_id"),
        Index("ix_optimization_output_planning_task_id", "planning_task_id"),
        Index(
            "ix_optimization_output_candidate_block_window_id",
            "candidate_block_window_id",
        ),
        Index("ix_optimization_output_output_type", "output_type"),
        Index("ix_optimization_output_selected", "selected"),
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
    output_type: Mapped[str] = mapped_column(String(50), nullable=False)
    output_status: Mapped[str] = mapped_column(String(50), nullable=False)
    selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    output_payload: Mapped[dict | None] = mapped_column(PayloadType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    optimization_run = relationship(
        "OptimizationRun", back_populates="outputs"
    )
    planning_task = relationship(
        "PlanningTask", back_populates="optimization_outputs"
    )
    candidate_block_window = relationship(
        "CandidateBlockWindow", back_populates="optimization_outputs"
    )
