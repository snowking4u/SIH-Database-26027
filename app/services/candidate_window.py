"""STEP 9 deterministic candidate-window feasibility layer.

The service matches ``planning_task`` (and its linked ``block_requirement``)
against existing ``available_window`` records using explicit hard feasibility
rules. Every evaluated pair produces a ``candidate_block_window`` row whose
meaning is:

    "this task CAN potentially fit into this available window"

It is NOT a recommended window, an optimal window, a final block, an
approved block, or an AI decision. No AI/ML/optimization/ranking/scoring is
performed anywhere in this module.

Rules
-----
- Duration comes only from ``planning_task.duration_minutes``, falling back to
  ``block_requirement.required_duration_minutes``. If neither exists the
  candidate is ``REQUIRES_REVIEW`` with reason ``MISSING_DURATION`` and
  ``candidate_duration_minutes = 0`` (a documented sentinel; no duration is
  ever invented).
- Candidate start uses deterministic earliest-fit:
  ``max(available_window.window_start, block_requirement.earliest_start)``.
- Candidate must fit entirely inside the available window and (when provided)
  the ``earliest_start`` / ``latest_end`` bounds.
- Location/line must match exactly when both sides are known; missing context
  produces ``REQUIRES_REVIEW`` context codes, never an invented location.
- Power/traffic block requirements are NOT satisfied by this layer; they
  produce ``REQUIRES_REVIEW`` confirmation codes.
- ``available_window`` is read-only and is never modified.
- No candidate is ranked or selected; no winner is chosen.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.available_window import AvailableWindow
from app.models.block_requirement import BlockRequirement
from app.models.candidate_block_window import CandidateBlockWindow
from app.models.planning_task import PlanningTask

FEASIBLE_STATUS = "FEASIBLE"
INFEASIBLE_STATUS = "INFEASIBLE"
REQUIRES_REVIEW_STATUS = "REQUIRES_REVIEW"

FEASIBLE_TEMPORAL_MATCH = "FEASIBLE_TEMPORAL_MATCH"
DURATION_EXCEEDS_WINDOW = "DURATION_EXCEEDS_WINDOW"
LOCATION_MISMATCH = "LOCATION_MISMATCH"
LINE_MISMATCH = "LINE_MISMATCH"
EARLIEST_START_VIOLATION = "EARLIEST_START_VIOLATION"
LATEST_END_VIOLATION = "LATEST_END_VIOLATION"
POWER_BLOCK_CONFIRMATION_REQUIRED = "POWER_BLOCK_CONFIRMATION_REQUIRED"
TRAFFIC_BLOCK_CONFIRMATION_REQUIRED = "TRAFFIC_BLOCK_CONFIRMATION_REQUIRED"
MISSING_DURATION = "MISSING_DURATION"
MISSING_LOCATION_CONTEXT = "MISSING_LOCATION_CONTEXT"
MISSING_LINE_CONTEXT = "MISSING_LINE_CONTEXT"


def _required_duration(
    planning_task: PlanningTask, block: BlockRequirement | None
) -> int | None:
    if planning_task.duration_minutes is not None and planning_task.duration_minutes > 0:
        return planning_task.duration_minutes
    if (
        block is not None
        and block.required_duration_minutes is not None
        and block.required_duration_minutes > 0
    ):
        return block.required_duration_minutes
    return None


def _span_for(available_window: AvailableWindow) -> tuple:
    start, end = available_window.window_start, available_window.window_end
    if start > end:
        start, end = end, start
    return start, end


def evaluate_candidate(
    planning_task: PlanningTask,
    available_window: AvailableWindow,
    block: BlockRequirement | None = None,
) -> dict:
    """Evaluate one (task, available window) pair with deterministic rules.

    Returns a plain dict snapshot of the candidate fields. Never writes.
    """
    duration = _required_duration(planning_task, block)

    if duration is None:
        start, end = _span_for(available_window)
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id if block is not None else None,
            "available_window_id": available_window.id,
            "candidate_start": start,
            "candidate_end": end,
            "candidate_duration_minutes": 0,
            "feasible": False,
            "feasibility_status": REQUIRES_REVIEW_STATUS,
            "feasibility_reason": MISSING_DURATION,
        }

    window_valid = (
        available_window.window_start < available_window.window_end
        and available_window.duration_minutes is not None
        and available_window.duration_minutes > 0
    )
    if not window_valid:
        start, end = _span_for(available_window)
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id if block is not None else None,
            "available_window_id": available_window.id,
            "candidate_start": start,
            "candidate_end": end,
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": INFEASIBLE_STATUS,
            "feasibility_reason": DURATION_EXCEEDS_WINDOW,
        }

    if available_window.duration_minutes < duration:
        candidate_end = available_window.window_start + timedelta(minutes=duration)
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id if block is not None else None,
            "available_window_id": available_window.id,
            "candidate_start": available_window.window_start,
            "candidate_end": candidate_end,
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": INFEASIBLE_STATUS,
            "feasibility_reason": DURATION_EXCEEDS_WINDOW,
        }

    if block is not None and block.station_code:
        if available_window.station_code != block.station_code:
            return {
                "planning_task_id": planning_task.id,
                "block_requirement_id": block.id,
                "available_window_id": available_window.id,
                "candidate_start": available_window.window_start,
                "candidate_end": available_window.window_start
                + timedelta(minutes=duration),
                "candidate_duration_minutes": duration,
                "feasible": False,
                "feasibility_status": INFEASIBLE_STATUS,
                "feasibility_reason": LOCATION_MISMATCH,
            }
    else:
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id if block is not None else None,
            "available_window_id": available_window.id,
            "candidate_start": available_window.window_start,
            "candidate_end": available_window.window_start
            + timedelta(minutes=duration),
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": REQUIRES_REVIEW_STATUS,
            "feasibility_reason": MISSING_LOCATION_CONTEXT,
        }

    if block is not None and block.line_number:
        if available_window.line_number != block.line_number:
            return {
                "planning_task_id": planning_task.id,
                "block_requirement_id": block.id,
                "available_window_id": available_window.id,
                "candidate_start": available_window.window_start,
                "candidate_end": available_window.window_start
                + timedelta(minutes=duration),
                "candidate_duration_minutes": duration,
                "feasible": False,
                "feasibility_status": INFEASIBLE_STATUS,
                "feasibility_reason": LINE_MISMATCH,
            }
    else:
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id if block is not None else None,
            "available_window_id": available_window.id,
            "candidate_start": available_window.window_start,
            "candidate_end": available_window.window_start
            + timedelta(minutes=duration),
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": REQUIRES_REVIEW_STATUS,
            "feasibility_reason": MISSING_LINE_CONTEXT,
        }

    candidate_start = available_window.window_start
    if block is not None and block.earliest_start is not None:
        if block.earliest_start > candidate_start:
            candidate_start = block.earliest_start
    candidate_end = candidate_start + timedelta(minutes=duration)

    if (
        block is not None
        and block.earliest_start is not None
        and candidate_start < block.earliest_start
    ):
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id,
            "available_window_id": available_window.id,
            "candidate_start": candidate_start,
            "candidate_end": candidate_end,
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": INFEASIBLE_STATUS,
            "feasibility_reason": EARLIEST_START_VIOLATION,
        }

    if candidate_end > available_window.window_end:
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id if block is not None else None,
            "available_window_id": available_window.id,
            "candidate_start": candidate_start,
            "candidate_end": candidate_end,
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": INFEASIBLE_STATUS,
            "feasibility_reason": DURATION_EXCEEDS_WINDOW,
        }

    if (
        block is not None
        and block.latest_end is not None
        and candidate_end > block.latest_end
    ):
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id,
            "available_window_id": available_window.id,
            "candidate_start": candidate_start,
            "candidate_end": candidate_end,
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": INFEASIBLE_STATUS,
            "feasibility_reason": LATEST_END_VIOLATION,
        }

    if block is not None and block.power_block_required:
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id,
            "available_window_id": available_window.id,
            "candidate_start": candidate_start,
            "candidate_end": candidate_end,
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": REQUIRES_REVIEW_STATUS,
            "feasibility_reason": POWER_BLOCK_CONFIRMATION_REQUIRED,
        }

    if block is not None and block.traffic_block_required:
        return {
            "planning_task_id": planning_task.id,
            "block_requirement_id": block.id,
            "available_window_id": available_window.id,
            "candidate_start": candidate_start,
            "candidate_end": candidate_end,
            "candidate_duration_minutes": duration,
            "feasible": False,
            "feasibility_status": REQUIRES_REVIEW_STATUS,
            "feasibility_reason": TRAFFIC_BLOCK_CONFIRMATION_REQUIRED,
        }

    return {
        "planning_task_id": planning_task.id,
        "block_requirement_id": block.id if block is not None else None,
        "available_window_id": available_window.id,
        "candidate_start": candidate_start,
        "candidate_end": candidate_end,
        "candidate_duration_minutes": duration,
        "feasible": True,
        "feasibility_status": FEASIBLE_STATUS,
        "feasibility_reason": FEASIBLE_TEMPORAL_MATCH,
    }


def generate_candidate_windows(db: Session) -> dict[str, int]:
    """Deterministically evaluate every (planning task, available window) pair.

    Idempotent: an existing (planning_task_id, available_window_id) pair is
    skipped and never duplicated.
    """
    stats = {"processed": 0, "created": 0, "skipped": 0,
             "infeasible": 0, "requires_review": 0}

    tasks = db.scalars(
        select(PlanningTask)
        .options(selectinload(PlanningTask.block_requirement))
        .order_by(PlanningTask.id)
    ).all()
    windows = db.scalars(
        select(AvailableWindow).order_by(AvailableWindow.id)
    ).all()

    for task in tasks:
        block = task.block_requirement
        for window in windows:
            stats["processed"] += 1

            existing = db.scalar(
                select(CandidateBlockWindow).where(
                    CandidateBlockWindow.planning_task_id == task.id,
                    CandidateBlockWindow.available_window_id == window.id,
                )
            )
            if existing is not None:
                stats["skipped"] += 1
                continue

            values = evaluate_candidate(task, window, block)
            db.add(CandidateBlockWindow(**values))
            stats["created"] += 1
            if values["feasibility_status"] == INFEASIBLE_STATUS:
                stats["infeasible"] += 1
            elif values["feasibility_status"] == REQUIRES_REVIEW_STATUS:
                stats["requires_review"] += 1

    db.commit()
    return stats


def get_or_evaluate_candidate(
    db: Session, planning_task_id: int, available_window_id: int
) -> dict:
    """Return the stored candidate if present, otherwise evaluate deterministically."""
    task = db.get(PlanningTask, planning_task_id)
    if task is None:
        return {"error": "Planning task not found"}
    window = db.get(AvailableWindow, available_window_id)
    if window is None:
        return {"error": "Available window not found"}

    existing = db.scalar(
        select(CandidateBlockWindow).where(
            CandidateBlockWindow.planning_task_id == planning_task_id,
            CandidateBlockWindow.available_window_id == available_window_id,
        )
    )
    if existing is not None:
        return {
            "planning_task_id": existing.planning_task_id,
            "block_requirement_id": existing.block_requirement_id,
            "available_window_id": existing.available_window_id,
            "candidate_start": existing.candidate_start,
            "candidate_end": existing.candidate_end,
            "candidate_duration_minutes": existing.candidate_duration_minutes,
            "feasible": existing.feasible,
            "feasibility_status": existing.feasibility_status,
            "feasibility_reason": existing.feasibility_reason,
            "existing_candidate_id": existing.id,
        }

    values = evaluate_candidate(task, window, task.block_requirement)
    return {**values, "existing_candidate_id": None}