from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ControllerDecision(Base):
    """Human review/decision record for a block plan.

    This table represents HUMAN decision data. STEP 10 never creates an
    automatic APPROVED decision and never auto-transitions plan status.
    """

    __tablename__ = "controller_decision"
    __table_args__ = (
        Index("ix_controller_decision_block_plan_id", "block_plan_id"),
        Index("ix_controller_decision_decision", "decision"),
        Index("ix_controller_decision_decided_at", "decided_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_plan_id: Mapped[int] = mapped_column(
        ForeignKey("block_plan.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    controller_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    block_plan = relationship("BlockPlan", back_populates="decisions")
