from datetime import datetime

from sqlalchemy import func, inspect, select

from app.models.available_window import AvailableWindow
from app.models.block_requirement import BlockRequirement
from app.models.candidate_block_window import CandidateBlockWindow
from app.models.defect_failure import DefectFailure
from app.models.maintenance_requirement import MaintenanceRequirement
from app.models.planning_task import PlanningTask
from app.models.tms_defect import TMSDefect
from app.models.tms_inspection import TMSInspection

FORBIDDEN_SUBSTRINGS = [
    "score",
    "confidence",
    "prediction",
    "recommended",
    "optimal",
    "optimization",
    "ai_",
    "ml_",
    "rank",
]


def create_source(client, code):
    response = client.post(
        "/api/source-systems",
        json={
            "system_code": code,
            "system_name": code,
            "description": f"TEST/SYNTHETIC {code} source system for API testing.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_asset(client, source, suffix):
    response = client.post(
        "/api/assets",
        json={
            "source_system_id": source["id"],
            "source_asset_id": f"{suffix}-CAND-ASSET",
            "asset_type": "TEST/SYNTHETIC",
            "asset_name": f"TEST/SYNTHETIC {suffix} Asset",
            "status": "TEST",
        },
    )
    assert response.status_code == 201
    return response.json()


def find_by_type(items, record_type):
    matches = [i for i in items if i["source_record_type"] == record_type]
    assert len(matches) == 1
    return matches[0]


def build_chain(
    client,
    db_session,
    *,
    station="STA-7",
    line="L7",
    block_duration=120,
    earliest_start=None,
    latest_end=None,
    power_block=False,
    traffic_block=False,
):
    source = create_source(client, "TMS")
    asset = create_asset(client, source, "TMS")
    inspection = client.post(
        "/api/tms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": "2026-05-01T10:00:00",
            "inspection_type": "USFD",
            "parameter_code": "TUBE-DEFLECTION",
            "parameter_value": "4.5",
            "remarks": "TEST/SYNTHETIC TMS inspection.",
        },
    ).json()
    defect = client.post(
        "/api/tms/defects",
        json={
            "asset_id": asset["id"],
            "inspection_id": inspection["id"],
            "defect_code": "TMS-DF-001",
            "defect_description": "TEST/SYNTHETIC TMS defect observed.",
            "severity": "HIGH",
            "detected_date": "2026-05-01T10:30:00",
            "status": "OPEN",
            "remarks": "TEST/SYNTHETIC TMS defect remarks.",
        },
    ).json()
    client.post(
        "/api/tms/maintenance",
        json={
            "asset_id": asset["id"],
            "defect_id": defect["id"],
            "maintenance_type": "REPLACEMENT",
            "planned_date": "2026-05-10T09:00:00",
            "start_date": "2026-05-10T09:00:00",
            "end_date": "2026-05-10T11:30:00",
            "status": "PLANNED",
            "remarks": "TEST/SYNTHETIC TMS maintenance record.",
        },
    ).json()
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")

    block = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr["id"],
            "station_code": station,
            "line_number": line,
            "block_type": "INTEGRATED_BLOCK",
            "required_duration_minutes": block_duration,
            "earliest_start": earliest_start,
            "latest_end": latest_end,
            "power_block_required": power_block,
            "traffic_block_required": traffic_block,
            "resource_notes": "TEST/SYNTHETIC resource note.",
            "status": "REQUIRED",
            "remarks": "TEST/SYNTHETIC block requirement.",
        },
    ).json()

    summary = client.post("/api/planning/generate-tasks").json()
    assert summary["created"] == 1
    tasks = client.get(f"/api/planning/tasks?maintenance_requirement_id={mr['id']}").json()
    task = tasks[0]
    return {
        "source": source,
        "asset": asset,
        "defect": defect,
        "mr": mr,
        "block": block,
        "task": task,
    }


