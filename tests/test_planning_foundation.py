from sqlalchemy import func, inspect, select

from app.models.available_window import AvailableWindow
from app.models.block_requirement import BlockRequirement
from app.models.defect_failure import DefectFailure
from app.models.maintenance_requirement import MaintenanceRequirement
from app.models.planning_constraint import PlanningConstraint
from app.models.planning_resource import PlanningResource
from app.models.planning_task import PlanningTask
from app.models.task_dependency import TaskDependency
from app.models.task_resource import TaskResource

FORBIDDEN_COLUMNS = {
    "priority_score",
    "risk_score",
    "predicted_failure",
    "recommended_block",
    "optimization_score",
    "optimization_run",
    "optimization_input",
    "optimization_output",
    "candidate_block",
    "candidate_block_window",
    "planned_block",
    "plan_validation",
    "validation_result",
    "controller_decision",
    "execution_outcome",
    "block_plan",
    "block_plan_task",
    "ai_recommendation",
    "optimized_schedule",
}


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
            "source_asset_id": f"{suffix}-PLAN-ASSET",
            "asset_type": "TEST/SYNTHETIC",
            "asset_name": f"TEST/SYNTHETIC {suffix} Asset",
            "status": "TEST",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_tms_chain(client):
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
    maintenance = client.post(
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
    return source, asset, inspection, defect, maintenance


def create_tdms_chain(client):
    source = create_source(client, "TDMS")
    asset = create_asset(client, source, "TDMS")
    inspection = client.post(
        "/api/tdms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": "2026-05-02T10:00:00",
            "inspection_type": "SONIC",
            "parameter_code": "RAIL-DEFECT",
            "parameter_value": "ANOMALY",
            "remarks": "TEST/SYNTHETIC TDMS inspection.",
        },
    ).json()
    failure = client.post(
        "/api/tdms/failures",
        json={
            "asset_id": asset["id"],
            "inspection_id": inspection["id"],
            "failure_code": "TDMS-F-001",
            "failure_description": "TEST/SYNTHETIC TDMS failure detected.",
            "severity": "MEDIUM",
            "failure_date": "2026-05-02T10:40:00",
            "status": "OPEN",
            "rectification_date": None,
            "remarks": "TEST/SYNTHETIC TDMS failure remarks.",
        },
    ).json()
    maintenance = client.post(
        "/api/tdms/maintenance",
        json={
            "asset_id": asset["id"],
            "failure_id": failure["id"],
            "maintenance_type": "REPAIR",
            "planned_date": "2026-05-12T09:00:00",
            "start_date": "2026-05-12T09:00:00",
            "end_date": "2026-05-12T12:00:00",
            "status": "PLANNED",
            "remarks": "TEST/SYNTHETIC TDMS maintenance record.",
        },
    ).json()
    return source, asset, inspection, failure, maintenance


def find_by_type(records, record_type):
    return [r for r in records if r["source_record_type"] == record_type][0]


def create_generated_tms_task(client, with_block=True):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")
    block = None
    if with_block:
        block = client.post(
            "/api/unified/block-requirements",
            json={
                "maintenance_requirement_id": mr["id"],
                "station_code": "STA-7",
                "line_number": "L7",
                "block_type": "INTEGRATED_BLOCK",
                "required_duration_minutes": 120,
                "earliest_start": "2026-05-11T00:00:00",
                "latest_end": "2026-05-11T23:59:59",
                "power_block_required": True,
                "traffic_block_required": True,
                "resource_notes": "TEST/SYNTHETIC resource note.",
                "status": "REQUIRED",
                "remarks": "TEST/SYNTHETIC block requirement.",
            },
).json()
    summary = client.post("/api/planning/generate-tasks").json()
    tasks = client.get("/api/planning/tasks").json()
    task = tasks[0]
    return source, asset, defect, maintenance, mr, block, summary, task


