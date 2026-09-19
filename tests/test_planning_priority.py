"""STEP 12 tests: deterministic criticality & priority foundation.

Covers model constraints, the deterministic scoring formula, enumeration
validation, factor derivation rules, fallback behaviour, API endpoints,
filters, recalculation idempotency and source-data preservation.
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.core.database import Base
from app.models.block_requirement import BlockRequirement
from app.models.defect_failure import DefectFailure
from app.models.maintenance_requirement import MaintenanceRequirement
from app.models.planning_priority import PlanningPriority
from app.models.planning_task import PlanningTask
from app.models.source_system import SourceSystem
from app.routers.planning_priority import router as planning_priority_router
from app.schemas.planning_priority import PlanningPriorityResponse
from app.services.planning_priority import (
    CALCULATION_VERSION,
    calculate_priority_band,
    calculate_priority_score,
    create_or_update_priority,
    defect_age_bucket,
    derive_priority_factors,
    recalculate_all_priorities,
)

REF = datetime(2026, 9, 1, 0, 0, 0)


# --------------------------------------------------------------------------- #
# Chain helpers
# --------------------------------------------------------------------------- #
def create_source(client, code="TMS"):
    response = client.post(
        "/api/source-systems",
        json={
            "system_code": code,
            "system_name": code,
            "description": f"TEST/SYNTHETIC {code} source system for STEP 12.",
        },
    )
    if response.status_code == 201:
        return response.json()
    if response.status_code == 409:
        listing = client.get("/api/source-systems").json()
        return next(s for s in listing if s["system_code"] == code)
    assert False, response.text


_ASSET_COUNTER = 0


def _next_asset_id(source, suffix):
    global _ASSET_COUNTER
    _ASSET_COUNTER += 1
    return f"{suffix}-PRIORITY-ASSET-{_ASSET_COUNTER}"


def create_asset(client, source, suffix):
    response = client.post(
        "/api/assets",
        json={
            "source_system_id": source["id"],
            "source_asset_id": _next_asset_id(source, suffix),
            "asset_type": "TEST/SYNTHETIC",
            "asset_name": f"TEST/SYNTHETIC {suffix} Asset",
            "status": "TEST",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_tms_chain(client, asset, code, start, end, severity="HIGH"):
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
    payload = {
        "asset_id": asset["id"],
        "inspection_id": inspection["id"],
        "defect_code": code,
        "defect_description": "TEST/SYNTHETIC TMS defect observed.",
        "detected_date": start,
        "status": "OPEN",
        "remarks": "TEST/SYNTHETIC TMS defect remarks.",
    }
    if severity is not None:
        payload["severity"] = severity
    defect = client.post("/api/tms/defects", json=payload)
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


def add_block_requirement(client, mr_id, **overrides):
    payload = {
        "maintenance_requirement_id": mr_id,
        "station_code": "STA-7",
        "line_number": "L7",
        "block_type": "INTEGRATED_BLOCK",
        "required_duration_minutes": 120,
        "power_block_required": False,
        "traffic_block_required": False,
        "resource_notes": "TEST/SYNTHETIC resource note.",
        "status": "REQUIRED",
        "remarks": "TEST/SYNTHETIC block requirement.",
    }
    payload.update(overrides)
    response = client.post("/api/unified/block-requirements", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def setup_chain(client, db_session, *, severity="HIGH", start="2026-08-12T00:00:00",
                block=None, end="2026-08-12T04:00:00"):
    """Create one planning task via the full API chain."""
    source = create_source(client)
    asset = create_asset(client, source, "STEP12")
    _, defect, maintenance = add_tms_chain(
        client, asset, "TMS-DF-001", start, end, severity=severity
    )
    client.post("/api/unified/normalize/tms")
    requirements = client.get("/api/unified/maintenance").json()
    mr = [
        m for m in requirements
        if m["source_record_type"] == "TMS_MAINTENANCE"
        and m["source_record_id"] == maintenance["id"]
    ][0]
    if block is not None:
        block_json = add_block_requirement(client, mr["id"], **block)
    else:
        block_json = None
    client.post("/api/planning/generate-tasks")
    tasks = client.get(f"/api/planning/tasks?maintenance_requirement_id={mr['id']}").json()
    assert len(tasks) == 1, tasks
    task = tasks[0]
    task_obj = db_session.get(PlanningTask, task["id"])
    assert task_obj is not None
    return {"source": source, "asset": asset, "defect": defect,
            "mr": mr, "task": task, "task_id": task["id"], "task_obj": task_obj,
            "asset_id": asset["id"], "block_json": block_json,
            "block_id": block_json["id"] if block_json else None}


def build_task_without_defect(db_session):
    """Planning task whose requirement has no defect/failure provenance."""
    source = db_session.scalar(select(SourceSystem))
    if source is None:
        source = SourceSystem(system_code="TMS", system_name="Test TMS")
        db_session.add(source)
        db_session.flush()
    from app.models.asset import AssetMaster

    asset = AssetMaster(
        source_system_id=source.id,
        source_asset_id="PRIO-NO-DEFECT",
        asset_type="TRACK",
        asset_name="No-defect asset",
        status="TEST",
    )
    db_session.add(asset)
    db_session.flush()
    mr = MaintenanceRequirement(
        asset_id=asset.id,
        source_system_id=source.id,
        source_record_type="TMS_MAINTENANCE",
        source_record_id=777001,
        maintenance_type="REPAIR",
        description="Requirement without defect linkage",
        required_duration_minutes=120,
        status="PENDING",
    )
    db_session.add(mr)
    db_session.flush()
    from app.services.planning_foundation import generate_planning_tasks

    generate_planning_tasks(db_session)
    task = db_session.scalar(
        select(PlanningTask).where(PlanningTask.asset_id == asset.id)
    )
    assert task is not None
    return task


def add_extra_defect_failure(db_session, chain, source_record_id, detected_at, severity="HIGH"):
    defect = DefectFailure(
        asset_id=chain["asset_id"],
        source_system_id=chain["source"]["id"],
        source_record_type="TMS_DEFECT",
        source_record_id=source_record_id,
        defect_code="TMS-DF-EXTRA",
        severity=severity,
        detected_at=detected_at,
        status="OPEN",
    )
    db_session.add(defect)
    db_session.commit()


def stored(db_session, task_id):
    return db_session.scalar(
        select(PlanningPriority).where(PlanningPriority.planning_task_id == task_id)
    )


# --------------------------------------------------------------------------- #
# 1-3. Model: creation, FK, unique
# --------------------------------------------------------------------------- #
def test_model_creation(db_session):
    task = build_task_without_defect(db_session)
    priority = PlanningPriority(
        planning_task_id=task.id,
        criticality_level="LOW",
        urgency_level="LOW",
        safety_impact="NONE",
        asset_availability_impact="LOW",
        traffic_impact="NONE",
        failure_recurrence="NONE",
        defect_age_days=0,
        priority_score=3.5,
        priority_band="LOW",
        calculation_version=CALCULATION_VERSION,
        calculation_reason="test",
    )
    db_session.add(priority)
    db_session.commit()
    assert priority.id is not None
    assert priority.planning_task_id == task.id
    assert float(priority.priority_score) == 3.5
    assert priority.priority_band == "LOW"


def test_fk_to_planning_task(db_session):
    bad = PlanningPriority(
        planning_task_id=999999,
        criticality_level="LOW",
        urgency_level="LOW",
        safety_impact="NONE",
        asset_availability_impact="LOW",
        traffic_impact="NONE",
        failure_recurrence="NONE",
        defect_age_days=0,
        priority_score=3.5,
        priority_band="LOW",
        calculation_version=CALCULATION_VERSION,
        calculation_reason="test",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_planning_task_id(db_session):
    task = build_task_without_defect(db_session)
    create_or_update_priority(db_session, task, reference_time=REF)
    create_or_update_priority(db_session, task, reference_time=REF)
    count = db_session.scalar(
        select(func.count()).select_from(PlanningPriority).where(
            PlanningPriority.planning_task_id == task.id
        )
    )
    assert count == 1


def test_unique_constraint_in_metadata(db_session):
    table = Base.metadata.tables["planning_priority"]
    names = {u.name: u for u in table.constraints if u.name is not None}
    assert "uq_planning_priority_planning_task" in names


# --------------------------------------------------------------------------- #
# 4. Enum / value validation
# --------------------------------------------------------------------------- #
def test_enum_value_validation():
    payload = dict(
        id=1,
        planning_task_id=1,
        criticality_level="LOW",
        urgency_level="LOW",
        safety_impact="NONE",
        asset_availability_impact="LOW",
        traffic_impact="NONE",
        failure_recurrence="NONE",
        defect_age_days=0,
        priority_score=3.5,
        priority_band="LOW",
        calculation_version=CALCULATION_VERSION,
        calculated_at=datetime(2026, 9, 1),
        created_at=datetime(2026, 9, 1),
        updated_at=datetime(2026, 9, 1),
    )
    assert PlanningPriorityResponse(**payload).priority_band == "LOW"
    for field, bad in (
        ("criticality_level", "SUPER_DUPER"),
        ("urgency_level", "MAYBE"),
        ("safety_impact", "NONE_OR_OTHER"),
        ("asset_availability_impact", "BIG"),
        ("traffic_impact", "HIGHER"),
        ("failure_recurrence", "ALWAYS"),
        ("priority_band", "SOMETIMES"),
    ):
        broken = dict(payload)
        broken[field] = bad
        with pytest.raises(ValidationError):
            PlanningPriorityResponse(**broken)


def test_invalid_factor_value_rejected_in_score():
    with pytest.raises(KeyError):
        calculate_priority_score(
            {
                "criticality_level": "UNKNOWN",
                "urgency_level": "LOW",
                "safety_impact": "NONE",
                "asset_availability_impact": "LOW",
                "traffic_impact": "NONE",
                "failure_recurrence": "NONE",
                "defect_age_days": 0,
            }
        )


# --------------------------------------------------------------------------- #
# 5-7. Score calculation, rounding, range
# --------------------------------------------------------------------------- #
def test_score_calculation_low_case():
    factors = {
        "criticality_level": "LOW",
        "urgency_level": "LOW",
        "safety_impact": "LOW",
        "asset_availability_impact": "LOW",
        "traffic_impact": "NONE",
        "failure_recurrence": "LOW",
        "defect_age_days": 20,
    }
    score, band = calculate_priority_score(factors)
    assert score == 15.25
    assert band == "LOW"


def test_score_calculation_critical_case():
    factors = {
        "criticality_level": "CRITICAL",
        "urgency_level": "IMMEDIATE",
        "safety_impact": "CRITICAL",
        "asset_availability_impact": "HIGH",
        "traffic_impact": "HIGH",
        "failure_recurrence": "HIGH",
        "defect_age_days": 100,
    }
    score, band = calculate_priority_score(factors)
    assert score == 94.0
    assert band == "CRITICAL"


def test_score_calculation_high_case():
    factors = {
        "criticality_level": "HIGH",
        "urgency_level": "HIGH",
        "safety_impact": "HIGH",
        "asset_availability_impact": "MEDIUM",
        "traffic_impact": "HIGH",
        "failure_recurrence": "MEDIUM",
        "defect_age_days": 5,
    }
    score, band = calculate_priority_score(factors)
    assert score == 62.5
    assert band == "HIGH"


def test_score_rounding_to_two_decimals():
    factors = {
        "criticality_level": "MEDIUM",
        "urgency_level": "LOW",
        "safety_impact": "HIGH",
        "asset_availability_impact": "MEDIUM",
        "traffic_impact": "MEDIUM",
        "failure_recurrence": "HIGH",
        "defect_age_days": 8,
    }
    score, _ = calculate_priority_score(factors)
    assert isinstance(score, float)
    rounded = round(score, 2)
    assert score == rounded, "score must be pre-rounded to 2 decimals"


def test_score_stays_in_range():
    minimum = calculate_priority_score(
        {
            "criticality_level": "LOW",
            "urgency_level": "LOW",
            "safety_impact": "NONE",
            "asset_availability_impact": "NONE",
            "traffic_impact": "NONE",
            "failure_recurrence": "NONE",
            "defect_age_days": 0,
        }
    )[0]
    maximum = calculate_priority_score(
        {
            "criticality_level": "CRITICAL",
            "urgency_level": "IMMEDIATE",
            "safety_impact": "CRITICAL",
            "asset_availability_impact": "CRITICAL",
            "traffic_impact": "CRITICAL",
            "failure_recurrence": "HIGH",
            "defect_age_days": 1000,
        }
    )[0]
    assert 0.0 <= minimum <= maximum <= 100.0


# --------------------------------------------------------------------------- #
# 8. Priority band boundaries
# --------------------------------------------------------------------------- #
def test_priority_band_boundaries():
    assert calculate_priority_band(0.00) == "LOW"
    assert calculate_priority_band(24.99) == "LOW"
    assert calculate_priority_band(25.00) == "MEDIUM"
    assert calculate_priority_band(49.99) == "MEDIUM"
    assert calculate_priority_band(50.00) == "HIGH"
    assert calculate_priority_band(74.99) == "HIGH"
    assert calculate_priority_band(75.00) == "CRITICAL"
    assert calculate_priority_band(100.00) == "CRITICAL"


# --------------------------------------------------------------------------- #
# 9-15. Factor mapping tests
# --------------------------------------------------------------------------- #
def test_criticality_mapping(db_session, client):
    chain = setup_chain(client, db_session, severity="CRITICAL")
    factors = derive_priority_factors(db_session, chain["task_obj"], reference_time=REF)
    assert factors.criticality_level == "CRITICAL"
    chain2 = setup_chain(
        client, db_session, severity="LOW",
        start="2026-08-13T00:00:00", end="2026-08-13T04:00:00",
    )
    assert derive_priority_factors(
        db_session, chain2["task_obj"], reference_time=REF
    ).criticality_level == "LOW"


def test_urgency_mapping():
    from app.services.planning_priority import _derive_urgency

    assert _derive_urgency(None, REF)[0] == "LOW"
    assert _derive_urgency(REF - timedelta(days=1), REF)[0] == "IMMEDIATE"
    assert _derive_urgency(REF + timedelta(hours=6), REF)[0] == "IMMEDIATE"
    assert _derive_urgency(REF + timedelta(days=3), REF)[0] == "HIGH"
    assert _derive_urgency(REF + timedelta(days=15), REF)[0] == "MEDIUM"
    assert _derive_urgency(REF + timedelta(days=90), REF)[0] == "LOW"


def test_safety_mapping():
    from app.services.planning_priority import _derive_safety_and_criticality

    for severity, expected in (
        ("CRITICAL", "CRITICAL"),
        ("HIGH", "HIGH"),
        ("MEDIUM", "MEDIUM"),
        ("LOW", "LOW"),
    ):
        safety, _, _ = _derive_safety_and_criticality(severity)
        assert safety == expected
    safety, criticality, _ = _derive_safety_and_criticality(None)
    assert (safety, criticality) == ("NONE", "LOW")
    safety, criticality, _ = _derive_safety_and_criticality("minor")
    assert (safety, criticality) == ("NONE", "LOW")


def test_availability_impact_mapping(client, db_session):
    from app.services.planning_priority import _derive_availability_impact

    chain = setup_chain(
        client, db_session,
        block={"power_block_required": True, "traffic_block_required": True},
    )
    block = db_session.get(BlockRequirement, chain["block_id"])
    assert block is not None
    assert _derive_availability_impact(None)[0] == "LOW"
    assert _derive_availability_impact(block)[0] == "HIGH"
    block.power_block_required = True
    block.traffic_block_required = False
    db_session.flush()
    assert _derive_availability_impact(block)[0] == "MEDIUM"
    block.power_block_required = False
    block.traffic_block_required = True
    db_session.flush()
    assert _derive_availability_impact(block)[0] == "MEDIUM"
    block.power_block_required = False
    block.traffic_block_required = False
    db_session.flush()
    assert _derive_availability_impact(block)[0] == "LOW"


def test_traffic_impact_mapping(db_session, client):
    chain = setup_chain(client, db_session, block={"traffic_block_required": True})
    factors = derive_priority_factors(db_session, chain["task_obj"], reference_time=REF)
    assert factors.traffic_impact == "HIGH"
    chain2 = setup_chain(
        client, db_session, severity="LOW",
        start="2026-08-14T00:00:00", end="2026-08-14T04:00:00",
    )
    assert derive_priority_factors(
        db_session, chain2["task_obj"], reference_time=REF
    ).traffic_impact == "NONE"


def test_recurrence_mapping(db_session, client):
    chain = setup_chain(client, db_session)
    from app.services.planning_priority import _derive_recurrence

    assert _derive_recurrence(db_session, chain["asset_id"], REF)[0] == "LOW"
    add_extra_defect_failure(db_session, chain, 900001, REF - timedelta(days=10))
    assert _derive_recurrence(db_session, chain["asset_id"], REF)[0] == "MEDIUM"
    add_extra_defect_failure(db_session, chain, 900002, REF - timedelta(days=20))
    assert _derive_recurrence(db_session, chain["asset_id"], REF)[0] == "HIGH"
    outside = _derive_recurrence(db_session, chain["asset_id"], REF + timedelta(days=400))
    assert outside[0] == "NONE"


def test_defect_age_bucket_mapping():
    assert defect_age_bucket(0) == 10
    assert defect_age_bucket(7) == 10
    assert defect_age_bucket(8) == 30
    assert defect_age_bucket(30) == 30
    assert defect_age_bucket(31) == 60
    assert defect_age_bucket(90) == 60
    assert defect_age_bucket(91) == 100
    assert defect_age_bucket(9999) == 100


# --------------------------------------------------------------------------- #
# 16-17. Missing-data fallback + no negative age
# --------------------------------------------------------------------------- #
def test_missing_data_fallback(db_session):
    task = build_task_without_defect(db_session)
    factors = derive_priority_factors(db_session, task, reference_time=REF)
    assert factors.criticality_level == "LOW"
    assert factors.safety_impact == "NONE"
    assert factors.urgency_level == "LOW"
    assert factors.asset_availability_impact == "LOW"
    assert factors.traffic_impact == "NONE"
    assert factors.failure_recurrence == "NONE"
    assert factors.defect_age_days == 0


def test_no_negative_defect_age(client, db_session):
    chain = setup_chain(
        client, db_session,
        start=(REF + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S"),
        end=(REF + timedelta(days=2, hours=4)).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    factors = derive_priority_factors(db_session, chain["task_obj"], reference_time=REF)
    assert factors.defect_age_days == 0
    assert factors.defect_age_days >= 0


def test_defect_age_days_computed_floor_days(client, db_session):
    chain = setup_chain(client, db_session)  # detected 2026-08-12T00:00:00
    factors = derive_priority_factors(db_session, chain["task_obj"], reference_time=REF)
    assert factors.defect_age_days == 20  # REF - 20 days


# --------------------------------------------------------------------------- #
# 18-19. Idempotency + update-in-place
# --------------------------------------------------------------------------- #
def test_idempotent_recalculation(client, db_session):
    chain = setup_chain(client, db_session)
    first = create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    second = create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    assert first.id == second.id
    assert float(first.priority_score) == float(second.priority_score)
    count = db_session.scalar(
        select(func.count()).select_from(PlanningPriority).where(
            PlanningPriority.planning_task_id == chain["task_id"]
        )
    )
    assert count == 1


def test_recalculation_updates_existing_not_duplicate(client, db_session):
    chain = setup_chain(client, db_session)
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    before = stored(db_session, chain["task_id"])
    assert before.failure_recurrence == "LOW"
    add_extra_defect_failure(db_session, chain, 900003, REF - timedelta(days=10))
    add_extra_defect_failure(db_session, chain, 900004, REF - timedelta(days=20))
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    after = stored(db_session, chain["task_id"])
    assert after.id == before.id
    assert after.failure_recurrence == "HIGH"
    count = db_session.scalar(
        select(func.count()).select_from(PlanningPriority).where(
            PlanningPriority.planning_task_id == chain["task_id"]
        )
    )
    assert count == 1


# --------------------------------------------------------------------------- #
# 20-24. API
# --------------------------------------------------------------------------- #
def test_api_get_list(client, db_session):
    chain = setup_chain(client, db_session)
    assert client.get("/api/planning/priority").json() == []
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    listing = client.get("/api/planning/priority").json()
    assert len(listing) == 1
    assert listing[0]["planning_task_id"] == chain["task_id"]


def test_api_get_single(client, db_session):
    chain = setup_chain(client, db_session)
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    row = stored(db_session, chain["task_id"])
    body = client.get(f"/api/planning/priority/{row.id}").json()
    assert body["id"] == row.id
    assert client.get("/api/planning/priority/999999").status_code == 404


def test_api_task_specific_get(client, db_session):
    chain = setup_chain(client, db_session)
    assert client.get(
        f"/api/planning/tasks/{chain['task_id']}/priority"
    ).status_code == 404
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    body = client.get(f"/api/planning/tasks/{chain['task_id']}/priority").json()
    assert body["planning_task_id"] == chain["task_id"]
    assert client.get("/api/planning/tasks/999999/priority").status_code == 404


def test_api_recalculation_single(client, db_session):
    chain = setup_chain(client, db_session)
    response = client.post(f"/api/planning/tasks/{chain['task_id']}/priority/recalculate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["planning_task_id"] == chain["task_id"]
    assert body["calculation_version"] == CALCULATION_VERSION
    assert body["priority_band"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert 0 <= body["priority_score"] <= 100
    assert body["calculation_reason"]
    count = db_session.scalar(
        select(func.count()).select_from(PlanningPriority)
    )
    assert count == 1
    assert client.post("/api/planning/tasks/999999/priority/recalculate").status_code == 404


def test_api_recalculation_all(client, db_session):
    setup_chain(client, db_session)
    first = client.post("/api/planning/priority/recalculate")
    assert first.status_code == 200, first.text
    assert first.json() == {"processed": 1, "created": 1, "updated": 0}
    second = client.post("/api/planning/priority/recalculate")
    assert second.json() == {"processed": 1, "created": 0, "updated": 1}
    assert db_session.scalar(
        select(func.count()).select_from(PlanningPriority)
    ) == 1


def test_api_static_recalculate_not_captured_by_priority_id(client, db_session):
    """Regression: POST /api/planning/priority/recalculate must reach the
    static recalc handler, NOT be captured by the dynamic
    GET /api/planning/priority/{priority_id} integer route (which would raise
    422 int_parsing for the 'recalculate' path segment)."""
    response = client.post("/api/planning/priority/recalculate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    assert body.keys() == {"processed", "created", "updated"}
    assert all(isinstance(v, int) for v in body.values())


def test_router_registers_static_route_before_dynamic_route():
    """Static paths must be registered before overlapping dynamic paths.

    FastAPI resolves routes in registration order, so the static
    POST /priority/recalculate route must precede the dynamic
    GET /priority/{priority_id} route; otherwise older FastAPI/Starlette
    stacks capture 'recalculate' as an integer path parameter and return 422.
    """
    paths = [route.path for route in planning_priority_router.routes]
    static = paths.index("/api/planning/priority/recalculate")
    dynamic = paths.index("/api/planning/priority/{priority_id}")
    assert (
        static < dynamic
    ), "static POST /priority/recalculate must be registered before the dynamic {priority_id} route"


def test_api_filters(client, db_session):
    chain = setup_chain(client, db_session)
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    all_rows = client.get("/api/planning/priority").json()
    assert len(all_rows) == 1
    band = all_rows[0]["priority_band"]
    score = all_rows[0]["priority_score"]
    assert len(client.get(f"/api/planning/priority?priority_band={band}").json()) == 1
    assert len(client.get("/api/planning/priority?priority_band=BOGUS").json()) == 0
    assert len(client.get(
        f"/api/planning/priority?criticality_level={all_rows[0]['criticality_level']}"
    ).json()) == 1
    assert len(client.get(
        f"/api/planning/priority?urgency_level={all_rows[0]['urgency_level']}"
    ).json()) == 1
    assert len(client.get(
        f"/api/planning/priority?min_score={score}&max_score={score}"
    ).json()) == 1
    assert len(client.get(
        f"/api/planning/priority?min_score={score + 0.01}"
    ).json()) == 0
    assert len(client.get(
        f"/api/planning/priority?asset_id={chain['asset_id']}"
    ).json()) == 1
    assert len(client.get("/api/planning/priority?asset_id=999999").json()) == 0


def test_invalid_values_return_422(client, db_session):
    assert client.get("/api/planning/priority?min_score=abc").status_code == 422
    assert client.get("/api/planning/priority/abc").status_code == 422
    assert client.get("/api/planning/tasks/abc/priority").status_code == 422
    assert client.post("/api/planning/tasks/abc/priority/recalculate").status_code == 422


# --------------------------------------------------------------------------- #
# 25-28. Integrity, version, reason, determinism
# --------------------------------------------------------------------------- #
def test_no_source_table_data_modified(client, db_session):
    chain = setup_chain(client, db_session)
    tables = (
        "source_system", "tms_inspection", "tms_defect", "tms_maintenance",
        "defect_failure", "maintenance_requirement", "block_requirement",
        "planning_task", "available_window", "candidate_block_window",
    )
    before = {
        t: db_session.scalar(select(func.count()).select_from(Base.metadata.tables[t]))
        for t in tables
    }
    client.post("/api/planning/priority/recalculate")
    client.get("/api/planning/priority")
    after = {
        t: db_session.scalar(select(func.count()).select_from(Base.metadata.tables[t]))
        for t in tables
    }
    assert after == before


def test_no_ai_fields_on_source_tables(db_session):
    forbidden = ("priority", "score", "prediction", "rank", "confidence")
    source_tables = (
        "tms_inspection", "tms_defect", "tms_maintenance",
        "tdms_inspection", "tdms_failure", "tdms_maintenance",
        "smms_inspection", "smms_alert", "smms_maintenance",
        "train", "train_movement", "train_schedule",
        "line_occupancy", "operational_event", "available_window",
        "planning_task", "maintenance_requirement", "block_requirement",
        "defect_failure",
    )
    for table in source_tables:
        columns = {c["name"].lower() for c in inspect(db_session.bind).get_columns(table)}
        for column in columns:
            for token in forbidden:
                assert token not in column, f"{table}.{column} contains {token}"


def test_calculation_version_stored(client, db_session):
    chain = setup_chain(client, db_session)
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    row = stored(db_session, chain["task_id"])
    assert row.calculation_version == CALCULATION_VERSION
    assert CALCULATION_VERSION == "STEP12-DETERMINISTIC-1.0"


def test_calculation_reason_stored(client, db_session):
    chain = setup_chain(client, db_session)
    create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    row = stored(db_session, chain["task_id"])
    assert row.calculation_reason
    assert "criticality=" in row.calculation_reason
    assert "urgency=" in row.calculation_reason
    assert "defect_age_days=" in row.calculation_reason


def test_deterministic_same_input_same_score(client, db_session):
    chain = setup_chain(client, db_session)
    a = create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    b = create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    assert float(a.priority_score) == float(b.priority_score)
    assert a.calculation_reason == b.calculation_reason
    assert a.priority_band == b.priority_band


# --------------------------------------------------------------------------- #
# Extra
# --------------------------------------------------------------------------- #
def test_on_delete_restrict_metadata(db_session):
    table = Base.metadata.tables["planning_priority"]
    fk = list(table.columns["planning_task_id"].foreign_keys)[0]
    assert fk.target_fullname == "planning_task.id"
    assert fk.ondelete == "RESTRICT"


def test_full_egress_end_to_end_scenario(client, db_session):
    chain = setup_chain(
        client, db_session, severity="CRITICAL",
        block={"traffic_block_required": True, "power_block_required": True,
               "latest_end": (REF - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")},
    )
    add_extra_defect_failure(db_session, chain, 900011, REF - timedelta(days=100))
    add_extra_defect_failure(db_session, chain, 900012, REF - timedelta(days=200))
    row = create_or_update_priority(db_session, chain["task_obj"], reference_time=REF)
    factors = derive_priority_factors(db_session, chain["task_obj"], reference_time=REF)
    assert factors.criticality_level == "CRITICAL"
    assert factors.urgency_level == "IMMEDIATE"
    assert factors.safety_impact == "CRITICAL"
    assert factors.asset_availability_impact == "HIGH"
    assert factors.traffic_impact == "HIGH"
    assert factors.failure_recurrence == "HIGH"
    # detected_at = 2026-08-12, REF = 2026-09-01 -> 20 days -> bucket 30
    assert factors.defect_age_days == 20
    score, band = calculate_priority_score(
        {
            "criticality_level": factors.criticality_level,
            "urgency_level": factors.urgency_level,
            "safety_impact": factors.safety_impact,
            "asset_availability_impact": factors.asset_availability_impact,
            "traffic_impact": factors.traffic_impact,
            "failure_recurrence": factors.failure_recurrence,
            "defect_age_days": factors.defect_age_days,
        }
    )
    assert band == "CRITICAL"
    assert float(row.priority_score) == score
    assert row.priority_band == "CRITICAL"


def test_recalculate_all_priorities_service(db_session):
    task = build_task_without_defect(db_session)
    stats = recalculate_all_priorities(db_session, reference_time=REF)
    assert stats["processed"] == 1
    assert stats["created"] == 1
    assert stats["updated"] == 0
    row = stored(db_session, task.id)
    assert row is not None
    second = recalculate_all_priorities(db_session, reference_time=REF)
    assert second["created"] == 0 and second["updated"] == 1


def test_api_band_is_consistent_with_service(client, db_session):
    chain = setup_chain(client, db_session)
    body = client.post(
        f"/api/planning/tasks/{chain['task_id']}/priority/recalculate"
    ).json()
    assert body["priority_band"] == calculate_priority_band(body["priority_score"])