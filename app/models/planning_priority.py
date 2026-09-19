from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlanningPriority(Base):
    """Deterministic priority assessment for one planning task.

    STEP 12 planning-layer table. The assessment is purely deterministic and
    explainable: every factor is derived from existing project data through a
    documented rule (never invented, never ML). ``priority_score`` is a
    reproducible project-baseline composite, NOT an official Indian Railways
    score and NOT an AI prediction, ranking or optimization result.

    ``calculation_version`` stores the exact scoring formula revision
    (``STEP12-DETERMINISTIC-1.0``) so the formula can evolve later without
    losing traceability of previously calculated rows.
    """

    __tablename__ = "planning_priority"
    __table_args__ = (
        UniqueConstraint(
            "planning_task_id",
            name="uq_planning_priority_planning_task",
        ),
        CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100",
            name="ck_planning_priority_score_range",
        ),
        CheckConstraint(
            "defect_age_days >= 0",
            name="ck_planning_priority_defect_age_non_negative",
        ),
        Index("ix_planning_priority_planning_task_id", "planning_task_id"),
        Index("ix_planning_priority_priority_score", "priority_score"),
        Index("ix_planning_priority_priority_band", "priority_band"),
        Index("ix_planning_priority_criticality_level", "criticality_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planning_task_id: Mapped[int] = mapped_column(
        ForeignKey("planning_task.id", ondelete="RESTRICT"),
        nullable=False,
    )
    criticality_level: Mapped[str] = mapped_column(String(20), nullable=False)
    urgency_level: Mapped[str] = mapped_column(String(20), nullable=False)
    safety_impact: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_availability_impact: Mapped[str] = mapped_column(String(20), nullable=False)
    traffic_impact: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_recurrence: Mapped[str] = mapped_column(String(20), nullable=False)
    defect_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    priority_band: Mapped[str] = mapped_column(String(20), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(50), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    calculation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    planning_task = relationship("PlanningTask", back_populates="priority")