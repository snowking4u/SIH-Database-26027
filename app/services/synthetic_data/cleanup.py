"""STEP 11 cleanup: marker-based, FK-safe synthetic-data removal.

Only rows carrying the synthetic marker (or ``SYN-*`` identifiers) are ever
deleted. Id sets are materialized into Python collections first so the
deletes are legal on both PostgreSQL and the SQLite test harness. Nothing is
truncated and the seeded TMS/TDMS/SMMS/COA source systems are never touched.
"""

from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AssetMaster,
    AssetParameter,
    AvailableWindow,
    BlockRequirement,
    CandidateBlockWindow,
    DefectFailure,
    LineOccupancy,
    LocationMaster,
    MaintenanceRequirement,
    OperationalEvent,
    OptimizationInput,
    OptimizationOutput,
    OptimizationRun,
    PlanningConstraint,
    PlanningResource,
    PlanningTask,
    SMMSAlert,
    SMMSInspection,
    SMMSMaintenance,
    TDMSFailure,
    TDMSInspection,
    TDMSMaintenance,
    TMSDefect,
    TMSInspection,
    TMSMaintenance,
    TaskDependency,
    TaskResource,
    Train,
    TrainMovement,
    TrainSchedule,
)

from .config import MARKER


def _ids(result) -> set[int]:
    return set(result.scalars().all())


