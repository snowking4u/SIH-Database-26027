from sqlalchemy import inspect

from app.models.smms_inspection import SMMSInspection

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


def create_smms_asset(client):
    source = client.post(
        "/api/source-systems",
        json={
            "system_code": "SMMS",
            "system_name": "SMMS",
            "description": "TEST/SYNTHETIC SMMS source system for API testing.",
        },
    )
    assert source.status_code == 201
    asset = client.post(
        "/api/assets",
        json={
            "source_system_id": source.json()["id"],
            "source_asset_id": "SMMS-TEST-ASSET-001",
            "asset_type": "TEST/SYNTHETIC",
            "asset_name": "TEST/SYNTHETIC SMMS Asset",
            "status": "TEST",
        },
    )
    assert asset.status_code == 201
    return asset.json()


def create_inspection(client, asset, code="SMMS-TEST-INSP-001"):
    response = client.post(
        "/api/smms/inspections",
        json={
            "asset_id": asset["id"],
            "inspection_date": "2026-03-01T10:00:00",
            "inspection_type": "Point Machine Inspection",
            "parameter_code": code,
            "parameter_value": "NORMAL",
            "remarks": "TEST/SYNTHETIC SMMS inspection.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_alert(client, asset, inspection=None):
    payload = {
        "asset_id": asset["id"],
        "alert_type_code": "SMMS-ALERT-001",
        "alert_status_code": "OPEN",
        "cause_code": "SMMS-CAUSE-001",
        "incidence_date_time": "2026-03-01T10:30:00",
        "rectification_date_time": "2026-03-01T12:00:00",
        "incidence_duration": "PT1H30M",
        "maintainer_name": "TEST MAINTAINER",
        "maintainer_designation": "Signal Maintainer",
        "maintainer_mobile": "9999999999",
        "remarks": "TEST/SYNTHETIC SMMS alert.",
    }
    if inspection is not None:
        payload["inspection_id"] = inspection["id"]
    response = client.post("/api/smms/alerts", json=payload)
    assert response.status_code == 201
    return response.json()


def create_maintenance(client, asset, alert=None):
    payload = {
        "asset_id": asset["id"],
        "maintenance_type": "Preventive Maintenance Inspection",
        "planned_date": "2026-03-10T09:00:00",
        "status": "PLANNED",
        "remarks": "TEST/SYNTHETIC SMMS maintenance planning record.",
    }
    if alert is not None:
        payload["alert_id"] = alert["id"]
    response = client.post("/api/smms/maintenance", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_smms_inspection(client):
    asset = create_smms_asset(client)
    inspection = create_inspection(client, asset)

    assert inspection["asset_id"] == asset["id"]
    assert inspection["inspection_type"] == "Point Machine Inspection"
    assert inspection["parameter_code"] == "SMMS-TEST-INSP-001"


def test_get_smms_inspection(client):
    asset = create_smms_asset(client)
    inspection = create_inspection(client, asset)

    response = client.get(f"/api/smms/inspections/{inspection['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == inspection["id"]


def test_filter_inspection_by_asset_id(client):
    asset = create_smms_asset(client)
    create_inspection(client, asset)

    response = client.get(f"/api/smms/inspections?asset_id={asset['id']}")

    assert response.status_code == 200
    assert all(i["asset_id"] == asset["id"] for i in response.json())

    empty = client.get("/api/smms/inspections?asset_id=999999")
    assert empty.status_code == 200
    assert empty.json() == []


def test_create_smms_alert_linked_to_inspection(client):
    asset = create_smms_asset(client)
    inspection = create_inspection(client, asset)
    alert = create_alert(client, asset, inspection)

    assert alert["inspection_id"] == inspection["id"]
    assert alert["asset_id"] == asset["id"]
    assert alert["alert_status_code"] == "OPEN"
    assert alert["incidence_duration"] is not None


def test_get_smms_alert(client):
    asset = create_smms_asset(client)
    inspection = create_inspection(client, asset)
    alert = create_alert(client, asset, inspection)

    response = client.get(f"/api/smms/alerts/{alert['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == alert["id"]


def test_create_smms_alert_without_inspection(client):
    asset = create_smms_asset(client)
    alert = create_alert(client, asset, inspection=None)

    assert alert["inspection_id"] is None
    assert alert["alert_status_code"] == "OPEN"


def test_create_smms_maintenance_linked_to_alert(client):
    asset = create_smms_asset(client)
    alert = create_alert(client, asset, inspection=None)
    maintenance = create_maintenance(client, asset, alert)

    assert maintenance["alert_id"] == alert["id"]
    assert maintenance["asset_id"] == asset["id"]
    assert maintenance["status"] == "PLANNED"


def test_get_smms_maintenance(client):
    asset = create_smms_asset(client)
    alert = create_alert(client, asset, inspection=None)
    maintenance = create_maintenance(client, asset, alert)

    response = client.get(f"/api/smms/maintenance/{maintenance['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == maintenance["id"]


def test_filter_maintenance_by_asset_id(client):
    asset = create_smms_asset(client)
    alert = create_alert(client, asset, inspection=None)
    create_maintenance(client, asset, alert)

    response = client.get(f"/api/smms/maintenance?asset_id={asset['id']}")

    assert response.status_code == 200
    assert all(m["asset_id"] == asset["id"] for m in response.json())


def test_invalid_asset_id(client):
    response = client.post(
        "/api/smms/inspections",
        json={
            "asset_id": 999,
            "inspection_date": "2026-03-01T10:00:00",
            "inspection_type": "Point Machine Inspection",
            "parameter_code": "DROOP",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"


def test_invalid_inspection_id(client):
    asset = create_smms_asset(client)

    response = client.post(
        "/api/smms/alerts",
        json={
            "asset_id": asset["id"],
            "inspection_id": 999,
            "alert_type_code": "SMMS-ALERT-BAD",
            "alert_status_code": "OPEN",
            "incidence_date_time": "2026-03-01T10:30:00",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "SMMS inspection not found"


def test_invalid_alert_id(client):
    asset = create_smms_asset(client)

    response = client.post(
        "/api/smms/maintenance",
        json={
            "asset_id": asset["id"],
            "alert_id": 999,
            "maintenance_type": "Preventive Maintenance Inspection",
            "status": "PLANNED",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "SMMS alert not found"


def test_required_field_validation(client):
    asset = create_smms_asset(client)

    inspection_response = client.post(
        "/api/smms/inspections",
        json={"asset_id": asset["id"], "inspection_date": "2026-03-01T10:00:00"},
    )
    assert inspection_response.status_code == 422

    alert_missing_type = client.post(
        "/api/smms/alerts",
        json={
            "asset_id": asset["id"],
            "alert_status_code": "OPEN",
            "incidence_date_time": "2026-03-01T10:30:00",
        },
    )
    assert alert_missing_type.status_code == 422

    alert_missing_status = client.post(
        "/api/smms/alerts",
        json={
            "asset_id": asset["id"],
            "alert_type_code": "X",
            "incidence_date_time": "2026-03-01T10:30:00",
        },
    )
    assert alert_missing_status.status_code == 422

    maintenance_response = client.post(
        "/api/smms/maintenance",
        json={"asset_id": asset["id"]},
    )
    assert maintenance_response.status_code == 422


def test_verify_relationships(client, db_session):
    asset = create_smms_asset(client)
    inspection = create_inspection(client, asset)
    alert = create_alert(client, asset, inspection)
    maintenance = create_maintenance(client, asset, alert)

    re_inspection = client.get(f"/api/smms/inspections/{inspection['id']}").json()
    re_alert = client.get(f"/api/smms/alerts/{alert['id']}").json()
    re_maintenance = client.get(f"/api/smms/maintenance/{maintenance['id']}").json()

    assert re_inspection["asset_id"] == asset["id"]
    assert re_alert["inspection_id"] == inspection["id"]
    assert re_alert["asset_id"] == asset["id"]
    assert re_maintenance["alert_id"] == alert["id"]
    assert re_maintenance["asset_id"] == asset["id"]

    insp = db_session.get(SMMSInspection, inspection["id"])
    assert len(insp.alerts) == 1
    assert insp.alerts[0].id == alert["id"]


def test_no_ai_planning_fields_exist(db_session):
    inspector = inspect(db_session.bind)
    for table in ("smms_inspection", "smms_alert", "smms_maintenance"):
        columns = {col["name"] for col in inspector.get_columns(table)}
        assert columns.isdisjoint(FORBIDDEN_COLUMNS), (
            f"{table} contains forbidden AI/planning columns: "
            f"{columns & FORBIDDEN_COLUMNS}"
        )