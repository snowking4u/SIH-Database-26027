"""STEP 10 deterministic plan validation service.

This module performs ONLY deterministic checks against stored data. It does
NOT optimize, rank, score, predict, select a best plan, or approve anything.
A human ``controller_decision`` remains the only source of approval.

The validator returns an explicit list of result dicts, each with a
``validation_type``, ``validation_status`` (PASSED / FAILED / WARNING) and a
``validation_message``. Callers may persist them through
:func:`store_plan_validations`.

Power/traffic rule: a ``power_block_required`` / ``traffic_block_required``
flag does NOT mean the block/authorization actually exists. Since no
authoritative confirmation is stored, both produce WARNING codes
``POWER_BLOCK_CONFIRMATION_REQUIRED`` / ``TRAFFIC_BLOCK_CONFIRMATION_REQUIRED``.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.available_window import AvailableWindow
from app.models.block_plan import BlockPlan
from app.models.block_plan_task import BlockPlanTask
from app.models.candidate_block_window import CandidateBlockWindow
from app.models.plan_validation import PlanValidation
from app.models.planning_task import PlanningTask
from app.models.task_dependency import TaskDependency
from app.models.task_resource import TaskResource

PASSED = "PASSED"
FAILED = "FAILED"
WARNING = "WARNING"

VALIDATOR_VERSION = "STEP10-DETERMINISTIC-1.0"


def _result(validation_type, validation_status, validation_message):
    return {
        "validation_type": validation_type,
        "validation_status": validation_status,
        "validation_message": validation_message,
    }


def validate_block_plan(db: Session, block_plan_id: int) -> list[dict]:
    """Run deterministic validation for a block plan.

    Raises ``ValueError`` when the block plan does not exist.
    """
    plan = db.get(BlockPlan, block_plan_id)
    if plan is None:
        raise ValueError("Block plan not found")

    results: list[dict] = []

    plan_tasks = db.scalars(
        select(BlockPlanTask)
        .where(BlockPlanTask.block_plan_id == block_plan_id)
        .order_by(BlockPlanTask.id)
    ).all()
    if not plan_tasks:
        results.append(
            _result("PLAN_COMPLETENESS", FAILED, "BLOCK_PLAN_HAS_NO_TASKS")
        )

    planning_task_ids = {pt.planning_task_id for pt in plan_tasks}
    planning_tasks = {
        pt.id: pt
        for pt in db.scalars(
            select(PlanningTask).where(PlanningTask.id.in_(planning_task_ids))
        ).all()
    }
    task_resources = {
        row.planning_task_id
        for row in db.scalars(
            select(TaskResource).where(
                TaskResource.planning_task_id.in_(planning_task_ids)
            )
        ).all()
    }
    dependencies = db.scalars(
        select(TaskDependency).where(
            TaskDependency.predecessor_task_id.in_(planning_task_ids),
            TaskDependency.successor_task_id.in_(planning_task_ids),
        )
    ).all()

    intervals: list[tuple] = []

    for plan_task in plan_tasks:
        planning_task = planning_tasks.get(plan_task.planning_task_id)

        if plan_task.planned_start >= plan_task.planned_end:
            results.append(
                _result("DURATION", FAILED, "PLANNED_START_NOT_BEFORE_END")
            )
        if plan_task.planned_duration_minutes <= 0:
            results.append(
                _result("DURATION", FAILED, "PLANNED_DURATION_NOT_POSITIVE")
            )
        if (
            plan_task.planned_start < plan_task.planned_end
            and plan_task.planned_duration_minutes > 0
        ):
            results.append(
                _result("DURATION", PASSED, "PLANNED_DURATION_VALID")
            )

        if planning_task is None:
            results.append(
                _result(
                    "PLAN_COMPLETENESS",
                    FAILED,
                    f"PLANNING_TASK_NOT_FOUND:{plan_task.planning_task_id}",
                )
            )
            continue

        if (
            plan_task.planned_start < plan.planning_horizon_start
            or plan_task.planned_end > plan.planning_horizon_end
        ):
            results.append(
                _result(
                    "TIME_CONFLICT",
                    FAILED,
                    f"PLANNED_TASK_OUTSIDE_PLAN_HORIZON:{planning_task.id}",
                )
            )

        station = None
        line = None
        candidate = None
        if plan_task.candidate_block_window_id is not None:
            candidate = db.get(
                CandidateBlockWindow, plan_task.candidate_block_window_id
            )
            if candidate is None:
                results.append(
                    _result(
                        "WINDOW_FIT",
                        FAILED,
                        f"CANDIDATE_WINDOW_NOT_FOUND:{plan_task.candidate_block_window_id}",
                    )
                )
            else:
                fits = (
                    plan_task.planned_start >= candidate.candidate_start
                    and plan_task.planned_end <= candidate.candidate_end
                )
                results.append(
                    _result(
                        "WINDOW_FIT",
                        PASSED if fits else FAILED,
                        "PLANNED_TASK_FITS_CANDIDATE_WINDOW"
                        if fits
                        else f"PLANNED_TASK_OUTSIDE_CANDIDATE_WINDOW:{planning_task.id}",
                    )
                )
                available_window = db.get(
                    AvailableWindow, candidate.available_window_id
                )
                if available_window is not None:
                    station = available_window.station_code
                    line = available_window.line_number
                    if (
                        planning_task.location_code
                        and available_window.station_code
                        and planning_task.location_code
                        != available_window.station_code
                    ):
                        results.append(
                            _result(
                                "LOCATION",
                                FAILED,
                                f"TASK_LOCATION_MISMATCH_AVAILABLE_WINDOW:{planning_task.id}",
                            )
                        )
                    block = planning_task.block_requirement
                    if (
                        block is not None
                        and block.line_number
                        and available_window.line_number
                        and block.line_number != available_window.line_number
                    ):
                        results.append(
                            _result(
                                "LINE",
                                FAILED,
                                f"TASK_LINE_MISMATCH_AVAILABLE_WINDOW:{planning_task.id}",
                            )
                        )

        block = planning_task.block_requirement
        if block is not None:
            if block.power_block_required:
                results.append(
                    _result(
                        "POWER_BLOCK",
                        WARNING,
                        f"POWER_BLOCK_CONFIRMATION_REQUIRED:{planning_task.id}",
                    )
                )
            if block.traffic_block_required:
                results.append(
                    _result(
                        "TRAFFIC_BLOCK",
                        WARNING,
                        f"TRAFFIC_BLOCK_CONFIRMATION_REQUIRED:{planning_task.id}",
                    )
                )

        if planning_task.id in task_resources:
            results.append(
                _result(
                    "RESOURCE",
                    PASSED,
                    f"RESOURCE_RELATIONSHIP_PRESENT:{planning_task.id}",
                )
            )
        else:
            results.append(
                _result(
                    "RESOURCE",
                    WARNING,
                    f"NO_RESOURCE_RELATIONSHIP_RECORDED:{planning_task.id}",
                )
            )

        if station is not None and line is not None:
            intervals.append(
                (
                    station,
                    line,
                    plan_task.planned_start,
                    plan_task.planned_end,
                    planning_task.id,
                )
            )

    seen_conflicts: set[tuple] = set()
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            station_i, line_i, start_i, end_i, task_i = intervals[i]
            station_j, line_j, start_j, end_j, task_j = intervals[j]
            if station_i != station_j or line_i != line_j:
                continue
            if start_i < end_j and start_j < end_i:
                key = tuple(sorted((task_i, task_j)))
                if key in seen_conflicts:
                    continue
                seen_conflicts.add(key)
                results.append(
                    _result(
                        "TIME_CONFLICT",
                        FAILED,
                        f"OVERLAPPING_PLAN_TASKS_ON_SAME_STATION_LINE:{task_i},{task_j}",
                    )
                )

    plan_task_by_planning_id = {
        pt.planning_task_id: pt for pt in plan_tasks
    }
    for dependency in dependencies:
        predecessor = plan_task_by_planning_id.get(
            dependency.predecessor_task_id
        )
        successor = plan_task_by_planning_id.get(dependency.successor_task_id)
        if predecessor is None or successor is None:
            continue
        if dependency.dependency_type == "FINISH_TO_START":
            required_start = predecessor.planned_end + timedelta(
                minutes=dependency.lag_minutes
            )
            if successor.planned_start < required_start:
                results.append(
                    _result(
                        "DEPENDENCY",
                        FAILED,
                        f"DEPENDENCY_ORDER_VIOLATION:"
                        f"{dependency.predecessor_task_id},"
                        f"{dependency.successor_task_id}",
                    )
                )
            else:
                results.append(
                    _result(
                        "DEPENDENCY",
                        PASSED,
                        f"DEPENDENCY_ORDER_SATISFIED:"
                        f"{dependency.predecessor_task_id},"
                        f"{dependency.successor_task_id}",
                    )
                )
        else:
            results.append(
                _result(
                    "DEPENDENCY",
                    WARNING,
                    f"DEPENDENCY_TYPE_NOT_EVALUATED:{dependency.dependency_type}",
                )
            )

    return results


def store_plan_validations(
    db: Session, block_plan_id: int
) -> list[PlanValidation]:
    """Persist deterministic validation results for a block plan.

    Does NOT change the block plan status and does NOT approve the plan.
    """
    results = validate_block_plan(db, block_plan_id)
    records = [
        PlanValidation(
            block_plan_id=block_plan_id,
            validation_type=result["validation_type"],
            validation_status=result["validation_status"],
            validation_message=result["validation_message"],
            validator_version=VALIDATOR_VERSION,
        )
        for result in results
    ]
    db.add_all(records)
    db.commit()
    for record in records:
        db.refresh(record)
    return records
