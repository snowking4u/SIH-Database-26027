"""STEP 11 tests: synthetic railway maintenance/planning dataset generator.

Every test runs against the shared in-memory SQLite harness (StaticPool +
``PRAGMA foreign_keys=ON``). Scale is pinned to ``tiny`` (or explicit tiny-like
config) so full end-to-end pipeline runs stay fast. Determinism and
idempotency are core guarantees and are tested explicitly; LARGE scale is
covered only as configuration / dry-run-proof and never executed.
"""

from __future__ import annotations

import json
import importlib.util
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.database import Base
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
    SourceSystem,
    TDMSFailure,
    TDMSInspection,
    TDMSMaintenance,
    TaskDependency,
    TaskResource,
    TMSDefect,
    TMSInspection,
    TMSMaintenance,
    Train,
    TrainMovement,
    TrainSchedule,
)
from app.services.available_window_derivation import CALCULATION_SOURCE
from app.services.planning_foundation import generate_planning_tasks
from app.services.synthetic_data import (
    MARKER,
    SCALE_PROFILES,
    SCENARIOS,
    VALID_SCENARIOS,
    SyntheticConfig,
    cleanup_synthetic,
    run_pipeline,
    verify_synthetic,
)
from app.services.synthetic_data.random_utils import day_start
from app.services.synthetic_data.master_generator import (
    line_number,
    station_code,
)

start_date = date(2026, 1, 5)


def tiny_cfg(**overrides) -> SyntheticConfig:
    cfg = dict(
        seed=42,
        scale="tiny",
        days=7,
        start_date=start_date,
        scenario="normal",
        batch_size=10,
        write_manifest=False,
    )
    cfg.update(overrides)
    return SyntheticConfig(**cfg)


def seed_sources(db: Session) -> None:
    db.add_all(
        [
            SourceSystem(system_code="TMS", system_name="Test TMS"),
            SourceSystem(system_code="TDMS", system_name="Test TDMS"),
            SourceSystem(system_code="SMMS", system_name="Test SMMS"),
            SourceSystem(system_code="COA", system_name="Test COA"),
        ]
    )
    db.commit()


@pytest.fixture()
def seeded(db_session):
    seed_sources(db_session)
    return db_session


def make_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False,
        class_=Session,
    )
    return engine, SessionLocal


def run_tiny(db: Session, **overrides) -> dict:
    return run_pipeline(db, tiny_cfg(**overrides))


# --------------------------------------------------------------------------- #
# 1. Configuration
# --------------------------------------------------------------------------- #
def test_unknown_scale_and_scenario_rejected():
    with pytest.raises(ValueError):
        tiny_cfg(scale="gigantic")
    with pytest.raises(ValueError):
        tiny_cfg(scenario="mystery")
    with pytest.raises(ValueError):
        tiny_cfg(days=0)
    with pytest.raises(ValueError):
        tiny_cfg(seed=-1)


def test_scale_profile_targets():
    cfg = tiny_cfg()
    assert cfg.station_count == SCALE_PROFILES["tiny"].stations
    assert cfg.asset_count == 10
    assert cfg.train_count == 10
    assert cfg.inspection_count == 30
    assert cfg.defect_count == 10
    assert cfg.maintenance_count == 10
    for key in SCALE_PROFILES:
        assert SyntheticConfig(seed=1, scale=key, days=7,
                               start_date=start_date, scenario="normal",
                               batch_size=100).station_count >= 1


def test_scenario_multipliers_and_valid_set():
    assert set(SCENARIOS) == set(VALID_SCENARIOS)
    normal = tiny_cfg().scenario_config
    assert normal.defect_multiplier == 1.0
    high = tiny_cfg(scenario="high_defect_load").scenario_config
    assert high.defect_multiplier == 2.6
    assert high.severe_ratio == 0.6
    cfg = tiny_cfg(scenario="high_defect_load")
    assert cfg.inspection_count == round(30 * high.inspection_multiplier)
    assert cfg.defect_count == round(10 * high.defect_multiplier)
    assert cfg.maintenance_count == max(10, cfg.defect_count)


