from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.candidate_block_window import CandidateBlockWindow
from app.schemas.candidate_block_window import (
    CandidateBlockWindowResponse,
    CandidateCheckRequest,
    CandidateCheckResponse,
    CandidateGenerationSummary,
)
from app.services.candidate_window import get_or_evaluate_candidate, generate_candidate_windows


router = APIRouter(prefix="/api/candidates", tags=["Candidate Block Window"])


@router.get(
    "/windows",
    response_model=list[CandidateBlockWindowResponse],
    summary="List candidate block windows",
    description=(
        "Return deterministic candidate matches between planning tasks and "
        "available windows. Optionally filter by planning_task_id, "
        "block_requirement_id, available_window_id, feasible or "
        "feasibility_status. No AI/optimization/ranking is applied."
    ),
)
def list_candidate_windows(
    planning_task_id: int | None = None,
    block_requirement_id: int | None = None,
    available_window_id: int | None = None,
    feasible: bool | None = None,
    feasibility_status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(CandidateBlockWindow).order_by(CandidateBlockWindow.id)
    if planning_task_id is not None:
        statement = statement.where(
            CandidateBlockWindow.planning_task_id == planning_task_id
        )
    if block_requirement_id is not None:
        statement = statement.where(
            CandidateBlockWindow.block_requirement_id == block_requirement_id
        )
    if available_window_id is not None:
        statement = statement.where(
            CandidateBlockWindow.available_window_id == available_window_id
        )
    if feasible is not None:
        statement = statement.where(CandidateBlockWindow.feasible == feasible)
    if feasibility_status is not None:
        statement = statement.where(
            CandidateBlockWindow.feasibility_status == feasibility_status
        )
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/windows/{candidate_id}",
    response_model=CandidateBlockWindowResponse,
    summary="Get a candidate block window",
    description="Return one candidate block window by internal identifier.",
)
def get_candidate_window(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.get(CandidateBlockWindow, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate block window not found",
        )
    return candidate


@router.post(
    "/generate",
    response_model=CandidateGenerationSummary,
    status_code=status.HTTP_200_OK,
    summary="Generate candidate block windows",
    description=(
        "Deterministically evaluate every planning task against every available "
        "window using hard feasibility rules. Idempotent; never duplicates a "
        "task/window pair and never modifies source or planning data."
    ),
)
def generate_candidate_window_records(db: Session = Depends(get_db)):
    return generate_candidate_windows(db)


@router.post(
    "/check",
    response_model=CandidateCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check a single candidate pair",
    description=(
        "Evaluate one planning_task / available_window pair deterministically "
        "without creating a duplicate record. Returns the stored evaluation if "
        "one already exists. No optimization is performed."
    ),
)
def check_candidate_pair(
    payload: CandidateCheckRequest,
    db: Session = Depends(get_db),
):
    result = get_or_evaluate_candidate(
        db,
        planning_task_id=payload.planning_task_id,
        available_window_id=payload.available_window_id,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )
    return result