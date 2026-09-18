"""STEP 11 dataset orchestrator: runs the whole synthetic pipeline in order.

Pipeline (deterministic, service-driven, no AI/optimization):

1. master data      -> locations, assets, parameters
2. COA/CTC source   -> trains, schedules, movements, occupancy, events
3. derive windows   -> existing ``derive_available_windows`` service, then tag
4. TMS/TDMS/SMMS    -> inspections, defects/failures/alerts, maintenance
5. normalize        -> existing unified-maintenance services
6. block reqs       -> UnifiedGenerator (source-derived, gap targeting)
7. planning         -> existing planning-foundation services
8. resources/deps   -> PlanningGenerator
9. candidates       -> existing candidate-window service
10. (optional) opt   -> synthetic placeholder run (inputs only, no outputs)

The orchestrator never invents railway values; every number traces back to the
scale profile / scenario configuration.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AssetMaster,
    AssetParameter,
    AvailableWindow,
    BlockRequirement,
    BlockPlan,
    BlockPlanTask,
    CandidateBlockWindow,
    ControllerDecision,
    DefectFailure,
    ExecutionOutcome,
    LineOccupancy,
    LocationMaster,
    MaintenanceRequirement,
    OperationalEvent,
    OptimizationInput,
    OptimizationOutput,
    OptimizationRun,
    PlanValidation,
    PlanningConstraint,
    PlanningResource,
    PlanningTask,
    SourceSystem,
    TaskDependency,
    TaskResource,
    Train,
    TrainMovement,
    TrainSchedule,
    TMSInspection,
    TMSDefect,
    TMSMaintenance,
    TDMSInspection,
    TDMSFailure,
    TDMSMaintenance,
    SMMSInspection,
    SMMSAlert,
    SMMSMaintenance,
)
from app.services.available_window_derivation import derive_available_windows
from app.services.candidate_window import generate_candidate_windows
from app.services.planning_foundation import (
    generate_planning_constraints,
    generate_planning_tasks,
)
from app.services.unified_maintenance import (
    normalize_smms,
    normalize_tdms,
    normalize_tms,
)

from .candidate_generator import generate_candidates
from .coa_generator import CoaData, CoaGenerator
from .config import MARKER, SyntheticConfig
from .master_generator import MasterGenerator
from .optimization_generator import generate_optimization_placeholder
from .planning_generator import PlanningGenerator
from .smms_generator import SmmsGenerator
from .tdms_generator import TdmsGenerator
from .tms_generator import TMSGenerator
from .unified_generator import UnifiedGenerator

COUNT_MODELS = [
    ("location_master", LocationMaster),
    ("asset_master", AssetMaster),
    ("asset_parameter", AssetParameter),
    ("source_system", SourceSystem),
    ("train", Train),
    ("train_schedule", TrainSchedule),
    ("train_movement", TrainMovement),
    ("line_occupancy", LineOccupancy),
    ("operational_event", OperationalEvent),
    ("available_window", AvailableWindow),
    ("tms_inspection", TMSInspection),
    ("tms_defect", TMSDefect),
    ("tms_maintenance", TMSMaintenance),
    ("tdms_inspection", TDMSInspection),
    ("tdms_failure", TDMSFailure),
    ("tdms_maintenance", TDMSMaintenance),
    ("smms_inspection", SMMSInspection),
    ("smms_alert", SMMSAlert),
    ("smms_maintenance", SMMSMaintenance),
    ("defect_failure", DefectFailure),
    ("maintenance_requirement", MaintenanceRequirement),
    ("block_requirement", BlockRequirement),
    ("planning_task", PlanningTask),
    ("planning_constraint", PlanningConstraint),
    ("planning_resource", PlanningResource),
    ("task_resource", TaskResource),
    ("task_dependency", TaskDependency),
    ("candidate_block_window", CandidateBlockWindow),
    ("optimization_run", OptimizationRun),
    ("optimization_input", OptimizationInput),
    ("optimization_output", OptimizationOutput),
    ("block_plan", BlockPlan),
    ("block_plan_task", BlockPlanTask),
    ("plan_validation", PlanValidation),
    ("controller_decision", ControllerDecision),
    ("execution_outcome", ExecutionOutcome),
]


def table_counts(db: Session) -> dict[str, int]:
    result: dict[str, int] = {}
    for name, model in COUNT_MODELS:
        result[name] = db.scalar(select(func.count()).select_from(model)) or 0
    return result


def _tag_windows(db: Session) -> int:
    """Idempotently tag derived windows with the synthetic marker."""
    tagged = 0
    windows = db.scalars(
        select(AvailableWindow).where(
            AvailableWindow.remarks.isnot(None),
            ~AvailableWindow.remarks.like(f"%{MARKER}%"),
        )
    ).all()
    for window in windows:
        window.remarks = f"{window.remarks} [{MARKER}]"
        tagged += 1
    db.commit()
    return tagged


def _build_asset_map(db: Session) -> dict[int, tuple[str, str]]:
    rows = db.execute(
        select(AssetMaster.id, LocationMaster.station_code, LocationMaster.line_code)
        .join(LocationMaster, AssetMaster.location_id == LocationMaster.id)
        .where(AssetMaster.source_asset_id.like("SYN-%"))
    ).all()
    return {asset_id: (station_code, line_code) for asset_id, station_code, line_code in rows}


def _dataset_id(cfg: SyntheticConfig) -> str:
    return f"SYN-STEP11-{cfg.start_date.strftime('%Y%m%d')}-0001"


def run_pipeline(db: Session, cfg: SyntheticConfig) -> dict:
    """Execute the deterministic pipeline against an existing session."""
    dataset_id = _dataset_id(cfg)

    master = MasterGenerator(db, cfg)
    master_stats = master.generate()
    asset_map = _build_asset_map(db)
    synth_assets = db.scalars(
        select(AssetMaster)
        .where(AssetMaster.source_asset_id.like("SYN-%"))
        .order_by(AssetMaster.id)
    ).all()
    from .master_generator import AssetInfo

    def _info(asset: AssetMaster) -> AssetInfo:
        station, line = asset_map[asset.id]
        # Only fields needed by the source generators are populated here.
        return AssetInfo(
            id=asset.id,
            station_idx=0,
            line_idx=0,
            station_code=station,
            line_number=line,
            asset_type=asset.asset_type,
            source_system_code="",
            installation_date=asset.installation_date or cfg.start_date,
            status=asset.status or "IN_SERVICE",
        )

    assets = [_info(a) for a in synth_assets]

    coa_gen = CoaGenerator(db, cfg)
    coa_data: CoaData = coa_gen.generate()
    windows_created = len(derive_available_windows(db))
    tagged = _tag_windows(db)

    tms = TMSGenerator(db, cfg, assets).generate()
    tdms = TdmsGenerator(db, cfg, assets).generate()
    smms = SmmsGenerator(db, cfg, assets).generate()

    normalized_tms = normalize_tms(db)
    normalized_tdms = normalize_tdms(db)
    normalized_smms = normalize_smms(db)

    unified = UnifiedGenerator(db, cfg, coa_data, asset_map).generate()

    planning = generate_planning_tasks(db)
    constraints = generate_planning_constraints(db)

    planner = PlanningGenerator(db, cfg, cfg.rng)
    planning_stats = planner.generate()
    planning_stats["planning_tasks"] = planning
    planning_stats["constraints"] = constraints

    candidates = generate_candidates(db, cfg)

    optimization_stats = {"run_created": 0, "inputs_created": 0, "skipped_run": 0}
    if cfg.with_optimization:
        optimization_stats = generate_optimization_placeholder(db, cfg, dataset_id)

    counts = table_counts(db)

    manifest = {
        "dataset_id": dataset_id,
        "generator_version": "STEP11-1.0",
        "seed": cfg.seed,
        "scale": cfg.scale,
        "scenario": cfg.scenario,
        "start_date": cfg.start_date.isoformat(),
        "days": cfg.days,
        "batch_size": cfg.batch_size,
        "with_optimization": cfg.with_optimization,
        "generation_timestamp": datetime.now(timezone.utc)
        .replace(tzinfo=None)
        .isoformat(timespec="seconds"),
        "configuration_summary": cfg.configuration_summary(),
        "windows": {
            "derived": windows_created,
            "tagged_as_synthetic": tagged,
        },
        "master_stats": master_stats,
        "source_stats": {"tms": tms, "tdms": tdms, "smms": smms},
        "normalized": {
            "tms": normalized_tms,
            "tdms": normalized_tdms,
            "smms": normalized_smms,
        },
        "block_requirements": unified,
        "planning": planning_stats,
        "candidates": candidates,
        "optimization": optimization_stats,
        "table_counts": counts,
    }

    if cfg.write_manifest and cfg.manifest_path is not None:
        _write_manifest(cfg.manifest_path, manifest)

    return manifest


def _write_manifest(path: Path, manifest: dict) -> None:
    import json

    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)