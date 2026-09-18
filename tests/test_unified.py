from sqlalchemy import func, inspect, select

from app.models.available_window import AvailableWindow
from app.models.block_requirement import BlockRequirement
from app.models.defect_failure import DefectFailure
from app.models.maintenance_requirement import MaintenanceRequirement
from app.models.smms_alert import SMMSAlert
from app.models.smms_maintenance import SMMSMaintenance
from app.models.tdms_failure import TDMSFailure
from app.models.tdms_maintenance import TDMSMaintenance
from app.models.tms_defect import TMSDefect
from app.models.tms_maintenance import TMSMaintenance

FORBIDDEN_COLUMNS = {
    "priority_score",
    "risk_score",
    "predicted_failure",
    "recommended_block",
    "optimization_score",
    "optimized_schedule",
    "candidate_block",
    "candidate_block_window",
    "optimization_run",
    "optimization_input",
    "optimization_output",
    "planned_block",
    "block_plan",
    "block_plan_task",
    "plan_validation",
    "controller_decision",
    "execution_outcome",
    "validation_result",
    "planning_task",
    "planning_constraint",
    "task_resource",
    "planning_resource",
    "task_dependency",
    "ai_recommendation",
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
            "source_asset_id": f"{suffix}-TEST-ASSET",
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


def create_smms_chain(client):
    source = create_source(client, "SMMS")
    asset = create_asset(client, source, "SMMS")
    inspection = client.post(
        "/api/smms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": "2026-05-03T10:00:00",
            "inspection_type": "Point Machine Inspection",
            "parameter_code": "POINT-STROKE",
            "parameter_value": "NORMAL",
            "remarks": "TEST/SYNTHETIC SMMS inspection.",
        },
    ).json()
    alert = client.post(
        "/api/smms/alerts",
        json={
            "asset_id": asset["id"],
            "inspection_id": inspection["id"],
            "alert_type_code": "SMMS-AL-001",
            "alert_feedback_code": "SMMS-FB-001",
            "alert_status_code": "OPEN",
            "cause_code": "SMMS-CAUSE-001",
            "incidence_date_time": "2026-05-03T10:50:00",
            "rectification_date_time": None,
            "incidence_duration": "PT1H",
            "remarks": "TEST/SYNTHETIC SMMS alert text.",
        },
    ).json()
    maintenance = client.post(
        "/api/smms/maintenance",
        json={
            "asset_id": asset["id"],
            "alert_id": alert["id"],
            "maintenance_type": "Preventive Maintenance",
            "planned_date": "2026-05-14T09:00:00",
            "start_date": "2026-05-14T09:00:00",
            "end_date": "2026-05-14T10:00:00",
            "status": "PLANNED",
            "remarks": "TEST/SYNTHETIC SMMS maintenance record.",
        },
    ).json()
    return source, asset, inspection, alert, maintenance


def find_by_type(records, record_type):
    return [r for r in records if r["source_record_type"] == record_type][0]