def test_wide_scenario_volume_properties():
    base = tiny_cfg(scenario="window_shortage")
    assert base.window_template() != tiny_cfg().window_template()
    scarce = tiny_cfg(scenario="resource_shortage")
    assert scarce.resource_count <= tiny_cfg().resource_count
    dense = tiny_cfg(scenario="dependency_conflict")
    assert dense.dependency_rate >= 1.0


# --------------------------------------------------------------------------- #
# 2. Determinism
# --------------------------------------------------------------------------- #
def test_same_seed_is_reproducible():
    manifest_a = {}
    engine_a, SessionLocalA = make_env()
    with SessionLocalA() as db:
        seed_sources(db)
        manifest_a["counts"] = run_tiny(db)["table_counts"]

    engine_b, SessionLocalB = make_env()
    with SessionLocalB() as db:
        seed_sources(db)
        manifest_b = run_tiny(db)
    assert manifest_b["table_counts"] == manifest_a["counts"]


def test_different_seed_changes_source_data():
    def values(seed: int):
        _, SessionLocal = make_env()
        with SessionLocal() as db:
            seed_sources(db)
            run_pipeline(db, tiny_cfg(seed=seed))
            inspections = db.scalars(
                select(TMSInspection).order_by(TMSInspection.id)
            ).all()
            return sorted((i.inspection_date.isoformat(), i.parameter_value)
                          for i in inspections)

    first = values(42)
    second = values(43)
    assert first != second


# --------------------------------------------------------------------------- #
# 3. Master and COA source layer
# --------------------------------------------------------------------------- #
def test_master_locations_assets_parameters(seeded: Session):
    manifest = run_tiny(seeded)
    cfg = tiny_cfg()
    combos = cfg.station_count * cfg.profile.lines_per_station
    assert manifest["master_stats"]["locations"] == combos
    assert seeded.scalar(select(func.count()).select_from(LocationMaster)) == combos
    assert manifest["master_stats"]["assets"] == cfg.asset_count
    assets = seeded.scalars(select(AssetMaster).order_by(AssetMaster.id)).all()
    assert all(a.source_asset_id.startswith("SYN-") for a in assets)
    assert all(a.location_id is not None for a in assets)
    params = seeded.scalars(select(AssetParameter)).all()
    assert manifest["master_stats"]["asset_parameters"] == len(params)
    assert all(isinstance(p.recorded_date, datetime) for p in params)


def test_coa_trains_schedules_movements_occupancy_events(seeded: Session):
    cfg = tiny_cfg()
    combos = cfg.station_count * cfg.profile.lines_per_station
    run_tiny(seeded)
    assert seeded.scalar(select(func.count()).select_from(Train)) == cfg.train_count
    assert (
        seeded.scalar(select(func.count()).select_from(TrainSchedule))
        == combos * cfg.days
    )
    assert (
        seeded.scalar(select(func.count()).select_from(TrainMovement))
        == cfg.train_count * cfg.days * 2
    )
    template = cfg.window_template()
    assert (
        seeded.scalar(select(func.count()).select_from(LineOccupancy))
        == combos * cfg.days * len(template)
    )
    assert (
        seeded.scalar(select(func.count()).select_from(OperationalEvent))
        == cfg.train_count * min(3, cfg.days)
    )
    trains = seeded.scalars(select(Train.train_id)).all()
    assert all(t.startswith("SYN-TRAIN-") for t in trains)


def test_schedule_and_occupancy_intervals_are_well_formed(seeded: Session):
    run_tiny(seeded)
    bad_schedules = seeded.scalar(
        select(func.count()).select_from(TrainSchedule).where(
            TrainSchedule.scheduled_arrival >= TrainSchedule.scheduled_departure
        )
    )
    assert bad_schedules == 0
    bad_occupancy = seeded.scalar(
        select(func.count()).select_from(LineOccupancy).where(
            LineOccupancy.occupancy_start >= LineOccupancy.occupancy_end
        )
    )
    assert bad_occupancy == 0
    movements = seeded.scalars(
        select(TrainMovement).where(TrainMovement.source_event_id.like("SYN-COA-%"))
    ).all()
    assert all(m.station_code and m.line_number for m in movements)