def cleanup_synthetic(db: Session) -> dict[str, int]:
    """Delete synthetic STEP 11 rows in dependency-safe order."""
    marker = f"%{MARKER}%"

    syn_asset_ids = _ids(
        db.execute(select(AssetMaster.id).where(AssetMaster.source_asset_id.like("SYN-%")))
    )
    br_ids = _ids(
        db.execute(
            select(BlockRequirement.id).where(BlockRequirement.remarks.like(marker))
        )
    )
    mr_ids = _ids(
        db.execute(
            select(MaintenanceRequirement.id).where(
                MaintenanceRequirement.description.like(marker)
            )
        )
    )
    task_ids = _ids(
        db.execute(
            select(PlanningTask.id).where(
                or_(
                    PlanningTask.description.like(marker),
                    PlanningTask.maintenance_requirement_id.in_(mr_ids),
                )
            )
        )
    )
    cand_ids = _ids(
        db.execute(
            select(CandidateBlockWindow.id).where(
                or_(
                    CandidateBlockWindow.planning_task_id.in_(task_ids),
                    CandidateBlockWindow.block_requirement_id.in_(br_ids),
                )
            )
        )
    )
    opt_run_ids = _ids(
        db.execute(
            select(OptimizationRun.id).where(OptimizationRun.run_code.like("SYN-OPT-%"))
        )
    )
    resource_ids = _ids(
        db.execute(
            select(PlanningResource.id).where(
                PlanningResource.resource_code.like("SYN-RES-%")
            )
        )
    )
    dep_ids = _ids(
        db.execute(
            select(TaskDependency.id).where(TaskDependency.description.like(marker))
        )
    )
    constraint_ids = _ids(
        db.execute(
            select(PlanningConstraint.id).where(
                PlanningConstraint.planning_task_id.in_(task_ids)
            )
        )
    )

    tracking: list[tuple[str, int]] = []

    def run(name: str, stmt) -> int:
        result = db.execute(stmt)
        tracking.append((name, result.rowcount or 0))
        return result.rowcount or 0

    # 1-3. Optimization layer (references candidates/tasks/resources/deps).
    run(
        "optimization_output",
        delete(OptimizationOutput).where(
            or_(
                OptimizationOutput.optimization_run_id.in_(opt_run_ids),
                OptimizationOutput.planning_task_id.in_(task_ids),
                OptimizationOutput.candidate_block_window_id.in_(cand_ids),
            )
        ),
    )
    run(
        "optimization_input",
        delete(OptimizationInput).where(
            or_(
                OptimizationInput.optimization_run_id.in_(opt_run_ids),
                OptimizationInput.planning_task_id.in_(task_ids),
                OptimizationInput.candidate_block_window_id.in_(cand_ids),
                OptimizationInput.planning_resource_id.in_(resource_ids),
                OptimizationInput.task_dependency_id.in_(dep_ids),
                OptimizationInput.planning_constraint_id.in_(constraint_ids),
            )
        ),
    )
    run(
        "optimization_run",
        delete(OptimizationRun).where(OptimizationRun.id.in_(opt_run_ids)),
    )

    # 4. Candidate windows.
    run(
        "candidate_block_window",
        delete(CandidateBlockWindow).where(
            or_(
                CandidateBlockWindow.planning_task_id.in_(task_ids),
                CandidateBlockWindow.block_requirement_id.in_(br_ids),
            )
        ),
    )

    # 5-8. Planning layer.
    run(
        "task_dependency",
        delete(TaskDependency).where(
            or_(
                TaskDependency.predecessor_task_id.in_(task_ids),
                TaskDependency.successor_task_id.in_(task_ids),
            )
        ),
    )
    run(
        "task_resource",
        delete(TaskResource).where(TaskResource.planning_task_id.in_(task_ids)),
    )
    run(
        "planning_constraint",
        delete(PlanningConstraint).where(PlanningConstraint.id.in_(constraint_ids)),
    )
    run("planning_task", delete(PlanningTask).where(PlanningTask.id.in_(task_ids)))
    run("block_requirement", delete(BlockRequirement).where(BlockRequirement.id.in_(br_ids)))

    # 9-10. Unified layer. Defect failures are matched by synthetic asset
    # because the SMMS normalizer re-writes remarks without the marker.
    run(
        "maintenance_requirement",
        delete(MaintenanceRequirement).where(MaintenanceRequirement.id.in_(mr_ids)),
    )
    run(
        "defect_failure",
        delete(DefectFailure).where(DefectFailure.asset_id.in_(syn_asset_ids)),
    )

    # 11. Resources.
    run(
        "planning_resource",
        delete(PlanningResource).where(PlanningResource.id.in_(resource_ids)),
    )

    # 12. Derived windows tagged synthetic.
    run(
        "available_window",
        delete(AvailableWindow).where(AvailableWindow.remarks.like(marker)),
    )

    # 13-17. COA source records.
    run(
        "train_schedule",
        delete(TrainSchedule).where(TrainSchedule.source_schedule_id.like("SYN-COA-%")),
    )
    run(
        "train_movement",
        delete(TrainMovement).where(TrainMovement.source_event_id.like("SYN-COA-%")),
    )
    run(
        "line_occupancy",
        delete(LineOccupancy).where(LineOccupancy.source_event_id.like("SYN-COA-%")),
    )
    run(
        "operational_event",
        delete(OperationalEvent).where(OperationalEvent.source_event_id.like("SYN-COA-%")),
    )
    run("train", delete(Train).where(Train.train_id.like("SYN-TRAIN-%")))

    # 18-20. Source systems' synthetic rows (maintenance after defect/alert).
    run(
        "tms_maintenance",
        delete(TMSMaintenance).where(TMSMaintenance.asset_id.in_(syn_asset_ids)),
    )
    run(
        "tdms_maintenance",
        delete(TDMSMaintenance).where(TDMSMaintenance.asset_id.in_(syn_asset_ids)),
    )
    run(
        "smms_maintenance",
        delete(SMMSMaintenance).where(SMMSMaintenance.asset_id.in_(syn_asset_ids)),
    )
    run("tms_defect", delete(TMSDefect).where(TMSDefect.asset_id.in_(syn_asset_ids)))
    run(
        "tdms_failure",
        delete(TDMSFailure).where(TDMSFailure.asset_id.in_(syn_asset_ids)),
    )
    run(
        "smms_alert",
        delete(SMMSAlert).where(SMMSAlert.asset_id.in_(syn_asset_ids)),
    )
    run(
        "tms_inspection",
        delete(TMSInspection).where(TMSInspection.asset_id.in_(syn_asset_ids)),
    )
    run(
        "tdms_inspection",
        delete(TDMSInspection).where(TDMSInspection.asset_id.in_(syn_asset_ids)),
    )
    run(
        "smms_inspection",
        delete(SMMSInspection).where(SMMSInspection.asset_id.in_(syn_asset_ids)),
    )

    # 21-23. Master data.
    run(
        "asset_parameter",
        delete(AssetParameter).where(AssetParameter.asset_id.in_(syn_asset_ids)),
    )
    run(
        "asset_master",
        delete(AssetMaster).where(AssetMaster.source_asset_id.like("SYN-%")),
    )
    run(
        "location_master",
        delete(LocationMaster).where(
            or_(
                LocationMaster.station_code.like("SYN-ST%"),
                LocationMaster.line_code.like("SYN-L%"),
            )
        ),
    )

    db.commit()
    summary = dict(tracking)
    summary["total"] = sum(count for _, count in tracking)
    return summary