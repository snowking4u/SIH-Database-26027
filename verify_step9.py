"""STEP 9 live verification: deterministic candidate-window feasibility layer.

Runs a real uvicorn server against the live PostgreSQL database, creates
synthetic TMS/TDMS source chains, COA-derived available windows, planning
tasks and block requirements, then exercises the /api/candidates endpoints
(generate, list, get-by-id, check), verifying deterministic feasibility
reasons, idempotency, provenance, available-window preservation, no
forbidden columns, structural integrity, then cleans up all synthetic data.

The seeded source systems (TMS, TDMS, SMMS, COA) are reused and never deleted.
No AI/ML/optimization/ranking/scoring is involved.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, inspect, text

from app.core.database import SessionLocal

PROJECT_ROOT = Path(__file__).resolve().parent
ENG = create_engine("postgresql+psycopg2://postgres:root@localhost:5432/sih_26027")
PORT = 8011
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{PORT}"

TAG = "VERIFY9"
TAG_CAUSE = "STEP9-SYNTHETIC"

FORBIDDEN_SUBSTRINGS = [
    "score", "confidence", "prediction", "recommended", "optimal",
    "optimization", "ai_", "ml_", "rank",
]

PLANNING_TABLES = [
    "planning_task", "planning_constraint", "planning_resource",
    "task_resource", "task_dependency",
]

server = None
client = None
assets_created = []
trains_created = []


def log(title):
    print(f"\n=== {title} ===")


def q(sql, params=None):
    with ENG.connect() as c:
        return c.execute(text(sql), params or {}).fetchall()


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
        "source_asset_id": f"{TAG}-{suffix}-ASSET-1",
        "asset_type": "TEST/SYNTHETIC",
        "asset_name": f"TEST/SYNTHETIC {suffix} Asset ({TAG_CAUSE})",
        "status": "TEST",
    })
    assert r.status_code in (200, 201), f"asset create failed: {r.text}"
    row = r.json()
    assets_created.append(row["id"])
    return row


def create_tms_chain(asset):
    insp = client.post("/api/tms/inspections", json={
        "asset_id": asset["id"],
        "inspection_date": "2026-05-01T10:00:00",
        "inspection_type": "USFD",
        "parameter_code": "TUBE-DEFLECTION",
        "parameter_value": "4.5",
        "remarks": f"{TAG_CAUSE} TMS inspection.",
    })
    assert insp.status_code == 201, insp.text
    insp = insp.json()
    defect = client.post("/api/tms/defects", json={
        "asset_id": asset["id"],
        "inspection_id": insp["id"],
        "defect_code": "TMS-DF-001",
        "defect_description": f"{TAG_CAUSE} TMS defect observed.",
        "severity": "HIGH",
        "detected_date": "2026-05-01T10:30:00",
        "status": "OPEN",
        "remarks": f"{TAG_CAUSE} TMS defect remarks.",
    })
    assert defect.status_code == 201, defect.text
    defect = defect.json()
    maint = client.post("/api/tms/maintenance", json={
        "asset_id": asset["id"],
        "defect_id": defect["id"],
        "maintenance_type": "REPLACEMENT",
        "planned_date": "2026-05-11T09:00:00",
        "start_date": "2026-05-11T09:00:00",
        "end_date": "2026-05-11T11:30:00",
        "status": "PLANNED",
        "remarks": f"{TAG_CAUSE} TMS maintenance record.",
    })
    assert maint.status_code == 201, maint.text
    return insp, defect, maint.json()


def create_tdms_chain(asset):
    insp = client.post("/api/tdms/inspections", json={
        "asset_id": asset["id"],
        "inspection_date": "2026-05-02T10:00:00",
        "inspection_type": "SONIC",
        "parameter_code": "RAIL-DEFECT",
        "parameter_value": "ANOMALY",
        "remarks": f"{TAG_CAUSE} TDMS inspection.",
    })
    assert insp.status_code == 201, insp.text
    insp = insp.json()
    failure = client.post("/api/tdms/failures", json={
        "asset_id": asset["id"],
        "inspection_id": insp["id"],
        "failure_code": "TDMS-F-001",
        "failure_description": f"{TAG_CAUSE} TDMS failure detected.",
        "severity": "MEDIUM",
        "failure_date": "2026-05-02T10:40:00",
        "status": "OPEN",
        "rectification_date": None,
        "remarks": f"{TAG_CAUSE} TDMS failure remarks.",
    })
    assert failure.status_code == 201, failure.text
    failure = failure.json()
    maint = client.post("/api/tdms/maintenance", json={
        "asset_id": asset["id"],
        "failure_id": failure["id"],
        "maintenance_type": "REPAIR",
        "planned_date": "2026-05-11T09:00:00",
        "start_date": "2026-05-11T09:00:00",
        "end_date": "2026-05-11T12:00:00",
        "status": "PLANNED",
        "remarks": f"{TAG_CAUSE} TDMS maintenance record.",
    })
    assert maint.status_code == 201, maint.text
    return insp, failure, maint.json()


def create_occupancy(train, station, line, start, end, suffix):
    r = client.post("/api/coa/line-occupancy", json={
        "station_code": station,
        "line_number": line,
        "occupancy_start": f"2026-05-11T{start}:00",
        "occupancy_end": f"2026-05-11T{end}:00",
        "occupancy_status": "OCCUPIED",
        "train_id": train["id"],
        "source_event_id": f"{TAG}-OCC-{suffix}",
    })
    assert r.status_code == 201, r.text
    return r.json()


def candidate_reason(task_id, window_id):
    return q(
        "SELECT feasibility_status, feasibility_reason, feasible, "
        "candidate_duration_minutes, candidate_start, candidate_end "
        "FROM candidate_block_window "
        "WHERE planning_task_id = :t AND available_window_id = :w",
        {"t": task_id, "w": window_id},
    )[0]


def main():
    global client

    log("LIVE SERVER")
    start_server()
    print(f"uvicorn live on {BASE_URL}")
    client = httpx.Client(base_url=BASE_URL, timeout=10)

    try:
        log("DATABASE / ALEMBIC BASELINE")
        print("current_database:", q("SELECT current_database()")[0][0])
        heads = [list(r) for r in q("SELECT version_num FROM alembic_version")]
        print("alembic_version:", heads)
        assert heads and heads[0][0] == "b7a4c2e8d1f6", heads
        print("source_systems:", [r[0] for r in q(
            "SELECT system_code FROM source_system ORDER BY id")])

        log("BASELINE COUNTS (pre-seeding)")
        tables = [
            "tms_inspection", "tms_defect", "tms_maintenance",
            "tdms_inspection", "tdms_failure", "tdms_maintenance",
            "defect_failure", "maintenance_requirement", "block_requirement",
            "available_window", "candidate_block_window",
        ] + PLANNING_TABLES
        for t in tables:
            print(f"  {t}: {q(f'SELECT count(*) FROM {t}')[0][0]}")

        log("COA AVAILABLE WINDOWS (deterministic gaps per station/line)")
        coa = get_source_system("COA")
        train = client.post("/api/coa/trains", json={
            "train_id": f"{TAG}-COA-TRAIN-1",
            "train_number": "7999",
            "train_name": f"TEST/SYNTHETIC COA Train ({TAG_CAUSE})",
            "direction": "UP",
            "source_system_id": coa["id"],
        })
        assert train.status_code == 201, train.text
        train = train.json()
        trains_created.append(train["id"])

        # STA-7/L7 gaps -> 10:00-14:00 (240m) and 15:00-16:00 (60m)
        create_occupancy(train, "STA-7", "L7", "00:00", "10:00", "A1")
        create_occupancy(train, "STA-7", "L7", "14:00", "15:00", "A2")
        create_occupancy(train, "STA-7", "L7", "16:00", "20:00", "A3")
        # STA-8/L7 gap -> 10:00-14:00 (location mismatch)
        create_occupancy(train, "STA-8", "L7", "00:00", "10:00", "B1")
        create_occupancy(train, "STA-8", "L7", "14:00", "20:00", "B2")
        # STA-7/L8 gap -> 10:00-14:00 (line mismatch)
        create_occupancy(train, "STA-7", "L8", "00:00", "10:00", "C1")
        create_occupancy(train, "STA-7", "L8", "14:00", "20:00", "C2")

        gen = client.post("/api/coa/available-windows/generate")
        assert gen.status_code == 200, gen.text
        windows = client.get("/api/coa/available-windows").json()
        for w in windows:
            print("  ", {k: w[k] for k in (
                "id", "station_code", "line_number", "window_start",
                "window_end", "duration_minutes")})
        assert len(windows) == 4, windows
        by_key = {}
        for w in windows:
            by_key.setdefault((w["station_code"], w["line_number"]), []).append(w)
        assert len(by_key[("STA-7", "L7")]) == 2
        w_sta7 = max(by_key[("STA-7", "L7")], key=lambda w: w["duration_minutes"])
        w_short = min(by_key[("STA-7", "L7")], key=lambda w: w["duration_minutes"])
        w_loc = by_key[("STA-8", "L7")][0]
        w_line = by_key[("STA-7", "L8")][0]
        assert w_sta7["duration_minutes"] == 240
        assert w_short["duration_minutes"] == 60

        log("SYNTHETIC SOURCE CHAINS (TMS + TDMS)")
        tms = get_source_system("TMS")
        tdms = get_source_system("TDMS")
        assets = {
            "TMS": create_asset(tms["id"], "TMS"),
            "TDMS": create_asset(tdms["id"], "TDMS"),
        }
        _, tms_defect, _ = create_tms_chain(assets["TMS"])
        _, tdms_failure, _ = create_tdms_chain(assets["TDMS"])

        log("NORMALIZATION + BLOCK REQUIREMENTS")
        client.post("/api/unified/normalize/tms")
        client.post("/api/unified/normalize/tdms")
        requirements = client.get("/api/unified/maintenance").json()
        mr_tms = [m for m in requirements if m["source_record_type"] == "TMS_MAINTENANCE"][0]
        mr_tdms = [m for m in requirements if m["source_record_type"] == "TDMS_MAINTENANCE"][0]

        br_tms = client.post("/api/unified/block-requirements", json={
            "maintenance_requirement_id": mr_tms["id"],
            "station_code": "STA-7",
            "line_number": "L7",
            "block_type": "INTEGRATED_BLOCK",
            "required_duration_minutes": 120,
            "power_block_required": False,
            "traffic_block_required": False,
            "resource_notes": f"{TAG_CAUSE} TMS resource note.",
            "status": "REQUIRED",
            "remarks": f"{TAG_CAUSE} TMS block requirement.",
        })
        assert br_tms.status_code == 201, br_tms.text
        br_tms = br_tms.json()

        br_tdms = client.post("/api/unified/block-requirements", json={
            "maintenance_requirement_id": mr_tdms["id"],
            "station_code": "STA-7",
            "line_number": "L7",
            "block_type": "INTEGRATED_BLOCK",
            "required_duration_minutes": 120,
            "power_block_required": True,
            "traffic_block_required": True,
            "resource_notes": f"{TAG_CAUSE} TDMS resource note.",
            "status": "REQUIRED",
            "remarks": f"{TAG_CAUSE} TDMS block requirement.",
        })
        assert br_tdms.status_code == 201, br_tdms.text
        br_tdms = br_tdms.json()

        log("PLANNING TASK GENERATION")
        s1 = client.post("/api/planning/generate-tasks").json()
        print("summary:", s1)
        assert s1["created"] == 2
        tasks = client.get("/api/planning/tasks").json()
        task_tms = [t for t in tasks if t["maintenance_requirement_id"] == mr_tms["id"]][0]
        task_tdms = [t for t in tasks if t["maintenance_requirement_id"] == mr_tdms["id"]][0]
        assert task_tms["duration_minutes"] == 150
        assert task_tdms["duration_minutes"] == 180

        log("CANDIDATE CHECK (no persistence, deterministic evaluation)")
        pre = q("SELECT count(*) FROM candidate_block_window")[0][0]
        chk = client.post("/api/candidates/check", json={
            "planning_task_id": task_tms["id"],
            "available_window_id": w_sta7["id"],
        })
        assert chk.status_code == 200, chk.text
        chk = chk.json()
        print("check:", chk)
        assert chk["feasible"] is True
        assert chk["feasibility_status"] == "FEASIBLE"
        assert chk["feasibility_reason"] == "FEASIBLE_TEMPORAL_MATCH"
        assert chk["existing_candidate_id"] is None
        assert q("SELECT count(*) FROM candidate_block_window")[0][0] == pre

        log("CANDIDATE GENERATION (run 1)")
        g1 = client.post("/api/candidates/generate").json()
        print("summary:", g1)
        assert g1["processed"] == 8, g1
        assert g1["created"] == 8, g1
        assert g1["skipped"] == 0
        assert g1["infeasible"] == 6, g1
        assert g1["requires_review"] == 1, g1

        log("DETERMINISTIC REASONS PER (task, window)")
        print("  TMS feat :", candidate_reason(task_tms["id"], w_sta7["id"]))
        print("  TMS short:", candidate_reason(task_tms["id"], w_short["id"]))
        print("  TMS loc  :", candidate_reason(task_tms["id"], w_loc["id"]))
        print("  TMS line :", candidate_reason(task_tms["id"], w_line["id"]))
        print("  TDMS feat:", candidate_reason(task_tdms["id"], w_sta7["id"]))
        assert tuple(candidate_reason(task_tms["id"], w_sta7["id"])[:3]) == (
            "FEASIBLE", "FEASIBLE_TEMPORAL_MATCH", True)
        assert candidate_reason(task_tms["id"], w_sta7["id"])[3] == 150
        assert tuple(candidate_reason(task_tms["id"], w_short["id"])[:2]) == (
            "INFEASIBLE", "DURATION_EXCEEDS_WINDOW")
        assert tuple(candidate_reason(task_tms["id"], w_loc["id"])[:2]) == (
            "INFEASIBLE", "LOCATION_MISMATCH")
        assert tuple(candidate_reason(task_tms["id"], w_line["id"])[:2]) == (
            "INFEASIBLE", "LINE_MISMATCH")
        assert tuple(candidate_reason(task_tdms["id"], w_sta7["id"])[:2]) == (
            "REQUIRES_REVIEW", "POWER_BLOCK_CONFIRMATION_REQUIRED")

        log("CANDIDATE LIST / FILTERS / GET-BY-ID")
        all_rows = client.get("/api/candidates/windows").json()
        assert len(all_rows) == 8
        assert len(client.get(f"/api/candidates/windows?planning_task_id={task_tms['id']}").json()) == 4
        assert len(client.get(f"/api/candidates/windows?available_window_id={w_sta7['id']}").json()) == 2
        assert len(client.get("/api/candidates/windows?feasible=true").json()) == 1
        assert len(client.get("/api/candidates/windows?feasible=false").json()) == 7
        assert len(client.get("/api/candidates/windows?feasibility_status=REQUIRES_REVIEW").json()) == 1
        first = all_rows[0]
        got = client.get(f"/api/candidates/windows/{first['id']}")
        assert got.status_code == 200 and got.json()["id"] == first["id"]
        missing = client.get("/api/candidates/windows/999999")
        assert missing.status_code == 404

        log("CANDIDATE CHECK (existing persisted candidate returned)")
        chk2 = client.post("/api/candidates/check", json={
            "planning_task_id": task_tms["id"],
            "available_window_id": w_sta7["id"],
        }).json()
        assert chk2["existing_candidate_id"] is not None

        log("INVALID FK / VALIDATION HTTP CHECKS")
        bad_task = client.post("/api/candidates/check", json={
            "planning_task_id": 999999, "available_window_id": w_sta7["id"]})
        assert bad_task.status_code == 404, bad_task.text
        bad_window = client.post("/api/candidates/check", json={
            "planning_task_id": task_tms["id"], "available_window_id": 999999})
        assert bad_window.status_code == 404, bad_window.text
        print("  404 invalid task/window FK: OK")

        log("CANDIDATE GENERATION (run 2 -> idempotent)")
        g2 = client.post("/api/candidates/generate").json()
        print("summary:", g2)
        assert g2["created"] == 0, g2
        assert g2["skipped"] == g1["processed"], g2
        total = q("SELECT count(*) FROM candidate_block_window")[0][0]
        distinct = q(
            "SELECT count(*) FROM (SELECT DISTINCT planning_task_id, available_window_id "
            "FROM candidate_block_window) s")[0][0]
        assert total == 8 and distinct == total, (total, distinct)

        log("FULL PROVENANCE JOIN")
        rows = q("""
            SELECT cbw.id AS cbw_id, cbw.feasible, cbw.feasibility_status,
                   cbw.feasibility_reason, cbw.candidate_duration_minutes,
                   pt.id AS pt_id, mr.id AS mr_id, mr.source_record_type,
                   df.id AS df_id, ss.system_code,
                   br.id AS br_id, br.station_code, br.line_number,
                   aw.id AS aw_id, aw.station_code AS aw_station,
                   aw.line_number AS aw_line
            FROM candidate_block_window cbw
            JOIN planning_task pt ON pt.id = cbw.planning_task_id
            JOIN maintenance_requirement mr ON mr.id = pt.maintenance_requirement_id
            JOIN defect_failure df ON df.id = mr.defect_failure_id
            JOIN source_system ss ON ss.id = df.source_system_id
            JOIN block_requirement br ON br.id = cbw.block_requirement_id
            JOIN available_window aw ON aw.id = cbw.available_window_id
            ORDER BY cbw.id
        """)
        for r in rows:
            print("  ", dict(zip(r._mapping.keys(), [str(x) if x is not None else None for x in r])))
        assert len(rows) == 8
        tms_rows = [r for r in rows if r._mapping["system_code"] == "TMS"]
        tdms_rows = [r for r in rows if r._mapping["system_code"] == "TDMS"]
        assert len(tms_rows) == 4 and len(tdms_rows) == 4
        assert all(r._mapping["mr_id"] == mr_tms["id"] for r in tms_rows)
        assert all(r._mapping["df_id"] for r in rows)
        assert all(r._mapping["aw_id"] for r in rows)
        assert tms_rows[0]._mapping["br_id"] == br_tms["id"]
        assert tdms_rows[0]._mapping["br_id"] == br_tdms["id"]

        src = q("SELECT defect_description, status FROM tms_defect WHERE id = :id",
                {"id": tms_defect["id"]})[0]
        assert src[0] == f"{TAG_CAUSE} TMS defect observed." and src[1] == "OPEN"
        src_f = q("SELECT failure_description, status FROM tdms_failure WHERE id = :id",
                  {"id": tdms_failure["id"]})[0]
        assert src_f[0] == f"{TAG_CAUSE} TDMS failure detected." and src_f[1] == "OPEN"

        log("SOURCE/UNIFIED RECORDS UNCHANGED AFTER GENERATION")
        for t in (
            "tms_inspection", "tms_defect", "tms_maintenance",
            "tdms_inspection", "tdms_failure", "tdms_maintenance",
            "defect_failure", "maintenance_requirement", "block_requirement",
        ):
            print(f"  {t}: {q(f'SELECT count(*) FROM {t}')[0][0]}")

        log("AVAILABLE WINDOW UNCHANGED AFTER CANDIDATE GENERATION")
        windows_after = client.get("/api/coa/available-windows").json()
        assert windows_after == windows, (windows, windows_after)
        print("  available window rows identical before/after candidate generation")

        log("AI / OPTIMIZATION SAFETY (forbidden columns absent)")
        insp = inspect(ENG)
        cols = {c["name"].lower() for c in insp.get_columns("candidate_block_window")}
        for column in cols:
            for bad in FORBIDDEN_SUBSTRINGS:
                assert bad not in column, f"candidate_block_window.{column} contains {bad}"
        print("  candidate_block_window:", sorted(cols))
        assert "score" not in cols and "rank" not in cols and "confidence" not in cols

        log("STRUCTURAL VERIFICATION (candidate_block_window)")
        pk = insp.get_pk_constraint("candidate_block_window")
        print("  PK:", pk)
        assert pk["constrained_columns"] == ["id"]
        print("  columns:", json.dumps([
            (c["name"], str(c["type"]), c["nullable"])
            for c in insp.get_columns("candidate_block_window")]))
        uniq = [(u["name"], tuple(u["column_names"]))
                for u in insp.get_unique_constraints("candidate_block_window")]
        print("  unique:", json.dumps(uniq))
        assert ("planning_task_id", "available_window_id") in [u[1] for u in uniq]
        index_names = [i["name"] for i in insp.get_indexes("candidate_block_window")]
        print("  indexes:", json.dumps([
            (i["name"], i["column_names"], i["unique"])
            for i in insp.get_indexes("candidate_block_window")]))
        for idx in ("ix_candidate_block_window_planning_task_id",
                    "ix_candidate_block_window_block_requirement_id",
                    "ix_candidate_block_window_available_window_id",
                    "ix_candidate_block_window_feasible",
                    "ix_candidate_block_window_feasibility_status"):
            assert idx in index_names, idx
        fks = insp.get_foreign_keys("candidate_block_window")
        for fk in fks:
            assert fk["options"].get("ondelete") == "RESTRICT", (fk, fk["options"])
        print("  FKs:", json.dumps([
            (fk["name"], fk["constrained_columns"], fk["referred_table"],
             fk["referred_columns"], fk["options"]) for fk in fks]))
        fk_map = {fk["constrained_columns"][0]: fk["referred_table"] for fk in fks}
        assert fk_map["planning_task_id"] == "planning_task"
        assert fk_map["block_requirement_id"] == "block_requirement"
        assert fk_map["available_window_id"] == "available_window"
        checks = {c["name"] for c in insp.get_check_constraints("candidate_block_window")}
        print("  checks:", checks)
        assert checks == {
            "ck_candidate_block_window_end_gt_start",
            "ck_candidate_block_window_duration_non_negative",
        }, checks

        print("\nALL CHECKS PASSED")
    finally:
        with SessionLocal() as db:
            log("CLEANUP (FK-safe order)")
            asset_ids = assets_created

            print("  deleting task_dependency rows...")
            db.execute(text(
                "DELETE FROM task_dependency WHERE predecessor_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": asset_ids})
            db.execute(text(
                "DELETE FROM task_dependency WHERE successor_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": asset_ids})
            print("  deleting task_resource rows...")
            db.execute(text(
                "DELETE FROM task_resource WHERE planning_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": asset_ids})
            print("  deleting planning_constraint rows...")
            db.execute(text(
                "DELETE FROM planning_constraint WHERE planning_task_id IN "
                "(SELECT id FROM planning_task WHERE asset_id = ANY(:ids))"
            ), {"ids": asset_ids})
            print("  deleting candidate_block_window rows...")
            db.execute(text("DELETE FROM candidate_block_window"))
            print("  deleting planning_task rows...")
            db.execute(text("DELETE FROM planning_task WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            print("  deleting planning_resource rows...")
            db.execute(text("DELETE FROM planning_resource WHERE resource_code LIKE :tag"), {"tag": f"{TAG}-%"})
            print("  deleting block_requirement rows...")
            db.execute(text(
                "DELETE FROM block_requirement WHERE maintenance_requirement_id IN "
                "(SELECT id FROM maintenance_requirement WHERE asset_id = ANY(:ids))"
            ), {"ids": asset_ids})
            print("  deleting maintenance_requirement rows...")
            db.execute(text("DELETE FROM maintenance_requirement WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            print("  deleting defect_failure rows...")
            db.execute(text("DELETE FROM defect_failure WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})

            print("  deleting TMS source rows...")
            for t in ("tms_maintenance", "tms_defect", "tms_inspection"):
                db.execute(text(f"DELETE FROM {t} WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            print("  deleting TDMS source rows...")
            for t in ("tdms_maintenance", "tdms_failure", "tdms_inspection"):
                db.execute(text(f"DELETE FROM {t} WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})

            print("  deleting synthetic assets...")
            db.execute(text("DELETE FROM asset_master WHERE id = ANY(:ids)"), {"ids": asset_ids})
            assets_created.clear()

            print("  deleting synthetic COA data (windows/occupancy/train)...")
            db.execute(text("DELETE FROM available_window"))
            for t in ("line_occupancy", "train_movement", "train_schedule", "operational_event"):
                db.execute(text(f"DELETE FROM {t} WHERE train_id = ANY(:ids)"), {"ids": trains_created})
            db.execute(text("DELETE FROM train WHERE id = ANY(:ids)"), {"ids": trains_created})
            trains_created.clear()
            db.commit()

            log("FINAL DATABASE STATE (must be clean)")
            for t in tables + ["asset_master", "train"]:
                print(f"  {t}: {db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")
            for t in PLANNING_TABLES + ["candidate_block_window", "available_window",
                                        "defect_failure", "maintenance_requirement",
                                        "block_requirement", "asset_master", "train"]:
                remnants = db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                assert remnants == 0, f"{t} not clean ({remnants})"
            print("\nCLEANUP VERIFIED")


if __name__ == "__main__":
    try:
        main()
    finally:
        if client is not None:
            client.close()
        stop_server()