def make_window(
    db_session,
    *,
    station="STA-7",
    line="L7",
    start="2026-05-01T10:00:00",
    end="2026-05-01T14:00:00",
):
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    window = AvailableWindow(
        station_code=station,
        line_number=line,
        window_start=start_dt,
        window_end=end_dt,
        duration_minutes=int((end_dt - start_dt).total_seconds() // 60),
        window_status="AVAILABLE",
        calculation_source="TEST/SYNTHETIC:COA_SOURCE_DERIVATION_GAP",
        generated_at=datetime.now(),
    )
    db_session.add(window)
    db_session.commit()
    return window


def make_task(db_session, *, duration=150, block=None, task_type="REPLACEMENT"):
    task = PlanningTask(
        maintenance_requirement_id=block["maintenance_requirement_id"] if block else 1,
        block_requirement_id=block["id"] if block else None,
        asset_id=1,
        task_code="PT-CAND-TEST",
        task_type=task_type,
        description="TEST/SYNTHETIC planning task.",
        status="OPEN",
        earliest_start=None,
        latest_end=None,
        duration_minutes=duration,
        location_code=block["station_code"] if block else None,
    )
    db_session.add(task)
    db_session.commit()
    return task


def count_pairs(db_session):
    sub = (
        select(
            CandidateBlockWindow.planning_task_id,
            CandidateBlockWindow.available_window_id,
        )
        .distinct()
        .subquery()
    )
    return db_session.scalar(select(func.count()).select_from(sub))


def test_candidate_table_created(db_session):
    inspector = inspect(db_session.bind)
    assert "candidate_block_window" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("candidate_block_window")}
    for expected in (
        "id",
        "planning_task_id",
        "block_requirement_id",
        "available_window_id",
        "candidate_start",
        "candidate_end",
        "candidate_duration_minutes",
        "feasible",
        "feasibility_status",
        "feasibility_reason",
        "created_at",
        "updated_at",
    ):
        assert expected in cols, f"missing column {expected}"
    uniq = {
        tuple(u["column_names"])
        for u in inspector.get_unique_constraints("candidate_block_window")
    }
    assert ("planning_task_id", "available_window_id") in uniq
    fks = inspector.get_foreign_keys("candidate_block_window")
    fk_sets = {
        (f["constrained_columns"][0], f["referred_table"], f["options"].get("ondelete"))
        for f in fks
    }
    assert ("planning_task_id", "planning_task", "RESTRICT") in fk_sets
    assert ("block_requirement_id", "block_requirement", "RESTRICT") in fk_sets
    assert ("available_window_id", "available_window", "RESTRICT") in fk_sets


def test_valid_temporal_candidate(client, db_session):
    chain = build_chain(client, db_session)
    window = make_window(db_session)
    summary = client.post("/api/candidates/generate").json()
    assert summary["processed"] == 1
    assert summary["created"] == 1
    assert summary["infeasible"] == 0
    assert summary["requires_review"] == 0
    row = db_session.scalar(
        select(CandidateBlockWindow).where(
            CandidateBlockWindow.planning_task_id == chain["task"]["id"]
        )
    )
    assert row.feasible is True
    assert row.feasibility_status == "FEASIBLE"
    assert row.feasibility_reason == "FEASIBLE_TEMPORAL_MATCH"
    assert row.candidate_duration_minutes == 150
    assert row.candidate_start == datetime(2026, 5, 1, 10, 0)
    assert row.candidate_end == datetime(2026, 5, 1, 12, 30)
    assert row.candidate_end <= window.window_end
    assert row.block_requirement_id == chain["block"]["id"]


def test_candidate_api_get(client, db_session):
    chain = build_chain(client, db_session)
    make_window(db_session)
    client.post("/api/candidates/generate")
    rows = client.get("/api/candidates/windows").json()
    assert len(rows) == 1
    by_task = client.get(
        f"/api/candidates/windows?planning_task_id={chain['task']['id']}"
    ).json()
    assert len(by_task) == 1
    by_block = client.get(
        f"/api/candidates/windows?block_requirement_id={chain['block']['id']}"
    ).json()
    assert len(by_block) == 1
    by_feasible = client.get("/api/candidates/windows?feasible=true").json()
    assert len(by_feasible) == 1
    by_status = client.get("/api/candidates/windows?feasibility_status=FEASIBLE").json()
    assert len(by_status) == 1
    assert client.get("/api/candidates/windows?feasible=false").json() == []