def create_manual_constraint(client, planning_task_id):
    response = client.post(
        "/api/planning/constraints",
        json={
            "planning_task_id": planning_task_id,
            "constraint_type": "OPERATIONAL",
            "constraint_value": "WORK-ONLY-AT-NIGHT",
            "hard_constraint": True,
            "description": "TEST/SYNTHETIC operational constraint.",
"source": "TEST",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_planning_task_from_requirement(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    assert summary["processed"] == 1
    assert summary["created"] == 1
    assert task["maintenance_requirement_id"] == mr["id"]
    assert task["asset_id"] == asset["id"]
    assert task["block_requirement_id"] == block["id"]
    assert task["duration_minutes"] == 150
    assert task["status"] == "OPEN"
    assert task["task_type"] == "REPLACEMENT"
    assert task["earliest_start"] == "2026-05-11T00:00:00"
    assert task["latest_end"] == "2026-05-11T23:59:59"
    assert task["location_code"] == "STA-7"


def test_get_planning_task(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    single = client.get(f"/api/planning/tasks/{task['id']}")
    assert single.status_code == 200
    assert single.json()["id"] == task["id"]

    by_mr = client.get(f"/api/planning/tasks?maintenance_requirement_id={mr['id']}")
    assert by_mr.status_code == 200
    assert len(by_mr.json()) == 1

    by_asset = client.get(f"/api/planning/tasks?asset_id={asset['id']}")
    assert len(by_asset.json()) == 1

    by_status = client.get("/api/planning/tasks?status=OPEN")
    assert len(by_status.json()) == 1


def test_task_provenance_preserved(client, db_session):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    row = db_session.execute(
        select(PlanningTask, MaintenanceRequirement, DefectFailure)
        .join(MaintenanceRequirement, MaintenanceRequirement.id == PlanningTask.maintenance_requirement_id)
        .join(DefectFailure, DefectFailure.id == MaintenanceRequirement.defect_failure_id)
        .where(PlanningTask.id == task["id"])
    ).first()
    assert row[0].asset_id == asset["id"]
    assert row[1].source_system_id == source["id"]
    assert row[1].source_record_type == "TMS_MAINTENANCE"
    assert row[1].source_record_id == maint["id"]
    assert row[2].source_record_type == "TMS_DEFECT"
    assert row[2].source_record_id == defect["id"]


def test_block_requirement_linkage_preserved(client, db_session):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    db_task = db_session.get(PlanningTask, task["id"])
    assert db_task.block_requirement_id == block["id"]
    assert db_task.earliest_start is not None
    assert db_task.latest_end is not None


def test_deterministic_task_generation(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    tasks = client.get("/api/planning/tasks").json()
    assert tasks[0]["task_code"] == f"PT-{mr['id']:06d}"
    assert tasks[0]["task_type"] == "REPLACEMENT"
    assert tasks[0]["duration_minutes"] == 150


def test_idempotent_task_generation(client, db_session):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    second = client.post("/api/planning/generate-tasks").json()
    assert second["created"] == 0
    assert second["skipped"] == summary["processed"]
    count = db_session.scalar(select(func.count()).select_from(PlanningTask))
    assert count == 1


def test_generate_constraints(client, db_session):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    result = client.post("/api/planning/generate-constraints").json()
    assert result["processed"] == 1
    assert result["created"] == 6
    count = db_session.scalar(select(func.count()).select_from(PlanningConstraint))
    assert count == 6
    constraints = client.get(
        f"/api/planning/constraints?planning_task_id={task['id']}"
    ).json()
    assert len(constraints) == 6


def test_constraint_generation_derivations(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    client.post("/api/planning/generate-constraints")
    constraints = client.get(
        f"/api/planning/constraints?planning_task_id={task['id']}"
    ).json()

    types = {c["constraint_type"]: c["constraint_value"] for c in constraints}
    assert types["DURATION"] == "120"
    assert "2026-05-11T00:00:00" in types["TIME_WINDOW"]
    assert "2026-05-11T23:59:59" in types["TIME_WINDOW"]
    assert types["LOCATION"] == "STA-7"
    assert types["LINE"] == "L7"
    assert types["POWER_BLOCK"] == "TRUE"
    assert types["TRAFFIC_BLOCK"] == "TRUE"
    assert all(c["hard_constraint"] is True for c in constraints)


def test_manual_constraint_creation_and_filter(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    constraint = create_manual_constraint(client, task["id"])
    by_type = client.get(
        f"/api/planning/constraints?constraint_type=OPERATIONAL"
    ).json()
    assert len(by_type) == 1
    by_hard = client.get("/api/planning/constraints?hard_constraint=true").json()
    assert len(by_hard) >= 1
    single = client.get(f"/api/planning/constraints/{constraint['id']}")
    assert single.status_code == 200
    assert single.json()["constraint_value"] == "WORK-ONLY-AT-NIGHT"

def test_planning_resource_crud(client):
    response = client.post(
        "/api/planning/resources",
        json={
            "resource_code": "RES-700",
            "resource_type": "TEAM",
            "resource_name": "TEST/SYNTHETIC Team",
            "description": "TEST/SYNTHETIC planning team.",
            "capacity": 6,
            "unit": "persons",
            "status": "AVAILABLE",
            "location_code": "STA-7",
        },
    )
    assert response.status_code == 201
    resource = response.json()
    assert resource["resource_code"] == "RES-700"

    single = client.get(f"/api/planning/resources/{resource['id']}")
    assert single.status_code == 200

    by_type = client.get("/api/planning/resources?resource_type=TEAM")
    assert len(by_type.json()) == 1

    by_status = client.get("/api/planning/resources?status=AVAILABLE")
    assert len(by_status.json()) == 1

    by_location = client.get("/api/planning/resources?location_code=STA-7")
    assert len(by_location.json()) == 1


def test_duplicate_resource_code_rejected(client):
    payload = {
        "resource_code": "RES-DUP",
        "resource_type": "MACHINE",
        "resource_name": "TEST/SYNTHETIC Machine",
        "status": "AVAILABLE",
    }
    first = client.post("/api/planning/resources", json=payload)
    assert first.status_code == 201
    second = client.post("/api/planning/resources", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Planning resource code already exists"


def test_task_resource_relation(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    resource = client.post(
        "/api/planning/resources",
        json={
            "resource_code": "RES-701",
            "resource_type": "PERSONNEL",
            "resource_name": "TEST/SYNTHETIC Crew",
            "status": "AVAILABLE",
        },
    ).json()
    link = client.post(
        "/api/planning/task-resources",
        json={
            "planning_task_id": task["id"],
            "planning_resource_id": resource["id"],
            "required_quantity": 3,
            "allocation_status": "REQUIRED",
            "remarks": "TEST/SYNTHETIC task resource link.",
        },
    )
    assert link.status_code == 201
    link = link.json()
    assert link["required_quantity"] == 3

    single = client.get(f"/api/planning/task-resources/{link['id']}")
    assert single.status_code == 200

    by_task = client.get(f"/api/planning/task-resources?planning_task_id={task['id']}")
    assert len(by_task.json()) == 1

    by_resource = client.get(
        f"/api/planning/task-resources?planning_resource_id={resource['id']}"
    )
    assert len(by_resource.json()) == 1


def test_duplicate_task_resource_rejected(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    resource = client.post(
        "/api/planning/resources",
        json={
            "resource_code": "RES-702",
            "resource_type": "MATERIAL",
            "resource_name": "TEST/SYNTHETIC Material",
            "status": "AVAILABLE",
        },
    ).json()
    payload = {
        "planning_task_id": task["id"],
        "planning_resource_id": resource["id"],
        "required_quantity": 1,
        "allocation_status": "REQUIRED",
    }
    first = client.post("/api/planning/task-resources", json=payload)
    assert first.status_code == 201
    second = client.post("/api/planning/task-resources", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Task resource link already exists"


def test_task_dependency_creation(client):
    _, _, _, _, mr1, block1, _, task1 = create_generated_tms_task(client)
    source2, asset2, insp2, failure2, maint2 = create_tdms_chain(client)
    client.post("/api/unified/normalize/tdms")
    requirements = client.get("/api/unified/maintenance").json()
    mr2 = find_by_type(requirements, "TDMS_MAINTENANCE")
    client.post("/api/planning/generate-tasks")
    tasks = client.get("/api/planning/tasks").json()
    task2 = [t for t in tasks if t["maintenance_requirement_id"] == mr2["id"]][0]

    response = client.post(
        "/api/planning/dependencies",
        json={
            "predecessor_task_id": task1["id"],
            "successor_task_id": task2["id"],
            "dependency_type": "FINISH_TO_START",
            "lag_minutes": 15,
            "description": "TEST/SYNTHETIC task dependency.",
        },
    )
    assert response.status_code == 201
    dependency = response.json()
    assert dependency["predecessor_task_id"] == task1["id"]
    assert dependency["successor_task_id"] == task2["id"]

    single = client.get(f"/api/planning/dependencies/{dependency['id']}")
    assert single.status_code == 200

    by_pred = client.get(
        f"/api/planning/dependencies?predecessor_task_id={task1['id']}"
    )
    assert len(by_pred.json()) == 1

    by_succ = client.get(
        f"/api/planning/dependencies?successor_task_id={task2['id']}"
    )
    assert len(by_succ.json()) == 1


def test_self_dependency_rejected(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    response = client.post(
        "/api/planning/dependencies",
        json={
            "predecessor_task_id": task["id"],
            "successor_task_id": task["id"],
            "dependency_type": "FINISH_TO_START",
        },
    )
    assert response.status_code == 422


def test_duplicate_dependency_rejected(client):
    _, _, _, _, mr1, block1, _, task1 = create_generated_tms_task(client)
    source2, asset2, insp2, failure2, maint2 = create_tdms_chain(client)
    client.post("/api/unified/normalize/tdms")
    requirements = client.get("/api/unified/maintenance").json()
    mr2 = find_by_type(requirements, "TDMS_MAINTENANCE")
    client.post("/api/planning/generate-tasks")
    tasks = client.get("/api/planning/tasks").json()
    task2 = [t for t in tasks if t["maintenance_requirement_id"] == mr2["id"]][0]

    payload = {
        "predecessor_task_id": task1["id"],
        "successor_task_id": task2["id"],
        "dependency_type": "FINISH_TO_START",
    }
    first = client.post("/api/planning/dependencies", json=payload)
    assert first.status_code == 201
    second = client.post("/api/planning/dependencies", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Task dependency already exists"

def test_invalid_fk_rejected(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    bad_constraint = client.post(
        "/api/planning/constraints",
        json={
            "planning_task_id": 999999,
            "constraint_type": "OPERATIONAL",
            "constraint_value": "X",
        },
    )
    assert bad_constraint.status_code == 404
    assert bad_constraint.json()["detail"] == "Planning task not found"

    bad_link = client.post(
        "/api/planning/task-resources",
        json={
            "planning_task_id": task["id"],
            "planning_resource_id": 999999,
            "required_quantity": 1,
            "allocation_status": "REQUIRED",
        },
    )
    assert bad_link.status_code == 404
    assert bad_link.json()["detail"] == "Planning resource not found"

    bad_dep_succ = client.post(
        "/api/planning/dependencies",
        json={
            "predecessor_task_id": task["id"],
            "successor_task_id": 999999,
            "dependency_type": "FINISH_TO_START",
        },
)
    assert bad_dep_succ.status_code == 404
    assert bad_dep_succ.json()["detail"] == "Successor planning task not found"

    source2, asset2, insp2, failure2, maint2 = create_tdms_chain(client)
    client.post("/api/unified/normalize/tdms")
    client.post("/api/planning/generate-tasks")
    tasks = client.get("/api/planning/tasks").json()
    task_nb = [t for t in tasks if t["asset_id"] == asset2["id"]][0]
    assert task_nb["block_requirement_id"] is None
    assert task_nb["duration_minutes"] == 180
    assert task_nb["location_code"] is None


def test_invalid_duration_not_invented(client, db_session):
    source = create_source(client, "TMS")
    asset = create_asset(client, source, "TMS")
    inspection = client.post(
        "/api/tms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": "2026-06-01T10:00:00",
            "inspection_type": "USFD",
            "parameter_code": "P1",
            "parameter_value": "1.0",
            "remarks": "TEST/SYNTHETIC no-duration inspection.",
        },
    ).json()
    defect = client.post(
        "/api/tms/defects",
        json={
            "asset_id": asset["id"],
            "inspection_id": inspection["id"],
            "defect_code": "TMS-DF-ND",
            "defect_description": "TEST/SYNTHETIC defect without duration.",
            "severity": "LOW",
            "detected_date": "2026-06-01T10:30:00",
            "status": "OPEN",
        },
    ).json()
    maintenance = client.post(
        "/api/tms/maintenance",
        json={
            "asset_id": asset["id"],
            "defect_id": defect["id"],
            "maintenance_type": "INSPECTION",
            "status": "PLANNED",
            "remarks": "No start/end dates supplied.",
        },
    ).json()
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")
    assert mr["required_duration_minutes"] is None

    summary = client.post("/api/planning/generate-tasks").json()
    assert summary["created"] == 0
    assert summary["skipped"] == 1
    count = db_session.scalar(select(func.count()).select_from(PlanningTask))
    assert count == 0

    bad_resource = client.post(
        "/api/planning/resources",
        json={
            "resource_code": "RES-NEG",
            "resource_type": "OTHER",
            "resource_name": "TEST/SYNTHETIC negative capacity",
            "capacity": -1,
            "status": "AVAILABLE",
        },
    )
    assert bad_resource.status_code == 422


def test_invalid_time_range_rejected(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    response = client.post(
        "/api/planning/constraints",
        json={
            "planning_task_id": task["id"],
            "constraint_type": "TIME_WINDOW",
            "constraint_value": "NIGHT-WINDOW",
            "effective_start": "2026-05-11T23:00:00",
            "effective_end": "2026-05-11T22:00:00",
        },
    )
    assert response.status_code == 422


def test_invalid_quantity_rejected(client):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    resource = client.post(
        "/api/planning/resources",
        json={
            "resource_code": "RES-703",
            "resource_type": "VEHICLE",
            "resource_name": "TEST/SYNTHETIC Vehicle",
            "status": "AVAILABLE",
        },
    ).json()
    zero = client.post(
        "/api/planning/task-resources",
        json={
            "planning_task_id": task["id"],
            "planning_resource_id": resource["id"],
            "required_quantity": 0,
            "allocation_status": "REQUIRED",
        },
    )
    assert zero.status_code == 422

    negative = client.post(
        "/api/planning/task-resources",
        json={
            "planning_task_id": task["id"],
            "planning_resource_id": resource["id"],
            "required_quantity": -2,
            "allocation_status": "REQUIRED",
        },
    )
    assert negative.status_code == 422


def test_source_unified_records_unchanged(client, db_session):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    counts = {}
    for model in (BlockRequirement, MaintenanceRequirement, DefectFailure):
        counts[model.__tablename__] = db_session.scalar(
            select(func.count()).select_from(model)
        )
    before_task = client.get("/api/planning/tasks").json()

    client.post("/api/planning/generate-constraints")
    client.post("/api/planning/generate-tasks")

    for table, count in counts.items():
        model = next(m for m in (BlockRequirement, MaintenanceRequirement, DefectFailure) if m.__tablename__ == table)
        actual = db_session.scalar(select(func.count()).select_from(model))
        assert actual == count, f"{table} changed: {count} -> {actual}"
    after_task = client.get("/api/planning/tasks").json()
    assert after_task == before_task


def test_existing_available_window_unchanged(client, db_session):
    coa = create_source(client, "COA")
    train = client.post(
        "/api/coa/trains",
        json={
            "train_id": "PLAN-COA-TRN-001",
            "train_number": "7788",
            "train_name": "TEST/SYNTHETIC COA Train",
            "direction": "UP",
            "source_system_id": coa["id"],
        },
    ).json()
    for start, end in (
        ("2026-05-01T10:00:00", "2026-05-01T10:20:00"),
        ("2026-05-01T10:40:00", "2026-05-01T11:00:00"),
    ):
        client.post(
            "/api/coa/line-occupancy",
            json={
                "station_code": "STA-9",
                "line_number": "L9",
                "occupancy_start": start,
                "occupancy_end": end,
                "occupancy_status": "OCCUPIED",
                "train_id": train["id"],
                "source_event_id": f"PLAN-SRC-{start}",
            },
        )
    generated = client.post("/api/coa/available-windows/generate")
    assert generated.status_code == 200
    before = client.get("/api/coa/available-windows").json()

    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    client.post("/api/planning/generate-constraints")

    after = client.get("/api/coa/available-windows").json()
    assert after == before
    count = db_session.scalar(select(func.count()).select_from(AvailableWindow))
    assert count == 1


def test_no_ai_optimization_fields_exist(db_session):
    inspector = inspect(db_session.bind)
    for table in (
        "planning_task",
        "planning_constraint",
        "planning_resource",
        "task_resource",
        "task_dependency",
    ):
        columns = {col["name"] for col in inspector.get_columns(table)}
        assert columns.isdisjoint(FORBIDDEN_COLUMNS), (
            f"{table} contains forbidden AI/planning columns: "
            f"{columns & FORBIDDEN_COLUMNS}"
        )


def test_full_planning_provenance(client, db_session):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    resource = client.post(
        "/api/planning/resources",
        json={
            "resource_code": "RES-704",
            "resource_type": "TEAM",
            "resource_name": "TEST/SYNTHETIC Team",
            "status": "AVAILABLE",
        },
    ).json()
    client.post("/api/planning/task-resources", json={
        "planning_task_id": task["id"],
        "planning_resource_id": resource["id"],
        "required_quantity": 2,
        "allocation_status": "REQUIRED",
    })

    source2, asset2, insp2, failure2, maint2 = create_tdms_chain(client)
    client.post("/api/unified/normalize/tdms")
    requirements = client.get("/api/unified/maintenance").json()
    mr2 = find_by_type(requirements, "TDMS_MAINTENANCE")
    client.post("/api/planning/generate-tasks")
    tasks = client.get("/api/planning/tasks").json()
    task2 = [t for t in tasks if t["maintenance_requirement_id"] == mr2["id"]][0]
    client.post("/api/planning/dependencies", json={
        "predecessor_task_id": task["id"],
        "successor_task_id": task2["id"],
        "dependency_type": "FINISH_TO_START",
        "lag_minutes": 10,
    })

    chain = db_session.execute(
        select(
            TaskDependency, PlanningTask, BlockRequirement,
            MaintenanceRequirement, TaskResource, PlanningResource,
        )
        .join(PlanningTask, PlanningTask.id == TaskDependency.predecessor_task_id)
        .join(BlockRequirement, BlockRequirement.id == PlanningTask.block_requirement_id)
        .join(MaintenanceRequirement, MaintenanceRequirement.id == PlanningTask.maintenance_requirement_id)
        .join(TaskResource, TaskResource.planning_task_id == PlanningTask.id)
        .join(PlanningResource, PlanningResource.id == TaskResource.planning_resource_id)
        .where(TaskDependency.id == 1)
    ).first()
    assert chain is not None
    assert chain[0].predecessor_task_id == task["id"]
    assert chain[0].successor_task_id == task2["id"]
    assert chain[1].block_requirement_id == block["id"]
    assert chain[2].maintenance_requirement_id == mr["id"]
    assert chain[4].planning_resource_id == resource["id"]
    assert chain[5].resource_code == "RES-704"

    task2_row = db_session.execute(
        select(PlanningTask, MaintenanceRequirement)
        .join(MaintenanceRequirement, MaintenanceRequirement.id == PlanningTask.maintenance_requirement_id)
        .where(PlanningTask.id == task2["id"])
    ).first()
    assert task2_row[1].source_record_type == "TDMS_MAINTENANCE"
    assert task2_row[1].source_record_id == maint2["id"]
    assert task2_row[0].asset_id == asset2["id"]

    assert db_session.get(PlanningTask, task["id"]).asset_id == asset["id"]
    assert db_session.get(BlockRequirement, block["id"]).id == block["id"]


def test_planning_generation_idempotent_constraints(client, db_session):
    source, asset, defect, maint, mr, block, summary, task = (
        create_generated_tms_task(client)
    )
    first = client.post("/api/planning/generate-constraints").json()
    second = client.post("/api/planning/generate-constraints").json()
    assert first["created"] == 6
    assert second["created"] == 0
    assert second["skipped"] == first["created"]
    count = db_session.scalar(select(func.count()).select_from(PlanningConstraint))
    assert count == 6
