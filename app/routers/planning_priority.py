"""STEP 12 router: deterministic criticality & priority assessments.

Read-only list/get endpoints plus deterministic recalculation triggers. No
endpoint here selects a best task, optimizes a plan or recommends a block;
that belongs to the future AI/optimization layer.

Route ordering note
-------------------
Static paths MUST be registered before dynamic paths that could overlap them.
``POST /priority/recalculate`` is declared BEFORE ``GET /priority/{priority_id}``
so a request to ``/priority/recalculate`` is never captured by the ``{priority_id}``
integer route (FastAPI evaluates route patterns in registration order).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.planning_priority import PlanningPriority
from app.models.planning_task import PlanningTask
from app.schemas.planning_priority import PlanningPriorityResponse
from app.services.planning_priority import (
    recalculate_all_priorities,
    recalculate_task_priority,
)


router = APIRouter(prefix="/api/planning", tags=["Planning Priority"])


@router.get(
    "/priority",
    response_model=list[PlanningPriorityResponse],
    summary="List priority assessments",
    description=(
        "Return deterministic priority assessments for planning tasks. "
        "Optionally filter by priority_band, criticality_level, urgency_level, "
        "min_score, max_score or asset_id. No AI/ML is involved; the score is a "
        "documented deterministic project baseline."
    ),
)
def list_priorities(
    priority_band: str | None = None,
    criticality_level: str | None = None,
    urgency_level: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(PlanningPriority).order_by(PlanningPriority.id)
    if priority_band is not None:
        statement = statement.where(PlanningPriority.priority_band == priority_band)
    if criticality_level is not None:
        statement = statement.where(
            PlanningPriority.criticality_level == criticality_level
        )
    if urgency_level is not None:
        statement = statement.where(PlanningPriority.urgency_level == urgency_level)
    if min_score is not None:
        statement = statement.where(PlanningPriority.priority_score >= min_score)
    if max_score is not None:
        statement = statement.where(PlanningPriority.priority_score <= max_score)
    if asset_id is not None:
        statement = statement.join(
            PlanningTask, PlanningPriority.planning_task_id == PlanningTask.id
        ).where(PlanningTask.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/priority/recalculate",
    status_code=status.HTTP_200_OK,
    summary="Recalculate priority for eligible planning tasks",
    description=(
        "Deterministically recompute priority assessments for every planning "
        "task. Idempotent; existing assessments are updated in place, no "
        "duplicates are created. Returns creation/update/processed counts."
    ),
)
def recalculate_all(db: Session = Depends(get_db)):
    return recalculate_all_priorities(db)


@router.get(
    "/priority/{priority_id}",
    response_model=PlanningPriorityResponse,
    summary="Get a priority assessment",
    description="Return one priority assessment by internal identifier.",
)
def get_priority(priority_id: int, db: Session = Depends(get_db)):
    priority = db.get(PlanningPriority, priority_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Priority assessment not found",
        )
    return priority


@router.get(
    "/tasks/{task_id}/priority",
    response_model=PlanningPriorityResponse,
    summary="Get priority for a planning task",
    description=(
        "Return the single current priority assessment of a planning task, if "
        "one has been calculated."
    ),
)
def get_task_priority(task_id: int, db: Session = Depends(get_db)):
    task = db.get(PlanningTask, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning task not found",
        )
    priority = db.scalar(
        select(PlanningPriority).where(PlanningPriority.planning_task_id == task_id)
    )
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Priority not calculated for this planning task",
        )
    return priority


@router.post(
    "/tasks/{task_id}/priority/recalculate",
    response_model=PlanningPriorityResponse,
    status_code=status.HTTP_200_OK,
    summary="Recalculate priority for one planning task",
    description=(
        "Deterministically recompute the priority assessment of one planning "
        "task. Idempotent; creates or updates the single assessment row. Never "
        "modifies source data and never runs AI/ML."
    ),
)
def recalculate_single_priority(task_id: int, db: Session = Depends(get_db)):
    priority = recalculate_task_priority(db, task_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning task not found",
        )
    return priority