def test_available_windows_derived_by_service(seeded: Session):
    cfg = tiny_cfg()
    run_tiny(seeded)
    windows = seeded.scalars(select(AvailableWindow)).all()
    gaps = len(cfg.window_template()) - 1
    combos = cfg.station_count * cfg.profile.lines_per_station
    assert len(windows) == combos * cfg.days * gaps
    assert all(w.window_status == "AVAILABLE" for w in windows)
    assert all(w.window_start < w.window_end for w in windows)
    assert all(w.duration_minutes and w.duration_minutes > 0 for w in windows)
    assert all(w.calculation_source == CALCULATION_SOURCE for w in windows)


def test_windows_tagged_as_synthetic(seeded: Session):
    run_tiny(seeded)
    windows = seeded.scalars(select(AvailableWindow)).all()
    assert windows
    assert all(MARKER in (w.remarks or "") for w in windows)


# --------------------------------------------------------------------------- #
# 4. Source systems: TMS / TDMS / SMMS
# --------------------------------------------------------------------------- #
def test_tms_defect_maintenance_chain(seeded: Session):
    run_tiny(seeded)
    cfg = tiny_cfg()
    assert seeded.scalar(select(func.count()).select_from(TMSInspection)) == cfg.inspection_count
    assert seeded.scalar(select(func.count()).select_from(TMSDefect)) == cfg.defect_count
    assert seeded.scalar(select(func.count()).select_from(TMSMaintenance)) == cfg.defect_count
    defects = seeded.scalars(select(TMSDefect)).all()
    assert all(d.inspection_id is not None for d in defects)
    assert all(MARKER in (d.remarks or "") for d in defects)
    mains = seeded.scalars(select(TMSMaintenance)).all()
    assert all(m.defect_id is not None for m in mains)


def test_tdms_failure_chain_and_orphan_maintenance(seeded: Session):
    run_tiny(seeded)
    assert seeded.scalar(select(func.count()).select_from(TDMSFailure)) == tiny_cfg().defect_count
    failures = seeded.scalars(select(TDMSFailure)).all()
    assert all(f.inspection_id is not None for f in failures)
    assert all(MARKER in (f.remarks or "") for f in failures)
    orphans = seeded.scalars(
        select(TDMSMaintenance).where(TDMSMaintenance.failure_id.is_(None))
    ).all()
    assert orphans, "expected at least one deliberate orphan TDMS maintenance"


def test_smms_alert_chain_and_synthetic_maintainer(seeded: Session):
    run_tiny(seeded)
    assert seeded.scalar(select(func.count()).select_from(SMMSAlert)) == tiny_cfg().defect_count
    alerts = seeded.scalars(select(SMMSAlert)).all()
    assert all(a.inspection_id is not None for a in alerts)
    for alert in alerts:
        assert alert.maintainer_name.startswith("MAINTAINER-")
        assert re.fullmatch(r"9\d{9}", alert.maintainer_mobile)
    mains = seeded.scalars(select(SMMSMaintenance)).all()
    assert all(m.alert_id is not None for m in mains)


def test_source_timestamps_live_inside_dataset_window(seeded: Session):
    cfg = tiny_cfg()
    run_tiny(seeded)
    start = day_start(cfg.start_date, 0)
    end = day_start(cfg.start_date, cfg.days) - timedelta(minutes=1)

    for model, col in [
        (TMSInspection, TMSInspection.inspection_date),
        (TMSDefect, TMSDefect.detected_date),
        (TMSMaintenance, TMSMaintenance.start_date),
        (TDMSInspection, TDMSInspection.inspection_date),
        (TDMSFailure, TDMSFailure.failure_date),
        (SMMSInspection, SMMSInspection.inspection_date),
        (SMMSAlert, SMMSAlert.incidence_date_time),
        (OperationalEvent, OperationalEvent.event_datetime),
    ]:
        rows = seeded.scalars(select(model)).all()
        assert rows
        for row in rows:
            value = getattr(row, col.key)
            assert start <= value <= end, (model.__tablename__, value)


