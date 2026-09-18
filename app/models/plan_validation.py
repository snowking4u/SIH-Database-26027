from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlanValidation(Base):
    """Deterministic validation result for a block plan.

    This is NOT AI and never approval. No validation scores or AI confidence
    values are stored.
    """

    __tablename__ = "plan_validation"
    __table_args__ = (
        Index("ix_plan_validation_block_plan_id", "block_plan_id"),
        Index("ix_plan_validation_validation_type", "validation_type"),
        Index("ix_plan_validation_validation_status", "validation_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_plan_id: Mapped[int] = mapped_column(
        ForeignKey("block_plan.id", ondelete="RESTRICT"),
        nullable=False,
    )
    validation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    validator_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    block_plan = relationship("BlockPlan", back_populates="validations")
