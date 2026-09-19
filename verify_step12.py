"""STEP 12 live verification: criticality & priority foundation.

Runs a real uvicorn server against the live PostgreSQL database and verifies:

1. Alembic single head e1a9c2f3b7d5 on the live database, planning_priority
   empty at baseline.
2. ``planning_priority`` table exists with id PK, RESTRICT FK to
   planning_task, UNIQUE planning_task_id, score range + non-negative defect
   age checks, expected indexes, and NO forbidden AI columns on STEP 12 or
   source tables.
3. Deterministic derivation E2E via the API chain (TMS defect -> unified ->
   block requirement -> planning task -> priority recalc): a CRITICAL severity
   task with an urgent (already-past) power+traffic block scores strictly
   higher than a LOW severity task with no block; band mapping, score range,
   version, and reasons are checked.
4. Idempotency: single task recalc twice keeps one row; global recalc updates
   the already-computed rows and creates exactly the missing ones.
5. Filters (priority_band, criticality_level, urgency_level, min_score,
   max_score, asset_id) and 404/422 HTTP semantics, scoped to synthetic rows.
6. Provenance from planning_priority back to the TMS source record.
7. Source/unified/planning layer row counts are unchanged by STEP 12 writes
   (delta-based relative to a snapshot taken before recalculations).
8. FK-safe cleanup that removes only the synthetic rows this script created
   (plus the planning_priority rows it produced) and preserves pre-existing
   data and seed source systems.

No AI/ML/ranking/optimization algorithm is executed anywhere.
"""

import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine, inspect, text

from app.core.database import SessionLocal

PROJECT_ROOT = Path(__file__).resolve().parent
ENG = create_engine("postgresql+psycopg2://postgres:root@localhost:5432/sih_26027")
PORT = 8012
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{PORT}"

TAG = "VERIFY12"
TAG_CAUSE = "STEP12-SYNTHETIC"
RUN_ID = datetime.now().strftime("%Y%m%d%H%M%S")

FORBIDDEN_TOKENS = [
    "score", "confidence", "prediction", "recommended", "optimal",
    "embedding", "feature_vector", "probability", "priority", "risk", "rank",
]

SOURCE_TABLES = [
    "tms_inspection", "tms_defect", "tms_maintenance",
    "tdms_inspection", "tdms_failure", "tdms_maintenance",
    "smms_inspection", "smms_alert", "smms_maintenance",
    "train", "train_movement", "train_schedule",
    "line_occupancy", "operational_event", "available_window",
]

PLANNING_TABLES = [
    "planning_task", "planning_constraint", "planning_resource",
    "task_resource", "task_dependency",
]

INTEGRITY_TABLES = SOURCE_TABLES + PLANNING_TABLES + [
    "defect_failure", "maintenance_requirement", "block_requirement",
    "candidate_block_window",
]

server = None
client = None
assets_created = []
my_task_ids = []


def log(title):
    print(f"\n=== {title} ===")


def q(sql, params=None):
    with ENG.connect() as c:
        return c.execute(text(sql), params or {}).fetchall()