def test_tms_defect_normalization(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    summary = client.post("/api/unified/normalize/tms").json()

    assert summary["processed"] == 2
    assert summary["created"] == 2

    defects = client.get("/api/unified/defects").json()
    df = find_by_type(defects, "TMS_DEFECT")
    assert df["source_record_id"] == defect["id"]
    assert df["source_system_id"] == source["id"]
    assert df["asset_id"] == asset["id"]
    assert df["defect_code"] == "TMS-DF-001"
    assert df["severity"] == "HIGH"
    assert df["status"] == "OPEN"
    assert df["detected_at"] == "2026-05-01T10:30:00"


def test_tdms_failure_normalization(client):
    source, asset, inspection, failure, maintenance = create_tdms_chain(client)
    client.post("/api/unified/normalize/tdms")

    defects = client.get("/api/unified/defects").json()
    df = find_by_type(defects, "TDMS_FAILURE")
    assert df["source_record_id"] == failure["id"]
    assert df["source_system_id"] == source["id"]
    assert df["asset_id"] == asset["id"]
    assert df["defect_code"] == "TDMS-F-001"
    assert df["severity"] == "MEDIUM"
    assert df["detected_at"] == "2026-05-02T10:40:00"


def test_smms_alert_normalization(client):
    source, asset, inspection, alert, maintenance = create_smms_chain(client)
    client.post("/api/unified/normalize/smms")

    defects = client.get("/api/unified/defects").json()
    df = find_by_type(defects, "SMMS_ALERT")
    assert df["source_record_id"] == alert["id"]
    assert df["source_system_id"] == source["id"]
    assert df["asset_id"] == asset["id"]
    assert df["defect_code"] == "SMMS-AL-001"
    assert df["status"] == "OPEN"
    assert df["detected_at"] == "2026-05-03T10:50:00"


def test_tms_maintenance_normalization(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")

    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")
    assert mr["source_record_id"] == maintenance["id"]
    assert mr["source_system_id"] == source["id"]
    assert mr["asset_id"] == asset["id"]
    assert mr["maintenance_type"] == "REPLACEMENT"
    assert mr["status"] == "PLANNED"
    assert mr["required_duration_minutes"] == 150


def test_tdms_maintenance_normalization(client):
    source, asset, inspection, failure, maintenance = create_tdms_chain(client)
    client.post("/api/unified/normalize/tdms")

    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TDMS_MAINTENANCE")
    assert mr["source_record_id"] == maintenance["id"]
    assert mr["maintenance_type"] == "REPAIR"
    assert mr["required_duration_minutes"] == 180


def test_smms_maintenance_normalization(client):
    source, asset, inspection, alert, maintenance = create_smms_chain(client)
    client.post("/api/unified/normalize/smms")

    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "SMMS_MAINTENANCE")
    assert mr["source_record_id"] == maintenance["id"]
    assert mr["maintenance_type"] == "Preventive Maintenance"
    assert mr["required_duration_minutes"] == 60


def test_source_provenance_preserved(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")

    defects = client.get("/api/unified/defects").json()
    df = find_by_type(defects, "TMS_DEFECT")
    assert df["source_record_type"] == "TMS_DEFECT"
    assert df["source_record_id"] == defect["id"]

    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")
    assert mr["source_record_type"] == "TMS_MAINTENANCE"
    assert mr["source_record_id"] == maintenance["id"]


def test_asset_linkage_preserved(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")

    filtered = client.get(f"/api/unified/defects?asset_id={asset['id']}").json()
    assert len(filtered) == 1
    assert filtered[0]["asset_id"] == asset["id"]

    filtered_mr = client.get(
        f"/api/unified/maintenance?asset_id={asset['id']}"
    ).json()
    assert len(filtered_mr) == 1
    assert filtered_mr[0]["asset_id"] == asset["id"]


def test_defect_maintenance_linkage(client, db_session):
    source_t, asset_t, _, defect, maintenance = create_tms_chain(client)
    source_d, asset_d, _, failure, maint_d = create_tdms_chain(client)

    client.post("/api/unified/normalize/tms")
    client.post("/api/unified/normalize/tdms")

    df = db_session.scalar(
        select(DefectFailure).where(
            DefectFailure.source_record_type == "TMS_DEFECT",
            DefectFailure.source_record_id == defect["id"],
        )
    )
    mr = db_session.scalar(
        select(MaintenanceRequirement).where(
            MaintenanceRequirement.source_record_type == "TMS_MAINTENANCE",
            MaintenanceRequirement.source_record_id == maintenance["id"],
        )
    )
    assert mr.defect_failure_id == df.id

    df_td = db_session.scalar(
        select(DefectFailure).where(
            DefectFailure.source_record_type == "TDMS_FAILURE",
            DefectFailure.source_record_id == failure["id"],
        )
    )
    mr_td = db_session.scalar(
        select(MaintenanceRequirement).where(
            MaintenanceRequirement.source_record_type == "TDMS_MAINTENANCE",
            MaintenanceRequirement.source_record_id == maint_d["id"],
        )
    )
    assert mr_td.defect_failure_id == df_td.id


def test_block_requirement_creation(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")

    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")

    response = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr["id"],
            "station_code": "STA-7",
            "line_number": "L7",
            "block_type": "TRAFFIC_BLOCK",
            "required_duration_minutes": 120,
            "earliest_start": "2026-05-11T00:00:00",
            "latest_end": "2026-05-11T23:59:59",
            "power_block_required": True,
            "traffic_block_required": False,
            "resource_notes": "TEST/SYNTHETIC resource note.",
            "status": "REQUIRED",
            "remarks": "TEST/SYNTHETIC block requirement.",
        },
    )
    assert response.status_code == 201
    br = response.json()
    assert br["maintenance_requirement_id"] == mr["id"]
    assert br["block_type"] == "TRAFFIC_BLOCK"
    assert br["power_block_required"] is True
    assert br["traffic_block_required"] is False

    single = client.get(f"/api/unified/block-requirements/{br['id']}")
    assert single.status_code == 200
    assert single.json()["id"] == br["id"]

    by_station = client.get("/api/unified/block-requirements?station_code=STA-7")
    assert by_station.status_code == 200
    assert len(by_station.json()) == 1

    by_line = client.get("/api/unified/block-requirements?line_number=L7")
    assert by_line.status_code == 200
    assert len(by_line.json()) == 1

    by_status = client.get("/api/unified/block-requirements?status=REQUIRED")
    assert by_status.status_code == 200
    assert len(by_status.json()) == 1


def test_invalid_maintenance_requirement_id(client):
    response = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": 999,
            "block_type": "TRAFFIC_BLOCK",
            "status": "REQUIRED",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Maintenance requirement not found"


def test_required_field_validation(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")

    missing_block_type = client.post(
        "/api/unified/block-requirements",
        json={"maintenance_requirement_id": mr["id"], "status": "REQUIRED"},
    )
    assert missing_block_type.status_code == 422

    missing_status = client.post(
        "/api/unified/block-requirements",
        json={"maintenance_requirement_id": mr["id"], "block_type": "LINE_BLOCK"},
    )
    assert missing_status.status_code == 422


def test_invalid_duration_rejected(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")

    zero = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr["id"],
            "block_type": "LINE_BLOCK",
            "required_duration_minutes": 0,
            "status": "REQUIRED",
        },
    )
    assert zero.status_code == 422

    negative = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr["id"],
            "block_type": "LINE_BLOCK",
            "required_duration_minutes": -5,
            "status": "REQUIRED",
        },
    )
    assert negative.status_code == 422