def test_inspection_precedes_detection(seeded: Session):
    run_tiny(seeded)
    defects = seeded.execute(
        select(TMSDefect, TMSInspection.inspection_date).join(
            TMSInspection, TMSDefect.inspection_id == TMSInspection.id
        )
    ).all()
    assert defects
    for defect, inspection_date in defects:
        assert defect.detected_date >= inspection_date


# --------------------------------------------------------------------------- #
# 5. Unified layer + block requirements
# --------------------------------------------------------------------------- #
def test_unified_normalization_marks_requirements(seeded: Session):
    run_tiny(seeded)
    mrs = seeded.scalars(select(MaintenanceRequirement)).all()
    sources = seeded.scalars(select(SourceSystem)).all()
    all_ids = {s.id for s in sources}
    assert mrs
    assert all(mr.source_system_id in all_ids for mr in mrs)
    assert all(mr.source_record_type in ("TMS_MAINTENANCE", "TDMS_MAINTENANCE",
                                         "SMMS_MAINTENANCE") for mr in mrs)
    assert all(MARKER in (mr.description or "") for mr in mrs)
    defect_failures = seeded.scalars(select(DefectFailure)).all()
    assert defect_failures
    assert all(df.asset_id in {m.asset_id for m in mrs} for df in defect_failures)


def test_block_requirements_target_available_gaps(seeded: Session):
    cfg = tiny_cfg()
    run_tiny(seeded)
    brs = seeded.scalars(select(BlockRequirement)).all()
    assert brs
    assert all(MARKER in (br.remarks or "") for br in brs)
    template = cfg.window_template()
    assert all(
        br.block_type in ("NORMAL", "POWER_ONLY", "TRAFFIC_ONLY") for br in brs
    )
    assert all((br.power_block_required or br.traffic_block_required)
               and br.block_type in ("POWER_ONLY", "TRAFFIC_ONLY")
               or br.block_type == "NORMAL"
               for br in brs)
    # earliest/latest must fall on a real derived gap boundary of that day.
    for br in brs:
        assert br.earliest_start is not None and br.latest_end is not None
        assert br.earliest_start < br.latest_end


def test_block_requirement_duration_comes_from_maintenance(seeded: Session):
    run_tiny(seeded)
    for br in seeded.scalars(select(BlockRequirement)).all():
        mr = seeded.get(MaintenanceRequirement, br.maintenance_requirement_id)
        assert br.required_duration_minutes == mr.required_duration_minutes
        assert br.required_duration_minutes is not None and br.required_duration_minutes > 0


# --------------------------------------------------------------------------- #
# 6. Planning layer
# --------------------------------------------------------------------------- #
def test_planning_tasks_pair_with_requirements(seeded: Session):
    run_tiny(seeded)
    mrs = seeded.scalars(select(MaintenanceRequirement)).all()
    tasks = seeded.scalars(select(PlanningTask)).all()
    assert len(tasks) == len(mrs)
    assert all(t.maintenance_requirement_id in {mr.id for mr in mrs} for t in tasks)
    assert all(re.fullmatch(r"PT-\d{6}", t.task_code or "") for t in tasks)
    assert all(MARKER in (t.description or "") for t in tasks)


def test_no_duplicate_planning_task_per_requirement(seeded: Session):
    run_tiny(seeded)
    seen = seeded.execute(
        select(PlanningTask.maintenance_requirement_id)
    ).all()
    ids = [row[0] for row in seen]
    assert len(ids) == len(set(ids))