def counts():
    existing = {r[0] for r in q(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public'")}
    return {
        t: q(f"SELECT count(*) FROM {t}")[0][0]
        for t in INTEGRITY_TABLES if t in existing
    }


def start_server():
    global server
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        if server.poll() is not None:
            out = server.stdout.read().decode(errors="replace")
            raise RuntimeError(f"uvicorn exited early:\n{out}")
        try:
            with httpx.Client(base_url=BASE_URL, timeout=2) as c:
                if c.get("/health").status_code == 200:
                    return
        except httpx.HTTPError:
            time.sleep(0.5)
    raise RuntimeError("uvicorn did not become healthy in time")


def stop_server():
    if server is not None and server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def get_source_system(code):
    for row in client.get("/api/source-systems").json():
        if row["system_code"] == code:
            return row
    raise RuntimeError(f"source system {code} not found")


def create_asset(source_id, suffix):
    r = client.post("/api/assets", json={
        "source_system_id": source_id,
        "source_asset_id": f"{TAG}-{RUN_ID}-{suffix}-ASSET-1",
        "asset_type": "TEST/SYNTHETIC",
        "asset_name": f"TEST/SYNTHETIC {suffix} Asset ({TAG_CAUSE}-{RUN_ID})",
        "status": "TEST",
    })
    assert r.status_code in (200, 201), f"asset create failed: {r.text}"
    row = r.json()
    assets_created.append(row["id"])
    return row


def create_tms_chain(asset, defect_code, severity, detected_date, start, end):
    insp = client.post("/api/tms/inspections", json={
        "asset_id": asset["id"],
        "inspection_date": detected_date,
        "inspection_type": "USFD",
        "parameter_code": "TUBE-DEFLECTION",
        "parameter_value": "4.5",
        "remarks": f"{TAG_CAUSE}-{RUN_ID} TMS inspection.",
    })
    assert insp.status_code == 201, insp.text
    insp = insp.json()
    defect = client.post("/api/tms/defects", json={
        "asset_id": asset["id"],
        "inspection_id": insp["id"],
        "defect_code": defect_code,
        "defect_description": f"{TAG_CAUSE} TMS defect {defect_code}.",
        "severity": severity,
        "detected_date": detected_date,
        "status": "OPEN",
        "remarks": f"{TAG_CAUSE} TMS defect remarks.",
    })
    assert defect.status_code == 201, defect.text
    defect = defect.json()
    maint = client.post("/api/tms/maintenance", json={
        "asset_id": asset["id"],
        "defect_id": defect["id"],
        "maintenance_type": "REPLACEMENT",
        "planned_date": detected_date,
        "start_date": start,
        "end_date": end,
        "status": "PLANNED",
        "remarks": f"{TAG_CAUSE} TMS maintenance record.",
    })
    assert maint.status_code == 201, maint.text
    return defect, maint.json()


def add_block_requirement(mr_id, latest_end, power, traffic):
    r = client.post("/api/unified/block-requirements", json={
        "maintenance_requirement_id": mr_id,
        "station_code": "STA-7",
        "line_number": "L7",
        "block_type": "INTEGRATED_BLOCK",
        "required_duration_minutes": 120,
        "earliest_start": "2026-05-11T00:00:00",
        "latest_end": latest_end,
        "power_block_required": power,
        "traffic_block_required": traffic,
        "resource_notes": f"{TAG_CAUSE}-{RUN_ID} resource note.",
        "status": "REQUIRED",
        "remarks": f"{TAG_CAUSE}-{RUN_ID} block requirement.",
    })
    assert r.status_code == 201, r.text
    return r.json()


def main():
    global client

    log("LIVE SERVER")
    start_server()
    print(f"uvicorn live on {BASE_URL}")
    client = httpx.Client(base_url=BASE_URL, timeout=10)

    NOW = datetime.now(timezone.utc).replace(tzinfo=None)
    DETECT_DATE = "2026-05-11T09:00:00"
    YESTERDAY = (NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

    try:
        log("DATABASE / ALEMBIC BASELINE")
        print("current_database:", q("SELECT current_database()")[0][0])
        heads = [list(r) for r in q("SELECT version_num FROM alembic_version")]
        print("alembic_version:", heads)
        assert heads and heads[0][0] == "e1a9c2f3b7d5", heads
        print("source_systems:", [r[0] for r in q(
            "SELECT system_code FROM source_system ORDER BY id")])
        print("planning_priority baseline:",
              q("SELECT count(*) FROM planning_priority")[0][0])
        assert q("SELECT count(*) FROM planning_priority")[0][0] == 0

        log("STRUCTURAL VERIFICATION (planning_priority table)")
        insp = inspect(ENG)
        assert "planning_priority" in insp.get_table_names()
        pk = insp.get_pk_constraint("planning_priority")
        assert pk["constrained_columns"] == ["id"], pk
        cols = {c["name"] for c in insp.get_columns("planning_priority")}
        for column in cols:
            for token in ("confidence", "prediction", "recommended", "optimal",
                          "embedding", "feature_vector", "probability",
                          "risk", "rank"):
                assert token not in column, f"planning_priority.{column} contains {token}"
        fks = insp.get_foreign_keys("planning_priority")
        assert "planning_task" in [fk["referred_table"] for fk in fks], fks
        for fk in fks:
            assert fk["options"].get("ondelete") == "RESTRICT", (fk, fk["options"])
        uniq = {tuple(u["column_names"])
                for u in insp.get_unique_constraints("planning_priority")}
        print("  unique constraints:", uniq)
        assert ("planning_task_id",) in uniq
        checks = [c["sqltext"]
                  for c in insp.get_check_constraints("planning_priority")]
        print("  check constraints:", checks)
        assert any("priority_score" in c for c in checks)
        assert any("defect_age_days" in c for c in checks)
        idx = {tuple(i["column_names"])
               for i in insp.get_indexes("planning_priority")}
        print("  indexes:", idx)
        for required in (("planning_task_id",), ("priority_score",),
                         ("priority_band",), ("criticality_level",)):
            assert required in idx, required
        print("  planning_priority structure: OK")

        log("FORBIDDEN AI COLUMNS ACROSS SOURCE + PLANNING LAYER")
        count_checked = 0
        for table in INTEGRITY_TABLES:
            if table not in insp.get_table_names():
                continue
            columns = {c["name"] for c in insp.get_columns(table)}
            for column in columns:
                for token in FORBIDDEN_TOKENS:
                    assert token not in column, f"{table}.{column} contains {token}"
            count_checked += len(columns)
        for table in ("planning_priority",):
            columns = {c["name"] for c in insp.get_columns(table)}
            for column in columns:
                for token in ("confidence", "prediction", "recommended", "optimal",
                              "embedding", "feature_vector", "probability",
                              "risk", "rank"):
                    assert token not in column, f"{table}.{column} contains {token}"
            count_checked += len(columns)
        allowed = {"priority_score", "priority_band"}
        cols = {c["name"] for c in insp.get_columns("planning_priority")}
        assert cols >= allowed, cols
        print(f"  checked {count_checked} columns; only documented "
              f"{sorted(allowed)} carry advisory semantics in planning_priority")

        log("SYNTHETIC TMS CHAINS (two distinct priority scenarios)")
        tms = get_source_system("TMS")
        asset_a = create_asset(tms["id"], "HIGH")
        asset_b = create_asset(tms["id"], "LOW")
        _, maint_a = create_tms_chain(asset_a, "TMS-DF-001", "CRITICAL",
                                     DETECT_DATE, "2026-05-11T08:00:00",
                                     "2026-05-11T10:30:00")
        _, maint_b = create_tms_chain(asset_b, "TMS-DF-002", "LOW",
                                     DETECT_DATE, "2026-05-11T08:00:00",
                                     "2026-05-11T10:30:00")
        client.post("/api/unified/normalize/tms")
        requirements = client.get("/api/unified/maintenance").json()
        mr_a = [m for m in requirements
                if m["source_record_type"] == "TMS_MAINTENANCE"
                and m["source_record_id"] == maint_a["id"]][0]
        mr_b = [m for m in requirements
                if m["source_record_type"] == "TMS_MAINTENANCE"
                and m["source_record_id"] == maint_b["id"]][0]
        add_block_requirement(mr_a["id"], latest_end=YESTERDAY,
                              power=True, traffic=True)
        client.post("/api/planning/generate-tasks")
        tasks = client.get("/api/planning/tasks").json()
        task_a = [t for t in tasks if t["maintenance_requirement_id"] == mr_a["id"]][0]
        task_b = [t for t in tasks if t["maintenance_requirement_id"] == mr_b["id"]][0]
        my_task_ids.extend([task_a["id"], task_b["id"]])
        print("  task A:", task_a["id"], "block_requirement_id:",
              task_a["block_requirement_id"])
        print("  task B:", task_b["id"], "block_requirement_id:",
              task_b["block_requirement_id"])
        assert task_a["block_requirement_id"] is not None
        assert task_b["block_requirement_id"] is None

        log("STEP 12 WRITES DO NOT MODIFY SOURCE / UNIFIED / PLANNING LAYER")
        before = counts()
        print("  snapshot", len(before), "tables captured")

        log("PRIORITY NOT YET CALCULATED -> 404")
        assert client.get(
            f"/api/planning/tasks/{task_a['id']}/priority").status_code == 404
        assert client.get(
            f"/api/planning/tasks/{task_b['id']}/priority").status_code == 404
        print("  task priority before recalc -> 404: OK")

        log("DETERMINISTIC RECALCULATION (single task)")
        ra = client.post(f"/api/planning/tasks/{task_a['id']}/priority/recalculate")
        assert ra.status_code == 200, ra.text
        a = ra.json()
        print("  task A:", {k: a[k] for k in (
            "priority_score", "priority_band", "criticality_level", "urgency_level",
            "safety_impact", "asset_availability_impact", "traffic_impact",
            "failure_recurrence", "defect_age_days", "calculation_version")})
        assert a["calculation_version"] == "STEP12-DETERMINISTIC-1.0"
        assert a["criticality_level"] == "CRITICAL"
        assert a["urgency_level"] == "IMMEDIATE"
        assert a["safety_impact"] == "CRITICAL"
        assert a["asset_availability_impact"] == "HIGH"
        assert a["traffic_impact"] == "HIGH"
        assert a["failure_recurrence"] == "LOW"
        assert 0 <= a["priority_score"] <= 100
        assert a["priority_band"] == "CRITICAL"
        assert a["calculation_reason"]
        assert f"criticality={a['criticality_level']}" in a["calculation_reason"]
        assert f"defect_age_days={a['defect_age_days']}" in a["calculation_reason"]
        rb = client.post(f"/api/planning/tasks/{task_b['id']}/priority/recalculate")
        assert rb.status_code == 200, rb.text
        b = rb.json()
        print("  task B:", {k: b[k] for k in (
            "priority_score", "priority_band", "criticality_level", "urgency_level",
            "safety_impact", "asset_availability_impact", "traffic_impact",
            "failure_recurrence", "defect_age_days")})
        assert b["criticality_level"] == "LOW"
        assert b["urgency_level"] == "LOW"
        assert b["safety_impact"] == "LOW"
        assert b["asset_availability_impact"] == "LOW"
        assert b["traffic_impact"] == "NONE"
        assert b["priority_band"] == "LOW"
        assert a["priority_score"] > b["priority_score"], (a, b)
        print("  A (CRITICAL/urgent/power+traffic) strictly outranks B (LOW): OK")

        log("IDEMPOTENCY (single task recalc twice keeps one row)")
        ra2 = client.post(f"/api/planning/tasks/{task_a['id']}/priority/recalculate")
        assert ra2.status_code == 200
        assert ra2.json()["id"] == a["id"]
        assert ra2.json()["priority_score"] == a["priority_score"]
        rows_a = q(
            "SELECT count(*) FROM planning_priority WHERE planning_task_id = :tid",
            {"tid": task_a["id"]})
        print("  rows for task A after 2 recalc calls:", rows_a[0][0])
        assert rows_a[0][0] == 1
        print("  single-task recalculation idempotent: OK")

        log("GLOBAL RECALCULATION (idempotent across all planning tasks)")
        total_tasks = q("SELECT count(*) FROM planning_task")[0][0]
        owned = q(
            "SELECT count(*) FROM planning_priority WHERE planning_task_id = ANY(:ids)",
            {"ids": my_task_ids})[0][0]
        g1 = client.post("/api/planning/priority/recalculate")
        assert g1.status_code == 200, g1.text
        g1 = g1.json()
        print("  first global recalc:", g1)
        assert g1["processed"] == total_tasks, g1
        assert g1["updated"] == owned, g1
        assert g1["created"] == total_tasks - owned, g1
        assert q("SELECT count(*) FROM planning_priority")[0][0] == total_tasks
        g2 = client.post("/api/planning/priority/recalculate")
        assert g2.status_code == 200
        g2 = g2.json()
        print("  second global recalc:", g2)
        assert g2["processed"] == total_tasks and g2["created"] == 0
        assert g2["updated"] == total_tasks

        log("DETERMINISM (recalc does not change previously computed rows)")
        a_post = client.get(f"/api/planning/priority/{a['id']}").json()
        assert a_post["priority_score"] == a["priority_score"]
        assert a_post["priority_band"] == a["priority_band"]
        assert a_post["calculation_reason"] == a["calculation_reason"]
        print("  identical score/band/reason after global re-run: OK")

        log("FILTERS (scoped to synthetic rows via asset_id)")
        assert len(client.get(
            f"/api/planning/priority?asset_id={asset_a['id']}"
        ).json()) == 1
        assert len(client.get(
            f"/api/planning/priority?asset_id={asset_b['id']}"
        ).json()) == 1
        assert len(client.get(
            f"/api/planning/priority?priority_band=CRITICAL&asset_id={asset_a['id']}"
        ).json()) == 1
        assert len(client.get(
            f"/api/planning/priority?priority_band=LOW&asset_id={asset_b['id']}"
        ).json()) == 1
        assert len(client.get(
            f"/api/planning/priority?priority_band=BOGUS&asset_id={asset_a['id']}"
        ).json()) == 0
        assert len(client.get(
            f"/api/planning/priority?criticality_level=CRITICAL&asset_id={asset_a['id']}"
        ).json()) == 1
        assert len(client.get(
            f"/api/planning/priority?urgency_level=IMMEDIATE&asset_id={asset_a['id']}"
        ).json()) == 1
        assert len(client.get(
            f"/api/planning/priority?min_score={a['priority_score']}"
            f"&max_score={a['priority_score']}&asset_id={asset_a['id']}"
        ).json()) == 1
        assert len(client.get(
            f"/api/planning/priority?min_score={a['priority_score'] + 0.01}"
            f"&asset_id={asset_a['id']}"
        ).json()) == 0
        assert client.get(
            "/api/planning/priority?min_score=abc").status_code == 422
        assert client.get(
            "/api/planning/priority/999999").status_code == 404
        assert client.get(
            "/api/planning/tasks/999999/priority").status_code == 404
        assert client.post(
            "/api/planning/tasks/999999/priority/recalculate").status_code == 404
        assert client.get("/api/planning/priority/abc").status_code == 422
        print("  filters + 404/422 semantics: OK")

        log("PROVENANCE (planning_priority back to TMS source record)")
        rows = q("""
            SELECT pp.id AS priority_id, pp.priority_score, pp.priority_band,
                   pt.id AS task_id, pt.task_code,
                   mr.id AS mr_id, df.source_record_type, df.source_record_id,
                   df.severity
            FROM planning_priority pp
            JOIN planning_task pt ON pt.id = pp.planning_task_id
            JOIN maintenance_requirement mr ON mr.id = pt.maintenance_requirement_id
            JOIN defect_failure df ON df.id = mr.defect_failure_id
            WHERE pt.asset_id = ANY(:ids) ORDER BY pp.id
        """, {"ids": assets_created})
        for r in rows:
            print("  ", dict(zip(r._mapping.keys(), r)))
        assert len(rows) == 2
        assert {r._mapping["severity"] for r in rows} == {"CRITICAL", "LOW"}
        probe = [r for r in rows if r._mapping["severity"] == "CRITICAL"][0]
        source_row = q(
            "SELECT id, defect_code, severity FROM tms_defect WHERE id = :sid",
            {"sid": probe._mapping["source_record_id"]})
        print("  ", "tms_defect",
              dict(zip(source_row[0]._mapping.keys(), source_row[0])))
        assert source_row and source_row[0]._mapping["severity"] == "CRITICAL"

        log("SOURCE / UNIFIED / PLANNING LAYER UNCHANGED BY STEP 12 WRITES")
        after = counts()
        changed = {t: (before[t], after[t]) for t in before if before[t] != after[t]}
        print("  changed tables:", changed if changed else "none")
        assert changed == {}
        total_now = q("SELECT count(*) FROM planning_priority")[0][0]
        print("  planning_priority rows after verification:", total_now)
        assert total_now == total_tasks
        print("ALL CHECKS PASSED")
    finally:
        with SessionLocal() as db:
            log("CLEANUP (FK-safe order)")
            print("  deleting planning_priority rows (all, created by this run)...")
            db.execute(text("DELETE FROM planning_priority"))
            print("  deleting task_dependency rows...")
            db.execute(text(
                "DELETE FROM task_dependency WHERE predecessor_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": assets_created})
            db.execute(text(
                "DELETE FROM task_dependency WHERE successor_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": assets_created})
            print("  deleting task_resource rows...")
            db.execute(text(
                "DELETE FROM task_resource WHERE planning_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": assets_created})
            print("  deleting planning_constraint rows...")
            db.execute(text(
                "DELETE FROM planning_constraint WHERE planning_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": assets_created})
            print("  deleting planning_task rows...")
            db.execute(text(
                "DELETE FROM planning_task WHERE asset_id = ANY(:ids)"), {"ids": assets_created})
            print("  deleting planning_resource rows...")
            db.execute(text("DELETE FROM planning_resource WHERE resource_code LIKE :tag"),
                       {"tag": f"{TAG}-%"})
            print("  deleting block_requirement rows...")
            db.execute(text(
                "DELETE FROM block_requirement WHERE maintenance_requirement_id IN "
                "(SELECT id FROM maintenance_requirement WHERE asset_id = ANY(:ids))"
            ), {"ids": assets_created})
            print("  deleting maintenance_requirement rows...")
            db.execute(text(
                "DELETE FROM maintenance_requirement WHERE asset_id = ANY(:ids)"), {"ids": assets_created})
            print("  deleting defect_failure rows...")
            db.execute(text(
                "DELETE FROM defect_failure WHERE asset_id = ANY(:ids)"), {"ids": assets_created})
            print("  deleting TMS source rows...")
            for t in ("tms_maintenance", "tms_defect", "tms_inspection"):
                db.execute(text(f"DELETE FROM {t} WHERE asset_id = ANY(:ids)"), {"ids": assets_created})
            print("  deleting synthetic assets...")
            db.execute(text("DELETE FROM asset_master WHERE id = ANY(:ids)"), {"ids": assets_created})
            assets_created.clear()
            db.commit()

            log("FINAL DATABASE STATE (synthetic rows removed, pre-existing data kept)")
            leftover = db.execute(text(
                "SELECT count(*) FROM planning_priority")).scalar()
            print("  planning_priority:", leftover)
            assert leftover == 0
            seeds = [r[0] for r in db.execute(
                text("SELECT system_code FROM source_system ORDER BY id")).all()]
            print("  source systems preserved:", seeds)
            assert "TMS" in seeds and "TDMS" in seeds and "SMMS" in seeds and "COA" in seeds
            print("\nCLEANUP VERIFIED")


if __name__ == "__main__":
    try:
        main()
    finally:
        if client is not None:
            client.close()
        stop_server()