def test_invalid_time_range_rejected(client):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = find_by_type(requirements, "TMS_MAINTENANCE")

    response = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr["id"],
            "block_type": "LINE_BLOCK",
            "earliest_start": "2026-05-11T10:00:00",
            "latest_end": "2026-05-11T09:00:00",
            "status": "REQUIRED",
        },
    )
    assert response.status_code == 422


def test_tms_normalization_idempotency(client, db_session):
    create_tms_chain(client)
    first = client.post("/api/unified/normalize/tms").json()
    second = client.post("/api/unified/normalize/tms").json()

    assert first["created"] == 2
    assert second["created"] == 0
    assert second["skipped"] == first["processed"]
    assert db_session.scalar(select(func.count()).select_from(DefectFailure)) == 1
    assert db_session.scalar(select(func.count()).select_from(MaintenanceRequirement)) == 1


def test_tdms_normalization_idempotency(client, db_session):
    create_tdms_chain(client)
    first = client.post("/api/unified/normalize/tdms").json()
    second = client.post("/api/unified/normalize/tdms").json()

    assert first["created"] == 2
    assert second["created"] == 0
    assert second["skipped"] == first["processed"]
    assert db_session.scalar(select(func.count()).select_from(DefectFailure)) == 1
    assert db_session.scalar(select(func.count()).select_from(MaintenanceRequirement)) == 1


def test_smms_normalization_idempotency(client, db_session):
    create_smms_chain(client)
    first = client.post("/api/unified/normalize/smms").json()
    second = client.post("/api/unified/normalize/smms").json()

    assert first["created"] == 2
    assert second["created"] == 0
    assert second["skipped"] == first["processed"]
    assert db_session.scalar(select(func.count()).select_from(DefectFailure)) == 1
    assert db_session.scalar(select(func.count()).select_from(MaintenanceRequirement)) == 1


def test_source_records_unchanged_after_normalization(client, db_session):
    create_tms_chain(client)
    create_tdms_chain(client)
    create_smms_chain(client)

    source_models = (
        TMSDefect,
        TMSMaintenance,
        TDMSFailure,
        TDMSMaintenance,
        SMMSAlert,
        SMMSMaintenance,
    )
    counts_before = {
        model.__tablename__: db_session.scalar(select(func.count()).select_from(model))
        for model in source_models
    }

    client.post("/api/unified/normalize/tms")
    client.post("/api/unified/normalize/tdms")
    client.post("/api/unified/normalize/smms")

    for table, count in counts_before.items():
        model = next(m for m in source_models if m.__tablename__ == table)
        actual = db_session.scalar(select(func.count()).select_from(model))
        assert actual == count, f"{table} changed: {count} -> {actual}"