def test_planning_constraints_derived_from_block_requirement(seeded: Session):
    run_tiny(seeded)
    tasks = seeded.scalars(select(PlanningTask.id)).all()
    constraints = seeded.scalars(select(PlanningConstraint)).all()
    assert constraints
    assert all(c.planning_task_id in set(tasks) for c in constraints)
    assert all(c.hard_constraint for c in constraints)
    types = {c.constraint_type for c in constraints}
    assert {"DURATION", "TIME_WINDOW", "LOCATION", "LINE"}.issubset(types)


def test_planning_resources_and_task_links(seeded: Session):
    manifest = run_tiny(seeded)
    resources = seeded.scalars(select(PlanningResource)).all()
    assert resources
    assert all(r.resource_code.startswith("SYN-RES-") for r in resources)
    assert all(r.capacity and r.capacity > 0 for r in resources)
    assert all(r.status in ("AVAILABLE", "UNAVAILABLE", "UNDER_MAINTENANCE")
               for r in resources)
    links = seeded.scalars(select(TaskResource)).all()
    tasks = seeded.scalars(select(PlanningTask.id)).all()
    task_ids = set(tasks)
    assert links
    assert all(l.planning_task_id in task_ids for l in links)
    assert all(l.allocation_status in ("ALLOCATED", "REQUIRED", "UNAVAILABLE")
               for l in links)
    assert all(l.required_quantity and l.required_quantity > 0 for l in links)
    assert manifest["planning"]["resources_created"] == len(resources)


def test_task_dependencies_well_formed(seeded: Session):
    run_tiny(seeded)
    tasks = seeded.scalars(select(PlanningTask.id)).all()
    task_ids = set(tasks)
    deps = seeded.scalars(select(TaskDependency)).all()
    assert deps
    for dep in deps:
        assert dep.predecessor_task_id in task_ids
        assert dep.successor_task_id in task_ids
        assert dep.predecessor_task_id != dep.successor_task_id
        assert dep.dependency_type == "PRECEDENCE"


def test_missing_duration_requirement_skips_task(seeded: Session):
    asset = AssetMaster(
        source_system_id=seeded.scalar(
            select(SourceSystem.id).where(SourceSystem.system_code == "TMS")
        ),
        source_asset_id="REAL-ASSET-1",
        asset_type="TRACK",
        asset_name="Real asset",
    )
    seeded.add(asset)
    seeded.flush()
    seeded.add(
        MaintenanceRequirement(
            asset_id=asset.id,
            source_system_id=asset.source_system_id,
            source_record_type="TMS_MAINTENANCE",
            source_record_id=999999,
            maintenance_type="REPAIR",
            description="Real requirement without duration",
            required_duration_minutes=None,
            status="PENDING",
        )
    )
    seeded.commit()
    stats = generate_planning_tasks(seeded)
    assert stats["created"] == 0
    assert seeded.scalar(select(func.count()).select_from(PlanningTask)) == 0


# --------------------------------------------------------------------------- #
# 7. Candidate windows
# --------------------------------------------------------------------------- #
def test_candidate_windows_cover_task_window_product(seeded: Session):
    manifest = run_tiny(seeded)
    tasks = seeded.scalar(select(func.count()).select_from(PlanningTask))
    windows = seeded.scalar(select(func.count()).select_from(AvailableWindow))
    candidates = seeded.scalar(select(func.count()).select_from(CandidateBlockWindow))
    assert candidates == tasks * windows
    assert manifest["candidates"]["processed"] >= candidates


def test_feasible_candidates_are_temporally_valid(seeded: Session):
    run_tiny(seeded)
    feasible = seeded.scalars(
        select(CandidateBlockWindow).where(
            CandidateBlockWindow.feasibility_status == "FEASIBLE"
        )
    ).all()
    assert feasible
    for cand in feasible:
        assert cand.feasible is True
        assert cand.candidate_duration_minutes and cand.candidate_duration_minutes > 0
        window = seeded.get(AvailableWindow, cand.available_window_id)
        assert window is not None
        assert cand.candidate_start >= window.window_start
        assert cand.candidate_end <= window.window_end


