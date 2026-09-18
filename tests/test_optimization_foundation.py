from datetime import datetime

from sqlalchemy import inspect, select

from app.core.database import Base
from app.models.available_window import AvailableWindow
from app.models.block_plan import BlockPlan
from app.models.block_plan_task import BlockPlanTask
from app.models.candidate_block_window import CandidateBlockWindow
from app.models.controller_decision import ControllerDecision
from app.models.execution_outcome import ExecutionOutcome
from app.models.optimization_input import OptimizationInput
from app.models.optimization_output import OptimizationOutput
from app.models.optimization_run import OptimizationRun
from app.models.plan_validation import PlanValidation
from app.models.planning_task import PlanningTask

FORBIDDEN_TOKENS = [
    "score",
    "confidence",
    "prediction",
    "recommended",
    "optimal",
    "embedding",
    "feature_vector",
    "probability",
    "priority",
    "risk",
    "rank",
]

STEP10_TABLES = [
    "optimization_run",
    "optimization_input",
    "optimization_output",
    "block_plan",
    "block_plan_task",
    "plan_validation",
    "controller_decision",
    "execution_outcome",
]


def create_source(client, code):
    response = client.post(
        "/api/source-systems",
        json={
            "system_code": code,
            "system_name": code,
            "description": f"TEST/SYNTHETIC {code} source system for STEP 10.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_asset(client, source, suffix):
    response = client.post(
        "/api/assets",
        json={
            "source_system_id": source["id"],
            "source_asset_id": f"{suffix}-OPT-ASSET",
            "asset_type": "TEST/SYNTHETIC",
            "asset_name": f"TEST/SYNTHETIC {suffix} Asset",
            "status": "TEST",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_tms_chain(client, asset, code, start, end):
    inspection = client.post(
        "/api/tms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": start,
            "inspection_type": "USFD",
            "parameter_code": "TUBE-DEFLECTION",
            "parameter_value": "4.5",
            "remarks": "TEST/SYNTHETIC TMS inspection.",
        },
    )
    assert inspection.status_code == 201, inspection.text
    inspection = inspection.json()
    defect = client.post(
        "/api/tms/defects",
        json={
            "asset_id": asset["id"],
            "inspection_id": inspection["id"],
            "defect_code": code,
            "defect_description": "TEST/SYNTHETIC TMS defect observed.",
            "severity": "HIGH",
            "detected_date": start,
            "status": "OPEN",
            "remarks": "TEST/SYNTHETIC TMS defect remarks.",
        },
    )
    assert defect.status_code == 201, defect.text
    defect = defect.json()
    maintenance = client.post(
        "/api/tms/maintenance",
        json={
            "asset_id": asset["id"],
            "defect_id": defect["id"],
            "maintenance_type": "REPLACEMENT",
            "planned_date": start,
            "start_date": start,
            "end_date": end,
            "status": "PLANNED",
            "remarks": "TEST/SYNTHETIC TMS maintenance record.",
        },
    )
    assert maintenance.status_code == 201, maintenance.text
    return inspection, defect, maintenance.json()


def make_window(
    db_session,
    *,
    station="STA-7",
    line="L7",
    start="2026-05-11T10:00:00",
    end="2026-05-11T14:00:00",
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


def setup_chain(client, db_session):
    """Create a synthetic planning foundation with a FEASIBLE candidate."""
    source = create_source(client, "TMS")
    asset = create_asset(client, source, "STEP10")
    _, defect, maintenance = add_tms_chain(
        client, asset, "TMS-DF-001", "2026-05-11T09:00:00", "2026-05-11T11:00:00"
    )
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = [
        m
        for m in requirements
        if m["source_record_type"] == "TMS_MAINTENANCE"
        and m["source_record_id"] == maintenance["id"]
    ][0]
    block = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr["id"],
            "station_code": "STA-7",
            "line_number": "L7",
            "block_type": "INTEGRATED_BLOCK",
            "required_duration_minutes": 120,
            "power_block_required": False,
            "traffic_block_required": False,
            "resource_notes": "TEST/SYNTHETIC resource note.",
            "status": "REQUIRED",
            "remarks": "TEST/SYNTHETIC block requirement.",
        },
    )
    assert block.status_code == 201, block.text
    block = block.json()
    client.post("/api/planning/generate-tasks")
    tasks = client.get(
        f"/api/planning/tasks?maintenance_requirement_id={mr['id']}"
    ).json()
    task = tasks[0]
    window = make_window(db_session)
    client.post("/api/candidates/generate")
    candidates = client.get(
        f"/api/candidates/windows?planning_task_id={task['id']}"
    ).json()
    assert len(candidates) == 1, candidates
    return {
        "source": source,
        "asset": asset,
        "defect": defect,
        "mr": mr,
        "block": block,
        "task": task,
        "window": window,
        "candidate": candidates[0],
    }


def make_run(client, code="RUN-1", **overrides):
    payload = {
        "run_code": code,
        "run_type": "PLANNING",
        "status": "REQUESTED",
        "objective_description": "TEST/SYNTHETIC objective.",
    }
    payload.update(overrides)
    return client.post("/api/optimization/runs", json=payload)


def make_plan(client, code="PLAN-1", **overrides):
    payload = {
        "plan_code": code,
        "plan_date": "2026-05-11",
        "status": "PROPOSED",
        "planning_horizon_start": "2026-05-11T09:00:00",
        "planning_horizon_end": "2026-05-11T15:00:00",
    }
    payload.update(overrides)
    return client.post("/api/optimization/plans", json=payload)


def add_plan_task(client, plan_id, task_id, candidate_id, start, end, duration, **extra):
    payload = {
        "block_plan_id": plan_id,
        "planning_task_id": task_id,
        "candidate_block_window_id": candidate_id,
        "planned_start": start,
        "planned_end": end,
        "planned_duration_minutes": duration,
        "status": "CONFIRMED",
    }
    payload.update(extra)
    return client.post("/api/optimization/plan-tasks", json=payload)


def validate_results(client, plan_id):
    response = client.post(f"/api/optimization/plans/{plan_id}/validate")
    assert response.status_code == 200, response.text
    return response.json()


def find_result(results, validation_type):
    return [r for r in results if r["validation_type"] == validation_type]


def test_optimization_run_creation(client, db_session):
    response = make_run(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run_code"] == "RUN-1"
    assert body["run_type"] == "PLANNING"
    assert body["status"] == "REQUESTED"
    assert body["requested_at"] is not None
    assert body["created_at"] is not None
    assert body["model_name"] is None


def test_optimization_run_uniqueness(client, db_session):
    assert make_run(client).status_code == 201
    duplicate = make_run(client)
    assert duplicate.status_code == 409, duplicate.text


def test_optimization_run_retrieval(client, db_session):
    run = make_run(client, model_name="test-model", model_version="v1").json()
    listing = client.get("/api/optimization/runs").json()
    assert len(listing) == 1
    by_type = client.get("/api/optimization/runs?run_type=PLANNING").json()
    assert len(by_type) == 1
    by_status = client.get("/api/optimization/runs?status=REQUESTED").json()
    assert len(by_status) == 1
    assert len(client.get("/api/optimization/runs?model_name=test-model").json()) == 1
    assert len(client.get("/api/optimization/runs?model_version=v1").json()) == 1
    got = client.get(f"/api/optimization/runs/{run['id']}")
    assert got.status_code == 200 and got.json()["id"] == run["id"]
    assert client.get("/api/optimization/runs/999999").status_code == 404


def test_optimization_input_creation(client, db_session):
    chain = setup_chain(client, db_session)
    run = make_run(client).json()
    response = client.post(
        "/api/optimization/inputs",
        json={
            "optimization_run_id": run["id"],
            "planning_task_id": chain["task"]["id"],
            "input_role": "TASK",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["candidate_block_window_id"] is None


def test_optimization_input_validation(client, db_session):
    chain = setup_chain(client, db_session)
    run = make_run(client).json()
    all_null = client.post(
        "/api/optimization/inputs",
        json={"optimization_run_id": run["id"], "input_role": "TASK"},
    )
    assert all_null.status_code == 422, all_null.text
    bad_role = client.post(
        "/api/optimization/inputs",
        json={
            "optimization_run_id": run["id"],
            "planning_task_id": chain["task"]["id"],
            "input_role": "NOT_A_ROLE",
        },
    )
    assert bad_role.status_code == 422, bad_role.text
    bad_fk = client.post(
        "/api/optimization/inputs",
        json={
            "optimization_run_id": 999999,
            "planning_task_id": chain["task"]["id"],
            "input_role": "TASK",
        },
    )
    assert bad_fk.status_code == 404, bad_fk.text


def test_optimization_output_creation(client, db_session):
    chain = setup_chain(client, db_session)
    run = make_run(client).json()
    response = client.post(
        "/api/optimization/outputs",
        json={
            "optimization_run_id": run["id"],
            "planning_task_id": chain["task"]["id"],
            "candidate_block_window_id": chain["candidate"]["id"],
            "output_type": "WINDOW_ASSIGNMENT",
            "output_status": "PROPOSED",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["selected"] is False


def test_output_payload_jsonb(client, db_session):
    run = make_run(client).json()
    payload = {
        "model_metadata": {"framework": "future-engine", "n": 1},
        "arbitrary": [1, 2, {"nested": True}],
        "empty": None,
    }
    created = client.post(
        "/api/optimization/outputs",
        json={
            "optimization_run_id": run["id"],
            "output_type": "PLAN_METADATA",
            "output_status": "PROPOSED",
            "output_payload": payload,
        },
    )
    assert created.status_code == 201, created.text
    output_id = created.json()["id"]
    stored = client.get(f"/api/optimization/outputs/{output_id}").json()
    assert stored["output_payload"] == payload


def test_block_plan_creation(client, db_session):
    run = make_run(client).json()
    response = make_plan(client, optimization_run_id=run["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plan_code"] == "PLAN-1"
    assert body["status"] == "PROPOSED"
    assert body["plan_date"] == "2026-05-11"


def test_block_plan_uniqueness(client, db_session):
    assert make_plan(client).status_code == 201
    assert make_plan(client).status_code == 409
    bad_horizon = make_plan(
        client,
        code="PLAN-2",
        planning_horizon_start="2026-05-11T15:00:00",
        planning_horizon_end="2026-05-11T09:00:00",
    )
    assert bad_horizon.status_code == 422, bad_horizon.text


def test_block_plan_task_creation(client, db_session):
    chain = setup_chain(client, db_session)
    plan = make_plan(client).json()
    response = add_plan_task(
        client,
        plan["id"],
        chain["task"]["id"],
        chain["candidate"]["id"],
        "2026-05-11T10:00:00",
        "2026-05-11T12:00:00",
        120,
    )
    assert response.status_code == 201, response.text
    assert response.json()["sequence_number"] is None
    assert response.json()["status"] == "CONFIRMED"


def test_duplicate_plan_task_rejected(client, db_session):
    chain = setup_chain(client, db_session)
    plan = make_plan(client).json()
    first = add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T10:00:00", "2026-05-11T12:00:00", 120,
    )
    assert first.status_code == 201
    duplicate = add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T12:00:00", "2026-05-11T13:00:00", 60,
    )
    assert duplicate.status_code == 409, duplicate.text


def test_plan_validation_creation(client, db_session):
    plan = make_plan(client).json()
    response = client.post(
        "/api/optimization/validations",
        json={
            "block_plan_id": plan["id"],
            "validation_type": "GENERAL",
            "validation_status": "PASSED",
            "validation_message": "TEST/SYNTHETIC validation.",
            "validator_version": "TEST-1.0",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["validation_status"] == "PASSED"
    assert body["validated_at"] is not None


def test_deterministic_plan_validation(client, db_session):
    chain = setup_chain(client, db_session)
    plan = make_plan(client).json()
    add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T10:00:00", "2026-05-11T12:00:00", 120,
    )
    results = validate_results(client, plan["id"])
    window_fit = find_result(results, "WINDOW_FIT")
    assert window_fit and window_fit[0]["validation_status"] == "PASSED", results
    duration = find_result(results, "DURATION")
    assert any(r["validation_status"] == "PASSED" for r in duration), results
    stored = client.get(
        f"/api/optimization/validations?block_plan_id={plan['id']}"
    ).json()
    assert len(stored) == len(results)


def test_candidate_window_fit_validation(client, db_session):
    chain = setup_chain(client, db_session)
    plan = make_plan(client).json()
    add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T13:00:00", "2026-05-11T15:00:00", 120,
    )
    results = validate_results(client, plan["id"])
    window_fit = find_result(results, "WINDOW_FIT")
    assert window_fit and window_fit[0]["validation_status"] == "FAILED", results


def test_dependency_validation(client, db_session):
    chain = setup_chain(client, db_session)
    # second task on a new maintenance record (same asset, same station/line)
    _, _, maintenance_b = add_tms_chain(
        client, chain["asset"], "TMS-DF-002",
        "2026-05-11T09:00:00", "2026-05-11T12:00:00",
    )
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr_b = [
        m for m in requirements
        if m["source_record_type"] == "TMS_MAINTENANCE"
        and m["source_record_id"] == maintenance_b["id"]
    ][0]
    client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr_b["id"],
            "station_code": "STA-7",
            "line_number": "L7",
            "block_type": "INTEGRATED_BLOCK",
            "required_duration_minutes": 120,
            "power_block_required": False,
            "traffic_block_required": False,
            "status": "REQUIRED",
            "remarks": "TEST/SYNTHETIC block requirement B.",
        },
    )
    client.post("/api/planning/generate-tasks")
    tasks = client.get(
        f"/api/planning/tasks?maintenance_requirement_id={mr_b['id']}"
    ).json()
    task_b = tasks[0]
    dependency = client.post(
        "/api/planning/dependencies",
        json={
            "predecessor_task_id": chain["task"]["id"],
            "successor_task_id": task_b["id"],
            "dependency_type": "FINISH_TO_START",
            "lag_minutes": 0,
        },
    )
    assert dependency.status_code == 201, dependency.text

    plan = make_plan(client, code="PLAN-DEP").json()
    add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T10:00:00", "2026-05-11T11:00:00", 60,
    )
    add_plan_task(
        client, plan["id"], task_b["id"], None,
        "2026-05-11T10:30:00", "2026-05-11T12:00:00", 90,
    )
    results = validate_results(client, plan["id"])
    dependency_results = find_result(results, "DEPENDENCY")
    assert dependency_results, results
    assert dependency_results[0]["validation_status"] == "FAILED", results


def test_controller_decision_creation(client, db_session):
    plan = make_plan(client).json()
    response = client.post(
        "/api/optimization/decisions",
        json={
            "block_plan_id": plan["id"],
            "decision": "RETURNED_FOR_REVISION",
            "controller_code": "CTRL-1",
            "remarks": "TEST/SYNTHETIC controller decision.",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["decision"] == "RETURNED_FOR_REVISION"


def test_no_automatic_approval(client, db_session):
    plan = make_plan(client).json()
    client.post(
        "/api/optimization/decisions",
        json={
            "block_plan_id": plan["id"],
            "decision": "RETURNED_FOR_REVISION",
            "controller_code": "CTRL-1",
        },
    )
    unchanged = client.get(f"/api/optimization/plans/{plan['id']}").json()
    assert unchanged["status"] == "PROPOSED"
    decisions = client.get(
        f"/api/optimization/decisions?block_plan_id={plan['id']}"
    ).json()
    assert len(decisions) == 1 and decisions[0]["decision"] != "APPROVED"


def test_execution_outcome_creation(client, db_session):
    chain = setup_chain(client, db_session)
    plan = make_plan(client).json()
    plan_task = add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T10:00:00", "2026-05-11T12:00:00", 120,
    ).json()
    response = client.post(
        "/api/optimization/execution-outcomes",
        json={
            "block_plan_id": plan["id"],
            "block_plan_task_id": plan_task["id"],
            "execution_status": "COMPLETED",
            "actual_start": "2026-05-11T10:00:00",
            "actual_end": "2026-05-11T12:00:00",
            "actual_duration_minutes": 120,
            "outcome_code": "DONE",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["execution_status"] == "COMPLETED"
    assert body["recorded_at"] is not None
    listed = client.get(
        f"/api/optimization/execution-outcomes?block_plan_id={plan['id']}"
    ).json()
    assert len(listed) == 1 and listed[0]["block_plan_task_id"] == plan_task["id"]


def test_execution_duration_validation(client, db_session):
    plan = make_plan(client).json()
    bad_range = client.post(
        "/api/optimization/execution-outcomes",
        json={
            "block_plan_id": plan["id"],
            "execution_status": "COMPLETED",
            "actual_start": "2026-05-11T12:00:00",
            "actual_end": "2026-05-11T10:00:00",
        },
    )
    assert bad_range.status_code == 422, bad_range.text
    bad_duration = client.post(
        "/api/optimization/execution-outcomes",
        json={
            "block_plan_id": plan["id"],
            "execution_status": "COMPLETED",
            "actual_duration_minutes": -5,
        },
    )
    assert bad_duration.status_code == 422, bad_duration.text
    bad_plan = client.post(
        "/api/optimization/execution-outcomes",
        json={"block_plan_id": 999999, "execution_status": "NOT_STARTED"},
    )
    assert bad_plan.status_code == 404, bad_plan.text


def test_invalid_fk_handling(client, db_session):
    chain = setup_chain(client, db_session)
    run = make_run(client).json()
    bad_task = client.post(
        "/api/optimization/inputs",
        json={
            "optimization_run_id": run["id"],
            "planning_task_id": 999999,
            "input_role": "TASK",
        },
    )
    assert bad_task.status_code == 404, bad_task.text
    bad_window = client.post(
        "/api/optimization/outputs",
        json={
            "optimization_run_id": run["id"],
            "candidate_block_window_id": 999999,
            "output_type": "WINDOW_ASSIGNMENT",
            "output_status": "PROPOSED",
        },
    )
    assert bad_window.status_code == 404, bad_window.text
    bad_plan_fk = make_plan(client, optimization_run_id=999999)
    assert bad_plan_fk.status_code == 404, bad_plan_fk.text
    bad_decision = client.post(
        "/api/optimization/decisions",
        json={"block_plan_id": 999999, "decision": "APPROVED"},
    )
    assert bad_decision.status_code == 404, bad_decision.text
    bad_plan_task = add_plan_task(
        client, 999999, chain["task"]["id"], None,
        "2026-05-11T10:00:00", "2026-05-11T11:00:00", 60,
    )
    assert bad_plan_task.status_code == 404, bad_plan_task.text


def test_invalid_date_and_enum_handling(client, db_session):
    bad_enum = make_run(client, run_type="NOT_A_TYPE")
    assert bad_enum.status_code == 422, bad_enum.text
    bad_status = make_plan(client, status="NOPE")
    assert bad_status.status_code == 422, bad_status.text
    bad_task_range = add_plan_task(
        client, 1, 1, None,
        "2026-05-11T12:00:00", "2026-05-11T10:00:00", 60,
    )
    assert bad_task_range.status_code == 422, bad_task_range.text
    bad_duration = add_plan_task(
        client, 1, 1, None,
        "2026-05-11T10:00:00", "2026-05-11T11:00:00", 0,
    )
    assert bad_duration.status_code == 422, bad_duration.text
    bad_decision = client.post(
        "/api/optimization/decisions",
        json={"block_plan_id": 1, "decision": "MAYBE"},
    )
    assert bad_decision.status_code == 422, bad_decision.text


def test_on_delete_restrict(db_session):
    metadata = Base.metadata
    expected = {
        "optimization_input": {
            "optimization_run_id": "optimization_run",
            "planning_task_id": "planning_task",
            "candidate_block_window_id": "candidate_block_window",
            "planning_constraint_id": "planning_constraint",
            "planning_resource_id": "planning_resource",
            "task_dependency_id": "task_dependency",
        },
        "optimization_output": {
            "optimization_run_id": "optimization_run",
            "planning_task_id": "planning_task",
            "candidate_block_window_id": "candidate_block_window",
        },
        "block_plan": {"optimization_run_id": "optimization_run"},
        "block_plan_task": {
            "block_plan_id": "block_plan",
            "planning_task_id": "planning_task",
            "candidate_block_window_id": "candidate_block_window",
        },
        "plan_validation": {"block_plan_id": "block_plan"},
        "controller_decision": {"block_plan_id": "block_plan"},
        "execution_outcome": {
            "block_plan_id": "block_plan",
            "block_plan_task_id": "block_plan_task",
        },
    }
    for table_name, columns in expected.items():
        table = metadata.tables[table_name]
        for column_name, referred in columns.items():
            fk = list(table.columns[column_name].foreign_keys)[0]
            assert fk.target_fullname == f"{referred}.id", (table_name, column_name)
            assert fk.ondelete == "RESTRICT", (table_name, column_name, fk.ondelete)


def test_provenance(client, db_session):
    chain = setup_chain(client, db_session)
    run = make_run(client).json()
    input_row = client.post(
        "/api/optimization/inputs",
        json={
            "optimization_run_id": run["id"],
            "planning_task_id": chain["task"]["id"],
            "candidate_block_window_id": chain["candidate"]["id"],
            "input_role": "CANDIDATE_WINDOW",
        },
    ).json()
    output_row = client.post(
        "/api/optimization/outputs",
        json={
            "optimization_run_id": run["id"],
            "planning_task_id": chain["task"]["id"],
            "candidate_block_window_id": chain["candidate"]["id"],
            "output_type": "WINDOW_ASSIGNMENT",
            "output_status": "PROPOSED",
        },
    ).json()
    plan = make_plan(client, optimization_run_id=run["id"]).json()
    plan_task = add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T10:00:00", "2026-05-11T12:00:00", 120,
    ).json()
    client.post(
        "/api/optimization/validations",
        json={
            "block_plan_id": plan["id"],
            "validation_type": "WINDOW_FIT",
            "validation_status": "PASSED",
        },
    )
    client.post(
        "/api/optimization/decisions",
        json={"block_plan_id": plan["id"], "decision": "APPROVED"},
    )
    outcome = client.post(
        "/api/optimization/execution-outcomes",
        json={
            "block_plan_id": plan["id"],
            "block_plan_task_id": plan_task["id"],
            "execution_status": "COMPLETED",
            "actual_start": "2026-05-11T10:00:00",
            "actual_end": "2026-05-11T12:00:00",
            "actual_duration_minutes": 120,
        },
    ).json()

    db = db_session
    stored_input = db.get(OptimizationInput, input_row["id"])
    assert stored_input.optimization_run_id == run["id"]
    assert stored_input.candidate_block_window.candidate_start is not None
    assert stored_input.planning_task.maintenance_requirement.id == chain["mr"]["id"]
    assert (
        stored_input.planning_task.maintenance_requirement.defect_failure.source_record_id
        == chain["defect"]["id"]
    )
    stored_output = db.get(OptimizationOutput, output_row["id"])
    assert stored_output.candidate_block_window.id == chain["candidate"]["id"]
    stored_plan = db.get(BlockPlan, plan["id"])
    assert stored_plan.optimization_run_id == run["id"]
    stored_plan_task = db.get(BlockPlanTask, plan_task["id"])
    assert stored_plan_task.planning_task_id == chain["task"]["id"]
    assert stored_plan_task.candidate_block_window_id == chain["candidate"]["id"]
    assert db.get(PlanValidation, 1).block_plan_id == plan["id"]
    assert db.get(ControllerDecision, 1).block_plan_id == plan["id"]
    stored_outcome = db.get(ExecutionOutcome, outcome["id"])
    assert stored_outcome.block_plan_id == plan["id"]
    assert stored_outcome.block_plan_task_id == plan_task["id"]


def test_ai_contract(client, db_session):
    chain = setup_chain(client, db_session)
    run = make_run(client).json()
    for role, ref, value in (
        ("TASK", "planning_task_id", chain["task"]["id"]),
        ("CANDIDATE_WINDOW", "candidate_block_window_id", chain["candidate"]["id"]),
    ):
        response = client.post(
            "/api/optimization/inputs",
            json={
                "optimization_run_id": run["id"],
                ref: value,
                "input_role": role,
            },
        )
        assert response.status_code == 201, response.text
    metadata = {
        "features": {"custom": [1, 2, 3]},
        "model_specific": "anything",
        "nested": {"deep": {"ok": True}},
    }
    output = client.post(
        "/api/optimization/outputs",
        json={
            "optimization_run_id": run["id"],
            "output_type": "PLAN_METADATA",
            "output_status": "UNASSIGNED",
            "selected": True,
            "output_payload": metadata,
        },
    )
    assert output.status_code == 201, output.text
    assert client.get(
        f"/api/optimization/outputs/{output.json()['id']}"
    ).json()["output_payload"] == metadata
    inputs = client.get(
        f"/api/optimization/inputs?optimization_run_id={run['id']}"
    ).json()
    assert len(inputs) == 2


def test_optimization_input_all_roles(client, db_session):
    chain = setup_chain(client, db_session)
    run = make_run(client).json()
    constraint = client.post(
        "/api/planning/constraints",
        json={
            "planning_task_id": chain["task"]["id"],
            "constraint_type": "MAX_DURATION",
            "constraint_value": "240",
            "hard_constraint": True,
        },
    )
    assert constraint.status_code == 201, constraint.text
    resource = client.post(
        "/api/planning/resources",
        json={
            "resource_code": "STEP10-RES-1",
            "resource_type": "ENGINEERING_TEAM",
            "resource_name": "TEST/SYNTHETIC engineering team",
            "status": "AVAILABLE",
        },
    )
    assert resource.status_code == 201, resource.text
    payloads = [
        ("CONSTRAINT", {"planning_constraint_id": constraint.json()["id"]}),
        ("RESOURCE", {"planning_resource_id": resource.json()["id"]}),
    ]
    for role, reference in payloads:
        response = client.post(
            "/api/optimization/inputs",
            json={
                "optimization_run_id": run["id"],
                "input_role": role,
                **reference,
            },
        )
        assert response.status_code == 201, response.text
    for role, _ in payloads:
        listing = client.get(
            f"/api/optimization/inputs?optimization_run_id={run['id']}&input_role={role}"
        ).json()
        assert len(listing) == 1 and listing[0]["input_role"] == role


def test_plan_validation_does_not_change_status(client, db_session):
    from app.services.plan_validation import VALIDATOR_VERSION

    chain = setup_chain(client, db_session)
    plan = make_plan(client).json()
    add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T10:00:00", "2026-05-11T12:00:00", 120,
    )
    results = validate_results(client, plan["id"])
    assert results
    unchanged = client.get(f"/api/optimization/plans/{plan['id']}").json()
    assert unchanged["status"] == "PROPOSED"
    assert all(r["validator_version"] == VALIDATOR_VERSION for r in results)
    assert client.get(
        f"/api/optimization/decisions?block_plan_id={plan['id']}"
    ).json() == []


def test_no_ai_algorithm_execution(client, db_session):
    for table_name in STEP10_TABLES:
        columns = {c["name"].lower() for c in inspect(db_session.bind).get_columns(table_name)}
        for column in columns:
            for token in FORBIDDEN_TOKENS:
                assert token not in column, f"{table_name}.{column} contains {token}"

    from app.services import plan_validation

    forbidden_functions = [
        "run_optimizer",
        "optimize_plan",
        "find_best_plan",
        "rank_candidates",
        "select_best_window",
    ]
    for name in forbidden_functions:
        assert not hasattr(plan_validation, name), name


def test_source_data_integrity(client, db_session):
    chain = setup_chain(client, db_session)
    tables = {
        "source_system": None,
        "tms_inspection": None,
        "tms_defect": None,
        "tms_maintenance": None,
        "defect_failure": None,
        "maintenance_requirement": None,
        "block_requirement": None,
        "planning_task": PlanningTask,
        "candidate_block_window": CandidateBlockWindow,
        "available_window": AvailableWindow,
    }
    from app.models.defect_failure import DefectFailure
    from app.models.maintenance_requirement import MaintenanceRequirement
    from app.models.source_system import SourceSystem
    from app.models.tms_defect import TMSDefect
    from app.models.tms_inspection import TMSInspection
    from app.models.tms_maintenance import TMSMaintenance
    from app.models.block_requirement import BlockRequirement

    tables.update(
        {
            "source_system": SourceSystem,
            "tms_inspection": TMSInspection,
            "tms_defect": TMSDefect,
            "tms_maintenance": TMSMaintenance,
            "defect_failure": DefectFailure,
            "maintenance_requirement": MaintenanceRequirement,
            "block_requirement": BlockRequirement,
        }
    )
    from sqlalchemy import func

    before = {
        name: db_session.scalar(select(func.count()).select_from(model))
        for name, model in tables.items()
    }

    run = make_run(client).json()
    client.post(
        "/api/optimization/inputs",
        json={
            "optimization_run_id": run["id"],
            "planning_task_id": chain["task"]["id"],
            "candidate_block_window_id": chain["candidate"]["id"],
            "input_role": "TASK",
        },
    )
    client.post(
        "/api/optimization/outputs",
        json={
            "optimization_run_id": run["id"],
            "output_type": "TASK_ASSIGNMENT",
            "output_status": "PROPOSED",
            "output_payload": {"x": 1},
        },
    )
    plan = make_plan(client).json()
    add_plan_task(
        client, plan["id"], chain["task"]["id"], chain["candidate"]["id"],
        "2026-05-11T10:00:00", "2026-05-11T12:00:00", 120,
    )
    client.post(
        "/api/optimization/validations",
        json={
            "block_plan_id": plan["id"],
            "validation_type": "GENERAL",
            "validation_status": "PASSED",
        },
    )
    client.post(
        "/api/optimization/decisions",
        json={"block_plan_id": plan["id"], "decision": "APPROVED"},
    )
    client.post(
        "/api/optimization/execution-outcomes",
        json={"block_plan_id": plan["id"], "execution_status": "NOT_STARTED"},
    )

    after = {
        name: db_session.scalar(select(func.count()).select_from(model))
        for name, model in tables.items()
    }
    assert after == before, (before, after)