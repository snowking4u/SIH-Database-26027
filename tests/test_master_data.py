def create_source_system(client, code="TEST"):
    response = client.post(
        "/api/source-systems",
        json={
            "system_code": code,
            "system_name": f"{code} Source",
            "description": "TEST/SYNTHETIC source system for API testing.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_location(client):
    response = client.post(
        "/api/locations",
        json={
            "zone_code": "TEST-Z",
            "zone_name": "TEST/SYNTHETIC Zone",
            "division_code": "TEST-D",
            "division_name": "TEST/SYNTHETIC Division",
            "section_code": "TEST-S",
            "section_name": "TEST/SYNTHETIC Section",
            "station_code": "TST",
            "station_name": "TEST/SYNTHETIC Station",
            "line_code": "TEST-L",
            "line_name": "TEST/SYNTHETIC Line",
            "km_start": "1.000",
            "km_end": "2.000",
            "latitude": "12.971600",
            "longitude": "77.594600",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_asset(client):
    source_system = create_source_system(client)
    location = create_location(client)
    response = client.post(
        "/api/assets",
        json={
            "source_system_id": source_system["id"],
            "source_asset_id": "TEST-ASSET-001",
            "asset_type": "TEST/SYNTHETIC",
            "asset_subtype": "TEST/SYNTHETIC",
            "asset_name": "TEST/SYNTHETIC Asset",
            "location_id": location["id"],
            "installation_date": "2026-01-01",
            "status": "TEST",
            "remarks": "TEST/SYNTHETIC record for API testing.",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_source_system(client):
    source_system = create_source_system(client)

    assert source_system["system_code"] == "TEST"
    assert source_system["system_name"] == "TEST Source"


def test_get_source_systems(client):
    create_source_system(client)

    response = client.get("/api/source-systems")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_location(client):
    location = create_location(client)

    assert location["station_code"] == "TST"
    assert location["station_name"] == "TEST/SYNTHETIC Station"


def test_create_asset_linked_to_source_system_and_location(client):
    asset = create_asset(client)

    assert asset["source_asset_id"] == "TEST-ASSET-001"
    assert asset["source_system_id"] is not None
    assert asset["location_id"] is not None


def test_create_asset_parameter_linked_to_asset(client):
    asset = create_asset(client)

    response = client.post(
        f"/api/assets/{asset['id']}/parameters",
        json={
            "source_system_id": asset["source_system_id"],
            "parameter_code": "TEST-PARAM",
            "parameter_name": "TEST/SYNTHETIC Parameter",
            "parameter_value": "123",
            "unit": "TEST",
            "recorded_date": "2026-01-01T10:00:00",
        },
    )

    assert response.status_code == 201
    assert response.json()["asset_id"] == asset["id"]


def test_get_asset_parameters(client):
    asset = create_asset(client)
    client.post(
        f"/api/assets/{asset['id']}/parameters",
        json={
            "source_system_id": asset["source_system_id"],
            "parameter_code": "TEST-PARAM",
            "parameter_value": "123",
        },
    )

    response = client.get(f"/api/assets/{asset['id']}/parameters")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_invalid_foreign_key_reference_returns_404(client):
    response = client.post(
        "/api/assets",
        json={
            "source_system_id": 999,
            "source_asset_id": "MISSING-SOURCE",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source system not found"


def test_nonexistent_record_returns_404(client):
    response = client.get("/api/assets/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"
