"""STEP 11 verification: read-only integrity checks over generated data.

Reports problems; never repairs. On a clean, correctly generated dataset every
check passes except the explicitly documented "edge-case" counts (windows
missing on very-tight templates, tasks without candidates, etc.) which are
reported as information, not failures.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AssetMaster,
    AvailableWindow,
    BlockRequirement,
    CandidateBlockWindow,
    MaintenanceRequirement,
    PlanningTask,
    TaskDependency,
    TaskResource,
    TrainMovement,
    TrainSchedule,
)

from .config import MARKER, SyntheticConfig


def verify_synthetic(db: Session, cfg: SyntheticConfig) -> dict:
    problems: list[str] = []
    info: list[str] = []

    syn_asset_count = (
        db.scalar(
            select(func.count())
            .select_from(AssetMaster)
            .where(AssetMaster.source_asset_id.like("SYN-%"))
        )
        or 0
    )
    if syn_asset_count == 0:
        problems.append("No synthetic assets found; pipeline did not run.")

    windows = db.scalars(
        select(AvailableWindow).where(AvailableWindow.remarks.like(f"%{MARKER}%"))
    ).all()
    for window in windows:
        if window.window_start >= window.window_end:
            problems.append(
                f"available_window {window.id} has empty/negative interval."
            )
        if window.duration_minutes is None or window.duration_minutes <= 0:
            problems.append(
                f"available_window {window.id} has invalid duration."
            )
        if window.window_status != "AVAILABLE":
            problems.append(f"available_window {window.id} status not AVAILABLE.")

    tasks = db.scalars(select(PlanningTask)).all()
    task_ids = {t.id for t in tasks}
    mr_ids = {
        db.get(MaintenanceRequirement, t.maintenance_requirement_id).id
        for t in tasks
        if db.get(MaintenanceRequirement, t.maintenance_requirement_id) is not None
    }
    synthetic_mr_ids = set(
        db.scalars(
            select(MaintenanceRequirement.id).where(
                MaintenanceRequirement.description.like(f"%{MARKER}%")
            )
        ).all()
    )
    missing_mr = mr_ids - synthetic_mr_ids
    if missing_mr:
        problems.append(
            f"{len(missing_mr)} planning tasks reference non-synthetic requirements."
        )

    task_resources = db.scalars(
        select(TaskResource)
    ).all()
    for tr in task_resources:
        if tr.planning_task_id not in task_ids:
            problems.append(
                f"task_resource {tr.id} references a missing planning task."
            )

    deps = db.scalars(select(TaskDependency)).all()
    for dep in deps:
        if dep.predecessor_task_id not in task_ids:
            problems.append(
                f"task_dependency {dep.id} references a missing predecessor."
            )
        if dep.successor_task_id not in task_ids:
            problems.append(
                f"task_dependency {dep.id} references a missing successor."
            )
        if dep.predecessor_task_id == dep.successor_task_id:
            problems.append(f"task_dependency {dep.id} is self-referential.")

    candidates = db.scalars(
        select(CandidateBlockWindow).where(
            CandidateBlockWindow.planning_task_id.in_(
                select(PlanningTask.id).where(
                    PlanningTask.maintenance_requirement_id.in_(
                        select(MaintenanceRequirement.id).where(
                            MaintenanceRequirement.description.like(f"%{MARKER}%")
                        )
                    )
                )
            )
        )
    ).all()
    infeasible = len(
        [c for c in candidates if c.feasibility_status in ("INFEASIBLE", "REQUIRES_REVIEW")]
    )
    feasible = len([c for c in candidates if c.feasibility_status == "FEASIBLE"])
    info.append(
        f"Candidate windows: {len(candidates)} total "
        f"({feasible} feasible, {infeasible} infeasible/review)."
    )

    brs = db.scalars(
        select(BlockRequirement).where(
            BlockRequirement.remarks.like(f"%{MARKER}%")
        )
    ).all()
    for br in brs:
        if br.station_code and br.line_number:
            pass
        else:
            info.append(
                f"block_requirement {br.id} intentionally lacks location context."
            )

    pass_marker = f"{MARKER}"
    movable = db.scalars(
        select(TrainMovement).where(TrainMovement.source_event_id.like("SYN-COA-%"))
    ).all()
    schedules = db.scalars(
        select(TrainSchedule).where(TrainSchedule.source_schedule_id.like("SYN-COA-%"))
    ).all()
    for sched in schedules:
        if sched.scheduled_arrival and sched.scheduled_departure:
            if sched.scheduled_arrival >= sched.scheduled_departure:
                problems.append(
                    f"train_schedule {sched.id} has arrival >= departure."
                )
        elif not (sched.scheduled_arrival is None and sched.scheduled_departure is None):
            info.append(
                f"train_schedule {sched.id} has partial timetable information."
            )

    for mov in movable:
        if not mov.station_code or not mov.line_number:
            problems.append(
                f"train_movement {mov.id} is missing station/line context."
            )

    return {
        "pass": len(problems) == 0,
        "problems": problems,
        "info": info,
        "counts": {
            "synthetic_assets": syn_asset_count,
            "available_windows": len(windows),
            "planning_tasks": len(tasks),
            "block_requirements": len(brs),
            "candidate_windows": {
                "total": len(candidates),
                "feasible": feasible,
                "infeasible_or_review": infeasible,
            },
            "task_resources": len(task_resources),
            "task_dependencies": len(deps),
        },
        "marker": pass_marker,
    }