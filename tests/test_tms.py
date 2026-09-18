from sqlalchemy import inspect

from app.models.tms_inspection import TMSInspection

FORBIDDEN_COLUMNS = {
    "priority_score",
    "risk_score",
    "predicted_failure",
    "recommended_block",
    "optimization_score",
    "optimization_run_id",
    "candidate_window_id",
}


def create_tms_asset(client):
    source = client.post(
        "/api/source-systems",
        json={
            "system_code": "TMS",
            "system_name": "TMS",
            "description": "TEST/SYNTHETIC TMS source system for API testing.",
        },
    )
    assert source.status_code == 201
    asset = client.post(
        "/api/assets",
        json={
            "source_system_id": source.json()["id"],
            "source_asset_id": "TMS-TEST-ASSET-001",
            "asset_type": "TEST/SYNTHETIC",
            "asset_name": "TEST/SYNTHETIC TMS Asset",
            "status": "TEST",
        },
    )
    assert asset.status_code == 201
    return asset.json()


def create_inspection(client, asset):
    response = client.post(
        "/api/tms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": "2026-01-01T10:00:00",
            "inspection_type": "USFD",
            "parameter_code": "TUBE-DEFLECTION",
            "parameter_value": "4.5",
            "remarks": "TEST/SYNTHETIC inspection.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_defect(client, asset, inspection):
    response = client.post(
        "/api/tms/defects",
        json={
            "asset_id": asset["id"],
            "inspection_id": inspection["id"],
            "defect_code": "TMS-DEFECT-001",
            "defect_description": "TEST/SYNTHETIC defect observed on track.",
            "severity": "LOW",
            "detected_date": "2026-01-01T10:05:00",
            "status": "OPEN",
            "remarks": "TEST/SYNTHETIC defect.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_maintenance(client, asset, defect):
    response = client.post(
        "/api/tms/maintenance",
        json={
            "asset_id": asset["id"],
            "defect_id": defect["id"],
            "maintenance_type": "REPLACEMENT",
            "planned_date": "2026-01-15T09:00:00",
            "start_date": None,
            "end_date": None,
            "status": "PLANNED",
            "remarks": "TEST/SYNTHETIC maintenance planning record.",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_tms_inspection(client):
    asset = create_tms_asset(client)
    inspection = create_inspection(client, asset)

    assert inspection["asset_id"] == asset["id"]
    assert inspection["inspection_type"] == "USFD"
    assert inspection["parameter_code"] == "TUBE-DEFLECTION"


def test_get_tms_inspection(client):
    asset = create_tms_asset(client)
    inspection = create_inspection(client, asset)

    response = client.get(f"/api/tms/inspections/{inspection['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == inspection["id"]


def test_create_tms_defect_linked_to_inspection(client):
    asset = create_tms_asset(client)
    inspection = create_inspection(client, asset)
    defect = create_defect(client, asset, inspection)

    assert defect["inspection_id"] == inspection["id"]
    assert defect["asset_id"] == asset["id"]


def test_get_tms_defect(client):
    asset = create_tms_asset(client)
    inspection = create_inspection(client, asset)
    defect = create_defect(client, asset, inspection)

    response = client.get(f"/api/tms/defects/{defect['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == defect["id"]


def test_create_tms_maintenance_linked_to_defect(client):
    asset = create_tms_asset(client)
    inspection = create_inspection(client, asset)
    defect = create_defect(client, asset, inspection)
    maintenance = create_maintenance(client, asset, defect)

    assert maintenance["defect_id"] == defect["id"]
    assert maintenance["asset_id"] == asset["id"]
    assert maintenance["status"] == "PLANNED"


def test_get_tms_maintenance(client):
    asset = create_tms_asset(client)
    inspection = create_inspection(client, asset)
    defect = create_defect(client, asset, inspection)
    maintenance = create_maintenance(client, asset, defect)

    response = client.get(f"/api/tms/maintenance/{maintenance['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == maintenance["id"]


def test_invalid_asset_id(client):
    response = client.post(
        "/api/tms/inspections",
        json={
            "asset_id": 999,
            "inspection_date": "2026-01-01T10:00:00",
            "inspection_type": "USFD",
            "parameter_code": "TUBE-DEFLECTION",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"


def test_invalid_inspection_id(client):
    asset = create_tms_asset(client)

    response = client.post(
        "/api/tms/defects",
        json={
            "asset_id": asset["id"],
            "inspection_id": 999,
            "defect_code": "TMS-DEFECT-BAD",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TMS inspection not found"


def test_invalid_defect_id(client):
    asset = create_tms_asset(client)

    response = client.post(
        "/api/tms/maintenance",
        json={
            "asset_id": asset["id"],
            "defect_id": 999,
            "maintenance_type": "REPLACEMENT",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TMS defect not found"


def test_required_field_validation(client):
    asset = create_tms_asset(client)

    inspection_response = client.post(
        "/api/tms/inspections",
        json={"asset_id": asset["id"], "inspection_date": "2026-01-01T10:00:00"},
    )
    assert inspection_response.status_code == 422

    defect_response = client.post(
        "/api/tms/defects",
        json={"asset_id": asset["id"], "inspection_id": 1},
    )
    assert defect_response.status_code == 422

    maintenance_response = client.post(
        "/api/tms/maintenance",
        json={"asset_id": asset["id"], "defect_id": 1},
    )
    assert maintenance_response.status_code == 422


def test_asset_id_filter(client):
    asset = create_tms_asset(client)
    create_inspection(client, asset)

    response = client.get(f"/api/tms/inspections?asset_id={asset['id']}")

    assert response.status_code == 200
    assert all(i["asset_id"] == asset["id"] for i in response.json())

    empty = client.get("/api/tms/inspections?asset_id=999999")
    assert empty.status_code == 200
    assert empty.json() == []


def test_verify_relationships(client, db_session):
    asset = create_tms_asset(client)
    inspection = create_inspection(client, asset)
    defect = create_defect(client, asset, inspection)
    maintenance = create_maintenance(client, asset, defect)

    re_inspection = client.get(f"/api/tms/inspections/{inspection['id']}").json()
    re_defect = client.get(f"/api/tms/defects/{defect['id']}").json()
    re_maintenance = client.get(f"/api/tms/maintenance/{maintenance['id']}").json()

    assert re_inspection["asset_id"] == asset["id"]
    assert re_defect["inspection_id"] == inspection["id"]
    assert re_defect["asset_id"] == asset["id"]
    assert re_maintenance["defect_id"] == defect["id"]
    assert re_maintenance["asset_id"] == asset["id"]

    insp = db_session.get(TMSInspection, inspection["id"])
    assert len(insp.defects) == 1
    assert insp.defects[0].id == defect["id"]


def test_no_ai_planning_fields_exist(db_session):
    inspector = inspect(db_session.bind)
    for table in ("tms_inspection", "tms_defect", "tms_maintenance"):
        columns = {col["name"] for col in inspector.get_columns(table)}
        assert columns.isdisjoint(FORBIDDEN_COLUMNS), (
            f"{table} contains forbidden AI/planning columns: "
            f"{columns & FORBIDDEN_COLUMNS}"
        )