def test_candidate_api_get_by_id(client, db_session):
    chain = build_chain(client, db_session)
    make_window(db_session)
    client.post("/api/candidates/generate")
    candidate_id = db_session.scalar(
        select(CandidateBlockWindow.id).where(
            CandidateBlockWindow.planning_task_id == chain["task"]["id"]
        )
    )
    row = client.get(f"/api/candidates/windows/{candidate_id}")
    assert row.status_code == 200
    assert row.json()["id"] == candidate_id
    missing = client.get("/api/candidates/windows/999999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Candidate block window not found"


def test_duration_too_long(client, db_session):
    chain = build_chain(client, db_session)
    make_window(db_session, start="2026-05-01T10:00:00", end="2026-05-01T11:00:00")
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "INFEASIBLE"
    assert row.feasibility_reason == "DURATION_EXCEEDS_WINDOW"
    assert row.candidate_duration_minutes == 150


def test_location_mismatch(client, db_session):
    build_chain(client, db_session)
    make_window(db_session, station="STA-8")
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "INFEASIBLE"
    assert row.feasibility_reason == "LOCATION_MISMATCH"


def test_line_mismatch(client, db_session):
    build_chain(client, db_session)
    make_window(db_session, line="L8")
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "INFEASIBLE"
    assert row.feasibility_reason == "LINE_MISMATCH"


def test_earliest_start_handling(client, db_session):
    build_chain(client, db_session, earliest_start="2026-05-01T11:00:00")
    make_window(db_session, start="2026-05-01T10:00:00", end="2026-05-01T14:00:00")
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is True
    assert row.feasibility_status == "FEASIBLE"
    assert row.candidate_start == datetime(2026, 5, 1, 11, 0)
    assert row.candidate_end == datetime(2026, 5, 1, 13, 30)


def test_earliest_start_overflow_infeasible(client, db_session):
    build_chain(client, db_session, earliest_start="2026-05-01T13:00:00")
    make_window(db_session, start="2026-05-01T10:00:00", end="2026-05-01T14:00:00")
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "INFEASIBLE"
    assert row.feasibility_reason == "DURATION_EXCEEDS_WINDOW"


def test_latest_end_handling(client, db_session):
    build_chain(client, db_session, latest_end="2026-05-01T12:00:00")
    make_window(db_session, start="2026-05-01T11:00:00", end="2026-05-01T14:00:00")
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "INFEASIBLE"
    assert row.feasibility_reason == "LATEST_END_VIOLATION"


def test_power_block_review(client, db_session):
    build_chain(client, db_session, power_block=True)
    make_window(db_session)
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "REQUIRES_REVIEW"
    assert row.feasibility_reason == "POWER_BLOCK_CONFIRMATION_REQUIRED"


def test_traffic_block_review(client, db_session):
    build_chain(client, db_session, traffic_block=True)
    make_window(db_session)
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "REQUIRES_REVIEW"
    assert row.feasibility_reason == "TRAFFIC_BLOCK_CONFIRMATION_REQUIRED"


def test_missing_duration(client, db_session):
    chain = build_chain(client, db_session)
    task = db_session.get(PlanningTask, chain["task"]["id"])
    task.duration_minutes = 0
    task.block_requirement_id = None
    db_session.commit()
    make_window(db_session)
    summary = client.post("/api/candidates/generate").json()
    assert summary["requires_review"] == 1
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "REQUIRES_REVIEW"
    assert row.feasibility_reason == "MISSING_DURATION"
    assert row.candidate_duration_minutes == 0


def test_missing_location_context(client, db_session):
    chain = build_chain(client, db_session)
    task = db_session.get(PlanningTask, chain["task"]["id"])
    task.block_requirement_id = None
    db_session.commit()
    make_window(db_session)
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))
    assert row.feasible is False
    assert row.feasibility_status == "REQUIRES_REVIEW"
    assert row.feasibility_reason == "MISSING_LOCATION_CONTEXT"


def test_check_endpoint(client, db_session):
    chain = build_chain(client, db_session)
    window = make_window(db_session)
    before = client.post("/api/candidates/check", json={
        "planning_task_id": chain["task"]["id"],
        "available_window_id": window.id,
    })
    assert before.status_code == 200
    body = before.json()
    assert body["feasible"] is True
    assert body["feasibility_status"] == "FEASIBLE"
    assert body["existing_candidate_id"] is None
    assert db_session.scalar(select(func.count()).select_from(CandidateBlockWindow)) == 0

    client.post("/api/candidates/generate")
    after = client.post("/api/candidates/check", json={
        "planning_task_id": chain["task"]["id"],
        "available_window_id": window.id,
    }).json()
    assert after["existing_candidate_id"] is not None
    assert after["feasibility_status"] == "FEASIBLE"


def test_invalid_fk_check(client, db_session):
    chain = build_chain(client, db_session)
    window = make_window(db_session)
    bad_task = client.post("/api/candidates/check", json={
        "planning_task_id": 999999,
        "available_window_id": window.id,
    })
    assert bad_task.status_code == 404
    assert bad_task.json()["detail"] == "Planning task not found"
    bad_window = client.post("/api/candidates/check", json={
        "planning_task_id": chain["task"]["id"],
        "available_window_id": 999999,
    })
    assert bad_window.status_code == 404
    assert bad_window.json()["detail"] == "Available window not found"


