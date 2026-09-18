from sqlalchemy import inspect

from app.models.tdms_inspection import TDMSInspection

FORBIDDEN_COLUMNS = {
    "priority_score",
    "risk_score",
    "predicted_failure",
    "recommended_block",
    "optimization_score",
    "candidate_block",
    "available_window",
    "optimization_run_id",
    "candidate_window_id",
}


def create_tdms_asset(client):
    source = client.post(
        "/api/source-systems",
        json={
            "system_code": "TDMS",
            "system_name": "TDMS",
            "description": "TEST/SYNTHETIC TDMS source system for API testing.",
        },
    )
    assert source.status_code == 201
    asset = client.post(
        "/api/assets",
        json={
            "source_system_id": source.json()["id"],
            "source_asset_id": "TDMS-TEST-ASSET-001",
            "asset_type": "TEST/SYNTHETIC",
            "asset_name": "TEST/SYNTHETIC TDMS Asset",
            "status": "TEST",
        },
    )
    assert asset.status_code == 201
    return asset.json()


def create_inspection(client, asset, code="TDMS-TEST-INSP-001"):
    response = client.post(
        "/api/tdms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": "2026-02-01T10:00:00",
            "inspection_type": "OHE Inspection",
            "parameter_code": code,
            "parameter_value": "9.5",
            "remarks": "TEST/SYNTHETIC TDMS inspection.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_failure(client, asset, inspection=None):
    payload = {
        "asset_id": asset["id"],
        "failure_code": "TDMS-FAIL-001",
        "failure_description": "TEST/SYNTHETIC failure on OHE.",
        "severity": "MEDIUM",
        "failure_date": "2026-02-01T10:30:00",
        "status": "OPEN",
        "remarks": "TEST/SYNTHETIC TDMS failure.",
    }
    if inspection is not None:
        payload["inspection_id"] = inspection["id"]
    response = client.post("/api/tdms/failures", json=payload)
    assert response.status_code == 201
    return response.json()


def create_maintenance(client, asset, failure=None):
    payload = {
        "asset_id": asset["id"],
        "maintenance_type": "OHE RECTIFICATION",
        "planned_date": "2026-02-10T09:00:00",
        "status": "PLANNED",
        "remarks": "TEST/SYNTHETIC TDMS maintenance planning record.",
    }
    if failure is not None:
        payload["failure_id"] = failure["id"]
    response = client.post("/api/tdms/maintenance", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_tdms_inspection(client):
    asset = create_tdms_asset(client)
    inspection = create_inspection(client, asset)

    assert inspection["asset_id"] == asset["id"]
    assert inspection["inspection_type"] == "OHE Inspection"
    assert inspection["parameter_code"] == "TDMS-TEST-INSP-001"


def test_get_tdms_inspection(client):
    asset = create_tdms_asset(client)
    inspection = create_inspection(client, asset)

    response = client.get(f"/api/tdms/inspections/{inspection['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == inspection["id"]


def test_filter_inspection_by_asset_id(client):
    asset = create_tdms_asset(client)
    create_inspection(client, asset)

    response = client.get(f"/api/tdms/inspections?asset_id={asset['id']}")

    assert response.status_code == 200
    assert all(i["asset_id"] == asset["id"] for i in response.json())

    empty = client.get("/api/tdms/inspections?asset_id=999999")
    assert empty.status_code == 200
    assert empty.json() == []


def test_create_tdms_failure_linked_to_inspection(client):
    asset = create_tdms_asset(client)
    inspection = create_inspection(client, asset)
    failure = create_failure(client, asset, inspection)

    assert failure["inspection_id"] == inspection["id"]
    assert failure["asset_id"] == asset["id"]
    assert failure["failure_code"] == "TDMS-FAIL-001"


def test_get_tdms_failure(client):
    asset = create_tdms_asset(client)
    inspection = create_inspection(client, asset)
    failure = create_failure(client, asset, inspection)

    response = client.get(f"/api/tdms/failures/{failure['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == failure["id"]


def test_create_tdms_failure_without_inspection(client):
    asset = create_tdms_asset(client)
    failure = create_failure(client, asset, inspection=None)

    assert failure["inspection_id"] is None
    assert failure["status"] == "OPEN"


def test_create_tdms_maintenance_linked_to_failure(client):
    asset = create_tdms_asset(client)
    failure = create_failure(client, asset, inspection=None)
    maintenance = create_maintenance(client, asset, failure)

    assert maintenance["failure_id"] == failure["id"]
    assert maintenance["asset_id"] == asset["id"]
    assert maintenance["status"] == "PLANNED"


def test_get_tdms_maintenance(client):
    asset = create_tdms_asset(client)
    failure = create_failure(client, asset, inspection=None)
    maintenance = create_maintenance(client, asset, failure)

    response = client.get(f"/api/tdms/maintenance/{maintenance['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == maintenance["id"]


def test_filter_maintenance_by_asset_id(client):
    asset = create_tdms_asset(client)
    failure = create_failure(client, asset, inspection=None)
    create_maintenance(client, asset, failure)

    response = client.get(f"/api/tdms/maintenance?asset_id={asset['id']}")

    assert response.status_code == 200
    assert all(m["asset_id"] == asset["id"] for m in response.json())


def test_invalid_asset_id(client):
    response = client.post(
        "/api/tdms/inspections",
        json={
            "asset_id": 999,
            "inspection_date": "2026-02-01T10:00:00",
            "inspection_type": "OHE Inspection",
            "parameter_code": "DROOP",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"


def test_invalid_inspection_id(client):
    asset = create_tdms_asset(client)

    response = client.post(
        "/api/tdms/failures",
        json={
            "asset_id": asset["id"],
            "inspection_id": 999,
            "failure_code": "TDMS-FAIL-BAD",
            "failure_date": "2026-02-01T10:30:00",
            "status": "OPEN",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TDMS inspection not found"


def test_invalid_failure_id(client):
    asset = create_tdms_asset(client)

    response = client.post(
        "/api/tdms/maintenance",
        json={
            "asset_id": asset["id"],
            "failure_id": 999,
            "maintenance_type": "OHE RECTIFICATION",
            "status": "PLANNED",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TDMS failure not found"


def test_required_field_validation(client):
    asset = create_tdms_asset(client)

    inspection_response = client.post(
        "/api/tdms/inspections",
        json={"asset_id": asset["id"], "inspection_date": "2026-02-01T10:00:00"},
    )
    assert inspection_response.status_code == 422

    failure_missing_date = client.post(
        "/api/tdms/failures",
        json={"asset_id": asset["id"], "failure_code": "X", "status": "OPEN"},
    )
    assert failure_missing_date.status_code == 422

    failure_missing_status = client.post(
        "/api/tdms/failures",
        json={"asset_id": asset["id"], "failure_code": "X", "failure_date": "2026-02-01T10:00:00"},
    )
    assert failure_missing_status.status_code == 422

    maintenance_response = client.post(
        "/api/tdms/maintenance",
        json={"asset_id": asset["id"]},
    )
    assert maintenance_response.status_code == 422


def test_verify_relationships(client, db_session):
    asset = create_tdms_asset(client)
    inspection = create_inspection(client, asset)
    failure = create_failure(client, asset, inspection)
    maintenance = create_maintenance(client, asset, failure)

    re_inspection = client.get(f"/api/tdms/inspections/{inspection['id']}").json()
    re_failure = client.get(f"/api/tdms/failures/{failure['id']}").json()
    re_maintenance = client.get(f"/api/tdms/maintenance/{maintenance['id']}").json()

    assert re_inspection["asset_id"] == asset["id"]
    assert re_failure["inspection_id"] == inspection["id"]
    assert re_failure["asset_id"] == asset["id"]
    assert re_maintenance["failure_id"] == failure["id"]
    assert re_maintenance["asset_id"] == asset["id"]

    insp = db_session.get(TDMSInspection, inspection["id"])
    assert len(insp.failures) == 1
    assert insp.failures[0].id == failure["id"]


def test_no_ai_planning_fields_exist(db_session):
    inspector = inspect(db_session.bind)
    for table in ("tdms_inspection", "tdms_failure", "tdms_maintenance"):
        columns = {col["name"] for col in inspector.get_columns(table)}
        assert columns.isdisjoint(FORBIDDEN_COLUMNS), (
            f"{table} contains forbidden AI/planning columns: "
            f"{columns & FORBIDDEN_COLUMNS}"
        )