def test_candidate_statuses_are_explicit(seeded: Session):
    run_tiny(seeded)
    statuses = set(
        seeded.execute(select(CandidateBlockWindow.feasibility_status)).scalars().all()
    )
    assert statuses.issubset({"FEASIBLE", "INFEASIBLE", "REQUIRES_REVIEW"})
    assert "FEASIBLE" in statuses


# --------------------------------------------------------------------------- #
# 8. Optimization placeholder (never runs an optimizer)
# --------------------------------------------------------------------------- #
def test_optimization_placeholder_opt_in(seeded: Session):
    run_tiny(seeded, with_optimization=True)
    runs = seeded.scalars(select(OptimizationRun)).all()
    assert len(runs) == 1
    assert runs[0].run_code.startswith("SYN-OPT-")
    assert runs[0].status == "PENDING"
    task_count = seeded.scalar(select(func.count()).select_from(PlanningTask))
    assert seeded.scalar(select(func.count()).select_from(OptimizationInput)) == task_count
    assert seeded.scalar(select(func.count()).select_from(OptimizationOutput)) == 0


def test_optimization_placeholder_opt_out(seeded: Session):
    manifest = run_tiny(seeded)
    assert manifest["optimization"]["run_created"] == 0
    assert seeded.scalar(select(func.count()).select_from(OptimizationRun)) == 0


# --------------------------------------------------------------------------- #
# 9. Manifest + idempotency + cleanup + verification
# --------------------------------------------------------------------------- #
def test_manifest_written(tmp_path, seeded: Session):
    manifest_path = tmp_path / "manifest.json"
    cfg = tiny_cfg(write_manifest=True, manifest_path=manifest_path)
    run_pipeline(seeded, cfg)
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dataset_id"].startswith("SYN-STEP11-")
    assert manifest["seed"] == cfg.seed
    assert manifest["scale"] == "tiny"
    assert manifest["scenario"] == "normal"
    assert manifest["generator_version"].startswith("STEP11-")
    assert len(manifest["table_counts"]) >= 36
    assert manifest["configuration_summary"]["targets"]["assets"] == 10


def test_rerun_is_idempotent(seeded: Session):
    first = run_tiny(seeded)
    second = run_tiny(seeded)
    assert second["table_counts"] == first["table_counts"]
    mr_total = seeded.scalar(select(func.count()).select_from(PlanningTask))
    assert mr_total > 0


def test_no_schema_changes(seeded: Session):
    before = set(inspect(seeded.connection()).get_table_names())
    run_tiny(seeded)
    after = set(inspect(seeded.connection()).get_table_names())
    assert before == after
    assert "planning_task" in before


def test_cleanup_keeps_only_source_systems(seeded: Session):
    run_tiny(seeded)
    summary = cleanup_synthetic(seeded)
    assert summary["total"] > 0
    for model in [
        AssetMaster, AssetParameter, AvailableWindow, BlockRequirement,
        CandidateBlockWindow, LineOccupancy, LocationMaster,
        MaintenanceRequirement, OperationalEvent, PlanningConstraint,
        PlanningResource, PlanningTask, SMMSAlert, SMMSInspection,
        SMMSMaintenance, TDMSFailure, TDMSInspection, TDMSMaintenance,
        TMSDefect, TMSInspection, TMSMaintenance, TaskDependency,
        TaskResource, Train, TrainMovement, TrainSchedule, DefectFailure,
    ]:
        assert seeded.scalar(select(func.count()).select_from(model)) == 0, model
    assert seeded.scalar(select(func.count()).select_from(SourceSystem)) == 4


def test_cleanup_second_run_is_empty(seeded: Session):
    run_tiny(seeded)
    cleanup_synthetic(seeded)
    second = cleanup_synthetic(seeded)
    assert second["total"] == 0