def test_idempotent_generation(client, db_session):
    chain = build_chain(client, db_session)
    make_window(db_session, start="2026-05-01T10:00:00", end="2026-05-01T14:00:00")
    make_window(db_session, station="STA-8", start="2026-05-02T10:00:00", end="2026-05-02T14:00:00")
    first = client.post("/api/candidates/generate").json()
    assert first["created"] == 2
    assert first["processed"] == 2
    second = client.post("/api/candidates/generate").json()
    assert second["created"] == 0
    assert second["skipped"] == first["processed"]
    total = db_session.scalar(select(func.count()).select_from(CandidateBlockWindow))
    distinct = count_pairs(db_session)
    assert total == 2
    assert distinct == total


def test_source_data_unchanged(client, db_session):
    build_chain(client, db_session)
    make_window(db_session)
    counts = {
        "tms_inspection": db_session.scalar(select(func.count()).select_from(TMSInspection)),
        "planning_task": db_session.scalar(select(func.count()).select_from(PlanningTask)),
        "maintenance_requirement": db_session.scalar(select(func.count()).select_from(MaintenanceRequirement)),
        "defect_failure": db_session.scalar(select(func.count()).select_from(DefectFailure)),
    }
    client.post("/api/candidates/generate")
    after = {
        "tms_inspection": db_session.scalar(select(func.count()).select_from(TMSInspection)),
        "planning_task": db_session.scalar(select(func.count()).select_from(PlanningTask)),
        "maintenance_requirement": db_session.scalar(select(func.count()).select_from(MaintenanceRequirement)),
        "defect_failure": db_session.scalar(select(func.count()).select_from(DefectFailure)),
    }
    assert after == counts


def test_available_window_unchanged(client, db_session):
    build_chain(client, db_session)
    window = make_window(db_session)
    columns = [
        "station_code", "line_number", "window_start", "window_end",
        "duration_minutes", "window_status", "calculation_source",
    ]
    snapshot = {
        col: getattr(window, col)
        for col in columns
    }
    client.post("/api/candidates/generate")
    window_after = db_session.get(AvailableWindow, window.id)
    for col in columns:
        assert getattr(window_after, col) == snapshot[col], f"{col} changed"


def test_no_ai_optimization_fields(db_session):
    columns = {c["name"].lower() for c in inspect(db_session.bind).get_columns("candidate_block_window")}
    for column in columns:
        for bad in FORBIDDEN_SUBSTRINGS:
            assert bad not in column, f"candidate_block_window.{column} contains {bad}"


def test_end_to_end_provenance(client, db_session):
    chain = build_chain(client, db_session)
    window = make_window(db_session)
    client.post("/api/candidates/generate")
    row = db_session.scalar(select(CandidateBlockWindow))

    prov = db_session.execute(
        select(
            CandidateBlockWindow,
            PlanningTask,
            MaintenanceRequirement,
            DefectFailure,
            BlockRequirement,
            AvailableWindow,
        )
        .join(PlanningTask, PlanningTask.id == CandidateBlockWindow.planning_task_id)
        .join(MaintenanceRequirement, MaintenanceRequirement.id == PlanningTask.maintenance_requirement_id)
        .join(DefectFailure, DefectFailure.id == MaintenanceRequirement.defect_failure_id)
        .join(BlockRequirement, BlockRequirement.id == CandidateBlockWindow.block_requirement_id)
        .join(AvailableWindow, AvailableWindow.id == CandidateBlockWindow.available_window_id)
        .where(CandidateBlockWindow.id == row.id)
    ).first()
    assert prov is not None
    assert prov[1].id == chain["task"]["id"]
    assert prov[2].id == chain["mr"]["id"]
    assert prov[3].source_record_type == "TMS_DEFECT"
    assert prov[3].source_record_id == chain["defect"]["id"]
    assert prov[4].id == chain["block"]["id"]
    assert prov[5].id == window.id

    source_defect = db_session.get(TMSDefect, chain["defect"]["id"])
    assert source_defect is not None
    assert source_defect.defect_code == "TMS-DF-001"


def test_multiple_windows_summary(client, db_session):
    chain = build_chain(client, db_session)
    make_window(db_session, start="2026-05-01T10:00:00", end="2026-05-01T14:00:00")  # FEASIBLE
    make_window(db_session, start="2026-05-01T10:00:00", end="2026-05-01T11:00:00")  # INFEASIBLE
    make_window(db_session, station="STA-8", start="2026-05-02T10:00:00", end="2026-05-02T14:00:00")  # INFEASIBLE
    summary = client.post("/api/candidates/generate").json()
    assert summary["processed"] == 3
    assert summary["created"] == 3
    assert summary["infeasible"] == 2
    assert summary["requires_review"] == 0
    windows = client.get("/api/candidates/windows?planning_task_id=%d" % chain["task"]["id"]).json()
    assert len(windows) == 3