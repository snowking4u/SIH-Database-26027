"""Deterministic planning foundation generation.

Purpose
-------
STEP 8 planning foundation. Unified maintenance/block requirements are
converted into planning-ready inputs:

- ``planning_task``          <- one per maintenance_requirement
- ``planning_constraint``    <- deterministic constraints from block_requirement

These are structured planning inputs only. No AI/ML, no optimization, no
duration invention, no window matching, no final block selection.

Provenance
----------
Every ``planning_task`` keeps ``maintenance_requirement_id`` (and optionally
``block_requirement_id``). Traceability flows through the unified layer:

planning_task -> maintenance_requirement ->
    (source_system + source_record_type + source_record_id) -> TMS/TDMS/SMMS

planning_task -> asset_master

planning_task -> block_requirement -> maintenance_requirement

Idempotency
-----------
- ``planning_task`` has UNIQUE(maintenance_requirement_id): running task
  generation twice never creates duplicate tasks; existing tasks are skipped.
- ``planning_constraint`` uses deterministic (planning_task_id,
  constraint_type, constraint_value) upsert-or-skip.

Duration semantics
------------------
``duration_minutes`` is the known/source-derived duration. It is preferred from
``maintenance_requirement.required_duration_minutes``; when absent the linked
``block_requirement.required_duration_minutes`` (also source-derived) is used.
If no known duration exists the task is skipped - no optimized/invented
duration is ever produced.

Time semantics
--------------
``earliest_start`` / ``latest_end`` are preserved from
``block_requirement.earliest_start`` / ``latest_end`` (source-derived
requirement data). ``maintenance_requirement.planned_date`` is source-captured
information only and is NOT converted into a task window automatically;
this avoids inventing time bounds.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.block_requirement import BlockRequirement
from app.models.maintenance_requirement import MaintenanceRequirement
from app.models.planning_constraint import PlanningConstraint
from app.models.planning_task import PlanningTask

TASK_STATUS = "OPEN"

CONSTRAINT_SOURCE = "BLOCK_REQUIREMENT"


def _choose_block_requirement(
    db: Session, maintenance_requirement_id: int
) -> BlockRequirement | None:
    return db.scalar(
        select(BlockRequirement)
        .where(BlockRequirement.maintenance_requirement_id == maintenance_requirement_id)
        .order_by(BlockRequirement.id)
        .limit(1)
    )


def _valid_duration(value: int | None) -> bool:
    return value is not None and value > 0


def generate_planning_tasks(db: Session) -> dict[str, int]:
    """Create planning tasks for maintenance requirements that lack one.

    Deterministic and idempotent. Never invents durations or AI values.
    """
    stats = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}

    requirements = db.scalars(
        select(MaintenanceRequirement).order_by(MaintenanceRequirement.id)
    ).all()
    for requirement in requirements:
        stats["processed"] += 1
        existing = db.scalar(
            select(PlanningTask).where(
                PlanningTask.maintenance_requirement_id == requirement.id
            )
        )
        if existing is not None:
            stats["skipped"] += 1
            continue

        block = _choose_block_requirement(db, requirement.id)

        duration = requirement.required_duration_minutes
        if not _valid_duration(duration) and block is not None:
            duration = block.required_duration_minutes
        if not _valid_duration(duration):
            stats["skipped"] += 1
            continue

        task = PlanningTask(
            maintenance_requirement_id=requirement.id,
            block_requirement_id=block.id if block is not None else None,
            asset_id=requirement.asset_id,
            task_code=f"PT-{requirement.id:06d}",
            task_type=requirement.maintenance_type,
            description=requirement.description,
            status=TASK_STATUS,
            earliest_start=block.earliest_start if block is not None else None,
            latest_end=block.latest_end if block is not None else None,
            duration_minutes=duration,
            location_code=block.station_code if block is not None else None,
        )
        db.add(task)
        stats["created"] += 1

    db.commit()
    return stats


def _upsert_constraint(
    db: Session,
    *,
    planning_task_id: int,
    constraint_type: str,
    constraint_value: str,
    hard_constraint: bool,
    effective_start,
    effective_end,
    description: str | None,
    source: str | None,
):
    existing = db.scalar(
        select(PlanningConstraint).where(
            PlanningConstraint.planning_task_id == planning_task_id,
            PlanningConstraint.constraint_type == constraint_type,
            PlanningConstraint.constraint_value == constraint_value,
        )
    )
    values = {
        "planning_task_id": planning_task_id,
        "constraint_type": constraint_type,
        "constraint_value": constraint_value,
        "hard_constraint": hard_constraint,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "description": description,
        "source": source,
    }
    if existing is None:
        db.add(PlanningConstraint(**values))
        return "created"
    changed = any(getattr(existing, key) != value for key, value in values.items())
    if changed:
        for key, value in values.items():
            setattr(existing, key, value)
        return "updated"
    return "skipped"


def _iso(value) -> str:
    return value.isoformat() if value is not None else ""


def generate_planning_constraints(db: Session) -> dict[str, int]:
    """Create deterministic constraint records from block requirements.

    Only converts existing requirement data into explicit constraint records.
    No constraints are invented where source data does not provide them.
    """
    stats = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}

    tasks = db.scalars(
        select(PlanningTask)
        .options(selectinload(PlanningTask.block_requirement))
        .order_by(PlanningTask.id)
    ).all()
    for task in tasks:
        stats["processed"] += 1
        block = task.block_requirement
        if block is None:
            stats["skipped"] += 1
            continue

        candidates: list[dict] = []
        if block.required_duration_minutes is not None:
            candidates.append({
                "constraint_type": "DURATION",
                "constraint_value": str(block.required_duration_minutes),
                "description": (
                    f"Required duration of {block.required_duration_minutes} "
                    "minutes derived from block requirement"
                ),
            })
        if block.earliest_start is not None or block.latest_end is not None:
            candidates.append({
                "constraint_type": "TIME_WINDOW",
                "constraint_value": f"{_iso(block.earliest_start)}|{_iso(block.latest_end)}",
                "description": (
                    "Earliest start / latest end window derived from block "
                    "requirement"
                ),
            })
        if block.station_code:
            candidates.append({
                "constraint_type": "LOCATION",
                "constraint_value": block.station_code,
                "description": f"Location constraint: station {block.station_code}",
            })
        if block.line_number:
            candidates.append({
                "constraint_type": "LINE",
                "constraint_value": block.line_number,
                "description": f"Line constraint: {block.line_number}",
            })
        if block.power_block_required:
            candidates.append({
                "constraint_type": "POWER_BLOCK",
                "constraint_value": "TRUE",
                "description": "Power block access required",
            })
        if block.traffic_block_required:
            candidates.append({
                "constraint_type": "TRAFFIC_BLOCK",
                "constraint_value": "TRUE",
                "description": "Traffic block access required",
            })

        if not candidates:
            stats["skipped"] += 1
            continue

        for candidate in candidates:
            action = _upsert_constraint(
                db,
                planning_task_id=task.id,
                constraint_type=candidate["constraint_type"],
                constraint_value=candidate["constraint_value"],
                hard_constraint=True,
                effective_start=block.earliest_start,
                effective_end=block.latest_end,
                description=candidate["description"],
                source=CONSTRAINT_SOURCE,
            )
            stats[action] += 1

    db.commit()
    return stats