def test_cleanup_preserves_real_rows(seeded: Session):
    tms = seeded.scalar(select(SourceSystem).where(SourceSystem.system_code == "TMS"))
    real_asset = AssetMaster(
        source_system_id=tms.id,
        source_asset_id="REAL-LIVE-ASSET",
        asset_type="TRACK",
        asset_name="Live asset",
        remarks="real operational asset",
    )
    seeded.add(real_asset)
    seeded.flush()
    seeded.add(
        TMSInspection(
            asset_id=real_asset.id,
            inspection_date=datetime(2026, 1, 5, 8, 0),
            inspection_type="USFD",
            parameter_code="X",
            parameter_value=1,
            remarks="real inspection",
        )
    )
    seeded.commit()

    run_tiny(seeded)
    cleanup_synthetic(seeded)

    assert seeded.scalar(
        select(func.count()).select_from(TMSInspection).where(
            TMSInspection.asset_id == real_asset.id
        )
    ) == 1
    assert seeded.scalar(
        select(func.count()).select_from(TMSDefect).where(
            TMSDefect.asset_id.in_(
                select(AssetMaster.id).where(AssetMaster.source_asset_id == "REAL-LIVE-ASSET")
            )
        )
    ) == 0
    assert seeded.get(AssetMaster, real_asset.id) is not None


def test_verify_passes_on_generated_dataset(seeded: Session):
    cfg = tiny_cfg()
    run_pipeline(seeded, cfg)
    verification = verify_synthetic(seeded, cfg)
    assert verification["pass"] is True
    assert verification["problems"] == []
    assert verification["counts"]["synthetic_assets"] == cfg.asset_count
    assert verification["counts"]["candidate_windows"]["feasible"] >= 1


# --------------------------------------------------------------------------- #
# 10. CLI wiring
# --------------------------------------------------------------------------- #
def load_cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_synthetic_data.py"
    spec = importlib.util.spec_from_file_location("generate_synthetic_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cli_db(tmp_path) -> str:
    db_path = tmp_path / "cli.sqlite"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        seed_sources(db)
    engine.dispose()
    return db_path.as_posix()


def test_cli_dry_run_prints_plan(tmp_path, capsys, monkeypatch):
    cli = load_cli()
    monkeypatch.chdir(tmp_path)
    code = cli.main(["--scale", "large", "--days", "30", "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "DRY-RUN" in out
    assert "estimated_candidates" in out
    assert "No database changes" in out


def test_cli_large_is_dry_run_only(tmp_path):
    cli = load_cli()
    assert cli.main(["--scale", "large"]) == 1


def test_cli_generates_verifies_and_writes_manifest(tmp_path, monkeypatch):
    cli = load_cli()
    url = f"sqlite:///{cli_db(tmp_path)}"
    monkeypatch.chdir(tmp_path)
    code = cli.main(
        [
            "--db-url", url,
            "--seed", "42", "--scale", "tiny", "--days", "7",
            "--start-date", start_date.isoformat(),
            "--scenario", "normal", "--batch-size", "10",
            "--verify",
        ]
    )
    assert code == 0
    assert (tmp_path / "synthetic_dataset_manifest.json").exists()
    engine = create_engine(url)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AssetMaster)) == 10
        assert db.scalar(select(func.count()).select_from(PlanningTask)) >= 1
    engine.dispose()


def test_cli_cleanup_flag(tmp_path, monkeypatch):
    cli = load_cli()
    url = f"sqlite:///{cli_db(tmp_path)}"
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--db-url", url, "--seed", "42", "--scale", "tiny",
                     "--days", "7", "--start-date", start_date.isoformat(),
                     "--scenario", "normal", "--batch-size", "10"]) == 0
    assert cli.main(["--db-url", url, "--cleanup"]) == 0
    engine = create_engine(url)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AssetMaster)) == 0
        assert db.scalar(select(func.count()).select_from(SourceSystem)) == 4
    engine.dispose()