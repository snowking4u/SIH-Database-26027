"""STEP 11 optional optimization-layer placeholder generation.

This phase never runs an optimizer. When ``with_optimization`` is requested it
records the run lifecycle and which planning inputs WOULD be supplied to a
future optimization engine; no ``optimization_output`` is produced and nothing
is selected or ranked. All records are tagged synthetic for cleanup safety.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.optimization_input import OptimizationInput
from app.models.optimization_run import OptimizationRun
from app.models.planning_task import PlanningTask

from .config import MARKER, SyntheticConfig


def generate_optimization_placeholder(
    db: Session, cfg: SyntheticConfig, dataset_id: str
) -> dict:
    """Create a synthetic run + input references only (no outputs, no ranking)."""
    existing = db.scalar(
        select(OptimizationRun).where(OptimizationRun.run_code.startswith("SYN-OPT-"))
    )
    if existing is not None:
        return {"run_created": 0, "inputs_created": 0, "skipped_run": 1,
                "run_code": existing.run_code}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run = OptimizationRun(
        run_code=f"SYN-OPT-{dataset_id}-0001",
        run_type="SYNTHETIC_PLACEHOLDER",
        status="PENDING",
        requested_at=now,
        started_at=None,
        completed_at=None,
        model_name=None,
        model_version=None,
        input_snapshot_hash=None,
        output_snapshot_hash=None,
        objective_description=(
            f"{MARKER} placeholder run; no optimization performed. "
            "Records inputs only; produces no recommendations."
        ),
        error_message=None,
    )
    db.add(run)
    db.flush()

    inputs_created = 0
    tasks = db.scalars(
        select(PlanningTask).order_by(PlanningTask.id)
    ).all()
    for task in tasks:
        db.add(
            OptimizationInput(
                optimization_run_id=run.id,
                planning_task_id=task.id,
                candidate_block_window_id=None,
                planning_constraint_id=None,
                planning_resource_id=None,
                task_dependency_id=None,
                input_role="PLANNING_TASK",
            )
        )
        inputs_created += 1
        if inputs_created % max(1, cfg.batch_size) == 0:
            db.flush()
    db.commit()
    return {"run_created": 1, "inputs_created": inputs_created, "skipped_run": 0,
            "run_code": run.run_code}