from sqlalchemy import func, inspect, select

from app.models.line_occupancy import LineOccupancy
from app.models.operational_event import OperationalEvent
from app.models.smms_maintenance import SMMSMaintenance
from app.models.tdms_maintenance import TDMSMaintenance
from app.models.tms_maintenance import TMSMaintenance
from app.models.train import Train
from app.models.train_movement import TrainMovement
from app.models.train_schedule import TrainSchedule

FORBIDDEN_COLUMNS = {
    "priority_score",
    "risk_score",
    "predicted_failure",
    "recommended_block",
    "optimization_score",
    "candidate_block",
    "optimization_run",
    "optimization_input",
    "optimization_output",
    "planned_block",
    "controller_decision",
    "planning_task",
    "planning_constraint",
    "candidate_block_window",
    "validation_result",
    "execution_outcome",
}


def create_coa_source(client):
    source = client.post(
        "/api/source-systems",
        json={
            "system_code": "COA",
            "system_name": "COA",
            "description": "TEST/SYNTHETIC COA source system for API testing.",
        },
    )
    assert source.status_code == 201
    return source.json()


def create_train(client, source, train_id="COA-TRN-001"):
    response = client.post(
        "/api/coa/trains",
        json={
            "train_id": train_id,
            "train_number": "12345",
            "train_name": "TEST/SYNTHETIC Train",
            "schedule_date": "2026-03-01T00:00:00",
            "start_date": "2026-03-01T00:00:00",
            "loco_number": "LOCO-1",
            "direction": "UP",
            "source_system_id": source["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


def create_movement(client, train):
    response = client.post(
        "/api/coa/movements",
        json={
            "train_id": train["id"],
            "station_code": "STA-1",
            "movement_flag": "A",
            "movement_datetime": "2026-03-01T10:05:00",
            "line_number": "L1",
            "source_event_id": "SRC-MOV-1",
            "remarks": "TEST/SYNTHETIC movement.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_schedule(
    client,
    train,
    sequence_number,
    station_code="STA-2",
    line_number="L2",
    scheduled_arrival="2026-03-01T10:00:00",
    scheduled_departure="2026-03-01T10:30:00",
):
    response = client.post(
        "/api/coa/schedules",
        json={
            "train_id": train["id"],
            "station_code": station_code,
            "scheduled_arrival": scheduled_arrival,
            "scheduled_departure": scheduled_departure,
            "sequence_number": sequence_number,
            "line_number": line_number,
            "source_schedule_id": f"SRC-SCH-{sequence_number}",
            "remarks": "TEST/SYNTHETIC schedule.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_occupancy(
    client,
    train,
    start,
    end,
    status,
    station_code="STA-1",
    line_number="L1",
):
    payload = {
        "station_code": station_code,
        "line_number": line_number,
        "occupancy_start": start,
        "occupancy_end": end,
        "occupancy_status": status,
        "source_event_id": f"SRC-OCC-{start}",
        "remarks": "TEST/SYNTHETIC occupancy.",
    }
    if train is not None:
        payload["train_id"] = train["id"]
    response = client.post("/api/coa/line-occupancy", json=payload)
    assert response.status_code == 201
    return response.json()


def create_event(client, train):
    response = client.post(
        "/api/coa/events",
        json={
            "train_id": train["id"],
            "station_code": "STA-1",
            "event_type": "CAUTION",
            "event_datetime": "2026-03-01T10:10:00",
            "description": "TEST/SYNTHETIC event.",
            "source_event_id": "SRC-EVT-1",
            "remarks": "TEST/SYNTHETIC event.",
        },
    )
    assert response.status_code == 201
    return response.json()


def seed_derivation_data(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    create_movement(client, train)
    create_schedule(
        client,
        train,
        sequence_number=1,
        scheduled_arrival="2026-03-01T10:00:00",
        scheduled_departure="2026-03-01T10:30:00",
    )
    create_schedule(
        client,
        train,
        sequence_number=2,
        scheduled_arrival="2026-03-01T10:50:00",
        scheduled_departure="2026-03-01T11:20:00",
    )
    create_occupancy(client, train, "2026-03-01T10:00:00", "2026-03-01T10:20:00", "OCCUPIED")
    create_occupancy(client, train, "2026-03-01T10:40:00", "2026-03-01T11:00:00", "OCCUPIED")
    create_event(client, train)
    return source, train


def generate(client):
    response = client.post("/api/coa/available-windows/generate")
    assert response.status_code == 200
    return response.json()


def test_create_train(client):
    source = create_coa_source(client)
    train = create_train(client, source)

    assert train["train_id"] == "COA-TRN-001"
    assert train["source_system_id"] == source["id"]
    assert train["direction"] == "UP"


def test_get_train(client):
    source = create_coa_source(client)
    train = create_train(client, source)

    response = client.get(f"/api/coa/trains/{train['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == train["id"]


def test_filter_train_by_train_id(client):
    source = create_coa_source(client)
    create_train(client, source, train_id="COA-TRN-FILTER")

    response = client.get("/api/coa/trains?train_id=COA-TRN-FILTER")

    assert response.status_code == 200
    assert all(t["train_id"] == "COA-TRN-FILTER" for t in response.json())

    empty = client.get("/api/coa/trains?train_id=DOES-NOT-EXIST")
    assert empty.status_code == 200
    assert empty.json() == []


def test_create_train_movement(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    movement = create_movement(client, train)

    assert movement["train_id"] == train["id"]
    assert movement["movement_flag"] == "A"
    assert movement["station_code"] == "STA-1"


def test_get_train_movement(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    movement = create_movement(client, train)

    response = client.get(f"/api/coa/movements/{movement['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == movement["id"]


def test_create_train_schedule(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    schedule = create_schedule(client, train, sequence_number=1)

    assert schedule["train_id"] == train["id"]
    assert schedule["sequence_number"] == 1
    assert schedule["station_code"] == "STA-2"


def test_get_train_schedule(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    schedule = create_schedule(client, train, sequence_number=1)

    response = client.get(f"/api/coa/schedules/{schedule['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == schedule["id"]


def test_create_line_occupancy(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    occupancy = create_occupancy(
        client, train, "2026-03-01T10:00:00", "2026-03-01T10:20:00", "OCCUPIED"
    )

    assert occupancy["station_code"] == "STA-1"
    assert occupancy["line_number"] == "L1"
    assert occupancy["occupancy_status"] == "OCCUPIED"


def test_get_line_occupancy(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    occupancy = create_occupancy(
        client, train, "2026-03-01T10:00:00", "2026-03-01T10:20:00", "OCCUPIED"
    )

    response = client.get(f"/api/coa/line-occupancy/{occupancy['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == occupancy["id"]


def test_create_operational_event(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    event = create_event(client, train)

    assert event["train_id"] == train["id"]
    assert event["event_type"] == "CAUTION"


def test_get_operational_event(client):
    source = create_coa_source(client)
    train = create_train(client, source)
    event = create_event(client, train)

    response = client.get(f"/api/coa/events/{event['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == event["id"]


def test_invalid_source_system_id(client):
    response = client.post(
        "/api/coa/trains",
        json={"train_id": "COA-BAD-SOURCE", "source_system_id": 999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source system not found"


def test_invalid_train_id(client):
    response = client.post(
        "/api/coa/movements",
        json={
            "train_id": 999,
            "station_code": "STA-1",
            "movement_flag": "A",
            "movement_datetime": "2026-03-01T10:00:00",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Train not found"


def test_required_field_validation(client):
    source = create_coa_source(client)
    train = create_train(client, source)

    train_missing_id = client.post(
        "/api/coa/trains", json={"source_system_id": source["id"]}
    )
    assert train_missing_id.status_code == 422

    movement_missing_datetime = client.post(
        "/api/coa/movements",
        json={"train_id": train["id"], "station_code": "STA-1", "movement_flag": "A"},
    )
    assert movement_missing_datetime.status_code == 422

    schedule_missing_sequence = client.post(
        "/api/coa/schedules", json={"train_id": train["id"], "station_code": "STA-1"}
    )
    assert schedule_missing_sequence.status_code == 422

    occupancy_missing_status = client.post(
        "/api/coa/line-occupancy",
        json={
            "station_code": "STA-1",
            "line_number": "L1",
            "occupancy_start": "2026-03-01T10:00:00",
        },
    )
    assert occupancy_missing_status.status_code == 422

    event_missing_datetime = client.post(
        "/api/coa/events", json={"train_id": train["id"], "event_type": "CAUTION"}
    )
    assert event_missing_datetime.status_code == 422


def test_invalid_movement_flag(client):
    source = create_coa_source(client)
    train = create_train(client, source)

    response = client.post(
        "/api/coa/movements",
        json={
            "train_id": train["id"],
            "station_code": "STA-1",
            "movement_flag": "X",
            "movement_datetime": "2026-03-01T10:00:00",
        },
    )

    assert response.status_code == 422


def test_create_and_read_available_window(client):
    seed_derivation_data(client)
    windows = generate(client)

    assert len(windows) >= 1
    window = windows[0]

    response = client.get(f"/api/coa/available-windows/{window['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == window["id"]
    assert response.json()["window_status"] == "AVAILABLE"


def test_filter_available_window_by_station(client):
    seed_derivation_data(client)
    generate(client)

    response = client.get("/api/coa/available-windows?station_code=STA-1")

    assert response.status_code == 200
    assert all(w["station_code"] == "STA-1" for w in response.json())
    assert len(response.json()) == 1


def test_filter_available_window_by_line(client):
    seed_derivation_data(client)
    generate(client)

    response = client.get("/api/coa/available-windows?line_number=L2")

    assert response.status_code == 200
    assert all(w["line_number"] == "L2" for w in response.json())
    assert len(response.json()) == 1


def test_filter_available_window_by_status(client):
    seed_derivation_data(client)
    generate(client)

    response = client.get("/api/coa/available-windows?window_status=AVAILABLE")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all(w["window_status"] == "AVAILABLE" for w in response.json())

    unknown = client.get("/api/coa/available-windows?window_status=UNKNOWN")
    assert unknown.status_code == 200
    assert unknown.json() == []


def test_deterministic_available_window_derivation(client):
    seed_derivation_data(client)
    windows = generate(client)
    windows = generate(client)

    assert len(windows) == 2
    sta1 = [w for w in windows if w["station_code"] == "STA-1"][0]
    sta2 = [w for w in windows if w["station_code"] == "STA-2"][0]

    assert sta1["window_start"] == "2026-03-01T10:20:00"
    assert sta1["window_end"] == "2026-03-01T10:40:00"
    assert sta1["window_status"] == "AVAILABLE"

    assert sta2["window_start"] == "2026-03-01T10:30:00"
    assert sta2["window_end"] == "2026-03-01T10:50:00"


def test_correct_duration_minutes_calculation(client):
    seed_derivation_data(client)
    windows = generate(client)

    expected = {
        "STA-1": 20,
        "STA-2": 20,
    }
    assert len(windows) == 2
    for window in windows:
        assert window["duration_minutes"] == expected[window["station_code"]]
        assert window["window_end"] >= window["window_start"]


def test_generated_window_does_not_overlap_occupied_interval(client, db_session):
    seed_derivation_data(client)
    windows = generate(client)

    occupancy_rows = db_session.scalars(select(LineOccupancy)).all()
    for window in windows:
        for occ in occupancy_rows:
            if (
                occ.station_code == window["station_code"]
                and occ.line_number == window["line_number"]
                and occ.occupancy_end is not None
            ):
                assert not (
                    window["window_start"] < occ.occupancy_end.isoformat()
                    and occ.occupancy_start.isoformat() < window["window_end"]
                ), f"window overlaps occupancy {occ.id}"


def test_generation_does_not_modify_source_records(client, db_session):
    seed_derivation_data(client)

    train_count = db_session.scalar(select(func.count()).select_from(Train))
    movement_count = db_session.scalar(
        select(func.count()).select_from(TrainMovement)
    )
    schedule_count = db_session.scalar(
        select(func.count()).select_from(TrainSchedule)
    )
    occupancy_count = db_session.scalar(
        select(func.count()).select_from(LineOccupancy)
    )
    event_count = db_session.scalar(
        select(func.count()).select_from(OperationalEvent)
    )

    generate(client)

    assert db_session.scalar(select(func.count()).select_from(Train)) == train_count
    assert (
        db_session.scalar(select(func.count()).select_from(TrainMovement))
        == movement_count
    )
    assert (
        db_session.scalar(select(func.count()).select_from(TrainSchedule))
        == schedule_count
    )
    assert (
        db_session.scalar(select(func.count()).select_from(LineOccupancy))
        == occupancy_count
    )
    assert (
        db_session.scalar(select(func.count()).select_from(OperationalEvent))
        == event_count
    )


def test_generation_does_not_assign_maintenance(client, db_session):
    seed_derivation_data(client)
    windows = generate(client)

    assert all(
        "maintenance" not in field_name for window in windows for field_name in window
    )

    for model in (TMSMaintenance, TDMSMaintenance, SMMSMaintenance):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0


def test_no_ai_planning_fields_exist(db_session):
    inspector = inspect(db_session.bind)
    for table in (
        "train",
        "train_movement",
        "train_schedule",
        "line_occupancy",
        "operational_event",
        "available_window",
    ):
        columns = {col["name"] for col in inspector.get_columns(table)}
        assert columns.isdisjoint(FORBIDDEN_COLUMNS), (
            f"{table} contains forbidden AI/planning columns: "
            f"{columns & FORBIDDEN_COLUMNS}"
        )


def test_full_relationship_traceability(client, db_session):
    source, train = seed_derivation_data(client)
    windows = generate(client)

    sta1 = [w for w in windows if w["station_code"] == "STA-1"][0]

    tr = db_session.get(Train, train["id"])
    assert len(tr.movements) == 1
    assert len(tr.schedules) == 2
    assert len(tr.occupancies) == 2
    assert len(tr.events) == 1
    assert tr.source_system.system_code == "COA"

    window_occ = db_session.get(LineOccupancy, sta1["source_occupancy_id"])
    assert window_occ is not None
    assert window_occ.train_id == train["id"]

    trace_db = db_session.execute(
        select(Train, LineOccupancy).join(
            Train, Train.id == LineOccupancy.train_id
        ).where(LineOccupancy.id == window_occ.id)
    ).first()
    assert trace_db is not None
    assert trace_db[0].source_system.system_code == "COA"