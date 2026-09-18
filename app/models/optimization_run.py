from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OptimizationRun(Base):
    """One execution/request record for a future optimization process.

    This is a lifecycle/storage contract only. STEP 10 does NOT implement a
    model or optimization algorithm; ``model_name``/``model_version`` are
    metadata placeholders and snapshot hashes are caller-supplied values.
    """

    __tablename__ = "optimization_run"
    __table_args__ = (
        Index("ix_optimization_run_status", "status"),
        Index("ix_optimization_run_run_type", "run_type"),
        Index("ix_optimization_run_requested_at", "requested_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_snapshot_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_snapshot_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    objective_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    inputs = relationship(
        "OptimizationInput",
        back_populates="optimization_run",
        passive_deletes=True,
    )
    outputs = relationship(
        "OptimizationOutput",
        back_populates="optimization_run",
        passive_deletes=True,
    )
    block_plans = relationship(
        "BlockPlan",
        back_populates="optimization_run",
        passive_deletes=True,
    )