def test_full_source_to_block_requirement_traceability(client, db_session):
    source, asset, inspection, defect, maintenance = create_tms_chain(client)
    client.post("/api/unified/normalize/tms")

    df = db_session.scalar(
        select(DefectFailure).where(
            DefectFailure.source_record_type == "TMS_DEFECT",
            DefectFailure.source_record_id == defect["id"],
        )
    )
    mr = db_session.scalar(
        select(MaintenanceRequirement).where(
            MaintenanceRequirement.source_record_type == "TMS_MAINTENANCE",
            MaintenanceRequirement.source_record_id == maintenance["id"],
        )
    )
    assert df is not None and mr is not None
    assert df.asset_id == asset["id"]
    assert mr.defect_failure_id == df.id

    br = client.post(
        "/api/unified/block-requirements",
        json={
            "maintenance_requirement_id": mr.id,
            "station_code": "STA-7",
            "line_number": "L7",
            "block_type": "INTEGRATED_BLOCK",
            "status": "REQUIRED",
        },
    ).json()

    db_br = db_session.get(BlockRequirement, br["id"])
    assert db_br.maintenance_requirement_id == mr.id

    src_defect = db_session.get(TMSDefect, defect["id"])
    src_maintenance = db_session.get(TMSMaintenance, maintenance["id"])
    assert df.source_record_id == src_defect.id
    assert mr.source_record_id == src_maintenance.id
    assert mr.asset_id == src_maintenance.asset_id

    chain = (
        db_session.execute(
            select(DefectFailure, MaintenanceRequirement, BlockRequirement, TMSDefect)
            .join(MaintenanceRequirement, MaintenanceRequirement.defect_failure_id == DefectFailure.id)
            .join(BlockRequirement, BlockRequirement.maintenance_requirement_id == MaintenanceRequirement.id)
            .join(TMSDefect, TMSDefect.id == DefectFailure.source_record_id)
            .where(BlockRequirement.id == db_br.id)
        ).first()
    )
    assert chain is not None
    assert chain[0].id == df.id
    assert chain[1].id == mr.id
    assert chain[2].id == db_br.id
    assert chain[3].id == defect["id"]


def test_no_ai_optimization_fields_exist(db_session):
    inspector = inspect(db_session.bind)
    for table in ("defect_failure", "maintenance_requirement", "block_requirement"):
        columns = {col["name"] for col in inspector.get_columns(table)}
        assert columns.isdisjoint(FORBIDDEN_COLUMNS), (
            f"{table} contains forbidden AI/planning columns: "
            f"{columns & FORBIDDEN_COLUMNS}"
        )


def test_existing_available_window_unchanged(client, db_session):
    coa = create_source(client, "COA")
    train = client.post(
        "/api/coa/trains",
        json={
            "train_id": "COA-TRN-UNI-001",
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
                "source_event_id": f"SRC-UNI-{start}",
            },
        )
    generated = client.post("/api/coa/available-windows/generate")
    assert generated.status_code == 200
    before = client.get("/api/coa/available-windows").json()

    create_source(client, "TMS")
    create_source(client, "TDMS")
    create_source(client, "SMMS")
    client.post("/api/unified/normalize/tms")
    client.post("/api/unified/normalize/tdms")
    client.post("/api/unified/normalize/smms")

    after = client.get("/api/coa/available-windows").json()
    assert after == before
    assert len(after) == 1
    assert after[0]["window_status"] == "AVAILABLE"

    # AvailableWindow model/table still fully intact
    count = db_session.scalar(select(func.count()).select_from(AvailableWindow))
    assert count == 1


def test_existing_source_tables_intact(db_session):
    inspector = inspect(db_session.bind)
    existing = {
        "source_system",
        "location_master",
        "asset_master",
        "asset_parameter",
        "tms_inspection",
        "tms_defect",
        "tms_maintenance",
        "tdms_inspection",
        "tdms_failure",
        "tdms_maintenance",
        "smms_inspection",
        "smms_alert",
        "smms_maintenance",
        "train",
        "train_movement",
        "train_schedule",
        "line_occupancy",
        "operational_event",
        "available_window",
    }
    tables = set(inspector.get_table_names())
    assert existing.issubset(tables)
    for table in ("defect_failure", "maintenance_requirement", "block_requirement"):
        assert table in tables