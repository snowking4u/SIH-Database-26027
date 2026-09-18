"""STEP 7 live verification: Unified Maintenance / Defect / Block Requirement layer.

Runs a real uvicorn server against the live PostgreSQL database, creates
synthetic TMS/TDMS/SMMS source chains, normalizes them through the live HTTP
endpoints, verifies provenance / idempotency / block requirements / available
window preservation, then cleans up all synthetic data.

The seeded source systems (TMS, TDMS, SMMS, COA) are reused and never deleted.
"""

import subprocess
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, inspect, text

from app.core.database import Base, SessionLocal
from app.models.available_window import AvailableWindow

PROJECT_ROOT = Path(__file__).resolve().parent
ENG = create_engine("postgresql+psycopg2://postgres:root@localhost:5432/sih_26027")
PORT = 8011
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{PORT}"

TAG = "VERIFY7"
TAG_CAUSE = "STEP7-SYNTHETIC"

FORBIDDEN_COLUMNS = [
    "priority_score", "risk_score", "predicted_failure", "recommended_block",
    "optimization_score", "optimized_schedule", "ai_recommendation",
    "candidate_block_window", "optimization_run", "optimization_input",
    "optimization_output", "block_plan", "block_plan_task", "plan_validation",
    "controller_decision", "execution_outcome", "validation_result",
    "planning_task", "planning_constraint", "task_resource",
    "planning_resource", "task_dependency",
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
                r = c.get("/health")
                if r.status_code == 200:
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
    r = client.get("/api/source-systems")
    r.raise_for_status()
    for row in r.json():
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
        "planned_date": "2026-05-10T09:00:00",
        "start_date": "2026-05-10T09:00:00",
        "end_date": "2026-05-10T11:30:00",
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
        "planned_date": "2026-05-12T09:00:00",
        "start_date": "2026-05-12T09:00:00",
        "end_date": "2026-05-12T12:00:00",
        "status": "PLANNED",
        "remarks": f"{TAG_CAUSE} TDMS maintenance record.",
    })
    assert maint.status_code == 201, maint.text
    return insp, failure, maint.json()


def create_smms_chain(asset):
    insp = client.post("/api/smms/inspections", json={
        "asset_id": asset["id"],
        "inspection_date": "2026-05-03T10:00:00",
        "inspection_type": "Point Machine Inspection",
        "parameter_code": "POINT-STROKE",
        "parameter_value": "NORMAL",
        "remarks": f"{TAG_CAUSE} SMMS inspection.",
    })
    assert insp.status_code == 201, insp.text
    insp = insp.json()
    alert = client.post("/api/smms/alerts", json={
        "asset_id": asset["id"],
        "inspection_id": insp["id"],
        "alert_type_code": "SMMS-AL-001",
        "alert_feedback_code": "SMMS-FB-001",
        "alert_status_code": "OPEN",
        "cause_code": "SMMS-CAUSE-001",
        "incidence_date_time": "2026-05-03T10:50:00",
        "rectification_date_time": None,
        "incidence_duration": "PT1H",
        "remarks": f"{TAG_CAUSE} SMMS alert text.",
    })
    assert alert.status_code == 201, alert.text
    alert = alert.json()
    maint = client.post("/api/smms/maintenance", json={
        "asset_id": asset["id"],
        "alert_id": alert["id"],
        "maintenance_type": "Preventive Maintenance",
        "planned_date": "2026-05-14T09:00:00",
        "start_date": "2026-05-14T09:00:00",
        "end_date": "2026-05-14T10:00:00",
        "status": "PLANNED",
        "remarks": f"{TAG_CAUSE} SMMS maintenance record.",
    })
    assert maint.status_code == 201, maint.text
    return insp, alert, maint.json()


def main():
    global client

    log("LIVE SERVER")
    start_server()
    print(f"uvicorn live on {BASE_URL}")
    client = httpx.Client(base_url=BASE_URL, timeout=10)

    try:
        log("DATABASE / ALEMBIC BASELINE")
        print("current_database:", q("SELECT current_database()")[0][0])
        print("alembic_version:", [list(r) for r in q("SELECT version_num FROM alembic_version")])
        print("source_systems:", [r[0] for r in q("SELECT system_code FROM source_system ORDER BY id")])

        log("BASELINE COUNTS (pre-seeding)")
        tables = [
            "tms_inspection", "tms_defect", "tms_maintenance",
            "tdms_inspection", "tdms_failure", "tdms_maintenance",
            "smms_inspection", "smms_alert", "smms_maintenance",
            "defect_failure", "maintenance_requirement", "block_requirement",
            "available_window",
        ]
        for t in tables:
            print(f"  {t}: {q(f'SELECT count(*) FROM {t}')[0][0]}")

        log("COA AVAILABLE WINDOW (context, must stay unchanged)")
        coa = get_source_system("COA")
        train = client.post("/api/coa/trains", json={
            "train_id": f"{TAG}-COA-TRAIN-1",
            "train_number": "7997",
            "train_name": f"TEST/SYNTHETIC COA Train ({TAG_CAUSE})",
            "direction": "UP",
            "source_system_id": coa["id"],
        })
        assert train.status_code == 201, train.text
        train = train.json()
        trains_created.append(train["id"])
        for start, end in (
            ("2026-05-01T10:00:00", "2026-05-01T10:20:00"),
            ("2026-05-01T10:40:00", "2026-05-01T11:00:00"),
        ):
            occ = client.post("/api/coa/line-occupancy", json={
                "station_code": "STA-9",
                "line_number": "L9",
                "occupancy_start": start,
                "occupancy_end": end,
                "occupancy_status": "OCCUPIED",
                "train_id": train["id"],
                "source_event_id": f"{TAG}-SRC-OCC-{start}",
            })
            assert occ.status_code == 201, occ.text
        gen = client.post("/api/coa/available-windows/generate")
        assert gen.status_code == 200, gen.text
        windows_before = client.get("/api/coa/available-windows").json()
        print("available windows before normalization:", windows_before)

        log("SYNTHETIC SOURCE CHAINS")
        tms = get_source_system("TMS")
        tdms = get_source_system("TDMS")
        smms = get_source_system("SMMS")
        assets = {}
        assets["TMS"] = create_asset(tms["id"], "TMS")
        assets["TDMS"] = create_asset(tdms["id"], "TDMS")
        assets["SMMS"] = create_asset(smms["id"], "SMMS")

        _, tms_defect, tms_maint = create_tms_chain(assets["TMS"])
        _, tdms_failure, tdms_maint = create_tdms_chain(assets["TDMS"])
        _, smms_alert, smms_maint = create_smms_chain(assets["SMMS"])

        for a in assets.values():
            print(f"  asset#{a['id']} {a['source_asset_id']} (source_system_id={a['source_system_id']})")

        log("NORMALIZATION (run 1)")
        r1 = client.post("/api/unified/normalize/tms").json()
        r2 = client.post("/api/unified/normalize/tdms").json()
        r3 = client.post("/api/unified/normalize/smms").json()
        print("TMS :", r1)
        print("TDMS:", r2)
        print("SMMS:", r3)

        log("NORMALIZED COUNTS")
        for t in ("defect_failure", "maintenance_requirement"):
            print(f"  {t}: {q(f'SELECT count(*) FROM {t}')[0][0]}")

        log("HTTP FILTER CHECKS")
        defects = client.get("/api/unified/defects").json()
        requirements = client.get("/api/unified/maintenance").json()
        print("  defects:", len(defects), "| requirements:", len(requirements))

        df_asset_tms = [d for d in defects if d["asset_id"] == assets["TMS"]["id"]]
        assert len(df_asset_tms) == 1
        mr_by_asset = [m for m in requirements if m["asset_id"] == assets["TMS"]["id"]]
        assert len(mr_by_asset) == 1
        print("  filter asset_id OK")
        print("  filter source_system_id OK:",
              len(client.get(f"/api/unified/defects?source_system_id={tms['id']}").json()) == 1)
        print("  filter status=OPEN defects:",
              len(client.get("/api/unified/defects?status=OPEN").json()))
        print("  filter status=PLANNED maintenance:",
              len(client.get("/api/unified/maintenance?status=PLANNED").json()))

        log("SOURCE PROVENANCE (TMS/TDMS/SMMS -> defect_failure -> maintenance_requirement)")
        rows = q("""
            SELECT df.id, ss.system_code, df.source_record_type, df.source_record_id,
                   df.asset_id, df.detected_at, df.status,
                   mr.id AS mr_id, mr.maintenance_type, mr.status AS mr_status,
                   mr.defect_failure_id
            FROM defect_failure df
            JOIN source_system ss ON ss.id = df.source_system_id
            LEFT JOIN maintenance_requirement mr
              ON mr.defect_failure_id = df.id
            ORDER BY ss.system_code, df.id
        """)
        for r in rows:
            print("  ", dict(zip(r._mapping.keys(), [str(x) if x is not None else None for x in r])))
        assert len(rows) == 3

        tms_df = [r for r in rows if r._mapping["source_record_type"] == "TMS_DEFECT"][0]
        assert tms_df._mapping["source_record_id"] == tms_defect["id"]
        assert tms_df._mapping["asset_id"] == assets["TMS"]["id"]
        assert tms_df._mapping["defect_failure_id"] is not None
        tdms_df = [r for r in rows if r._mapping["source_record_type"] == "TDMS_FAILURE"][0]
        assert tdms_df._mapping["source_record_id"] == tdms_failure["id"]
        smms_df = [r for r in rows if r._mapping["source_record_type"] == "SMMS_ALERT"][0]
        assert smms_df._mapping["source_record_id"] == smms_alert["id"]

        log("IDEMPOTENCY (run 2 must create 0, skip all)")
        s1 = client.post("/api/unified/normalize/tms").json()
        s2 = client.post("/api/unified/normalize/tdms").json()
        s3 = client.post("/api/unified/normalize/smms").json()
        print("TMS :", s1)
        print("TDMS:", s2)
        print("SMMS:", s3)
        assert s1["created"] == 0 and s2["created"] == 0 and s3["created"] == 0
        assert s1["skipped"] == r1["processed"]
        assert s2["skipped"] == r2["processed"]
        assert s3["skipped"] == r3["processed"]
        for t in ("defect_failure", "maintenance_requirement"):
            assert q(f"SELECT count(*) FROM {t}")[0][0] == 3

        log("SOURCE RECORDS UNCHANGED AFTER NORMALIZATION")
        for t in (
            "tms_inspection", "tms_defect", "tms_maintenance",
            "tdms_inspection", "tdms_failure", "tdms_maintenance",
            "smms_inspection", "smms_alert", "smms_maintenance",
        ):
            count = q(f"SELECT count(*) FROM {t}")[0][0]
            print(f"  {t}: {count}")
            assert count >= 1
        unchanged = q(
            "SELECT defect_description, status FROM tms_defect WHERE id = :id",
            {"id": tms_defect["id"]},
        )[0]
        assert unchanged[0] == f"{TAG_CAUSE} TMS defect observed."
        assert unchanged[1] == "OPEN"

        log("BLOCK REQUIREMENT CREATION (HTTP)")
        mr_tms = [m for m in requirements if m["source_record_type"] == "TMS_MAINTENANCE"][0]
        br = client.post("/api/unified/block-requirements", json={
            "maintenance_requirement_id": mr_tms["id"],
            "station_code": "STA-7",
            "line_number": "L7",
            "block_type": "INTEGRATED_BLOCK",
            "required_duration_minutes": 120,
            "earliest_start": "2026-05-11T00:00:00",
            "latest_end": "2026-05-11T23:59:59",
            "power_block_required": True,
            "traffic_block_required": True,
            "resource_notes": f"{TAG_CAUSE} resource note.",
            "status": "REQUIRED",
            "remarks": f"{TAG_CAUSE} block requirement.",
        })
        assert br.status_code == 201, br.text
        br = br.json()
        print("created block_requirement id:", br["id"])

        log("FULL CHAIN VERIFICATION: source -> defect_failure -> maintenance_requirement -> block_requirement")
        chain = q("""
            SELECT td.id AS source_defect_id, td.defect_code,
                   df.id AS df_id, mr.id AS mr_id, br.id AS br_id,
                   br.block_type, br.required_duration_minutes,
                   br.power_block_required, br.traffic_block_required,
                   ss.system_code
            FROM block_requirement br
            JOIN maintenance_requirement mr ON mr.id = br.maintenance_requirement_id
            JOIN defect_failure df ON df.id = mr.defect_failure_id
            JOIN source_system ss ON ss.id = df.source_system_id
            JOIN tms_defect td ON td.id = df.source_record_id
            WHERE br.id = :id
        """, {"id": br["id"]})
        assert chain and chain[0] is not None, "full chain join failed"
        chain = chain[0]
        print("  ", dict(zip(chain._mapping.keys(), [str(x) for x in chain])))
        assert chain._mapping["source_defect_id"] == tms_defect["id"]
        assert chain._mapping["block_type"] == "INTEGRATED_BLOCK"

        log("INVALID / VALIDATION HTTP CHECKS")
        bad_ref = client.post("/api/unified/block-requirements", json={
            "maintenance_requirement_id": 999999,
            "block_type": "TRAFFIC_BLOCK",
            "status": "REQUIRED",
        })
        assert bad_ref.status_code == 404, bad_ref.text
        bad_dur = client.post("/api/unified/block-requirements", json={
            "maintenance_requirement_id": mr_tms["id"],
            "block_type": "LINE_BLOCK",
            "required_duration_minutes": 0,
            "status": "REQUIRED",
        })
        assert bad_dur.status_code == 422, bad_dur.text
        bad_range = client.post("/api/unified/block-requirements", json={
            "maintenance_requirement_id": mr_tms["id"],
            "block_type": "LINE_BLOCK",
            "earliest_start": "2026-05-11T10:00:00",
            "latest_end": "2026-05-11T09:00:00",
            "status": "REQUIRED",
        })
        assert bad_range.status_code == 422, bad_range.text
        missing = client.post("/api/unified/block-requirements", json={
            "maintenance_requirement_id": mr_tms["id"],
            "status": "REQUIRED",
        })
        assert missing.status_code == 422, missing.text
        print("  404 invalid FK: OK")
        print("  422 invalid duration: OK")
        print("  422 invalid time range: OK")
        print("  422 missing field: OK")

        log("AVAILABLE WINDOW UNCHANGED AFTER NORMALIZATION")
        windows_after = client.get("/api/coa/available-windows").json()
        assert windows_after == windows_before, (windows_before, windows_after)
        print("  available window rows identical before/after normalization:", windows_after)

        log("AI / PLANNING SAFETY (forbidden columns absent in new tables)")
        insp = inspect(ENG)
        for t in ("defect_failure", "maintenance_requirement", "block_requirement"):
            cols = {c["name"] for c in insp.get_columns(t)}
            hit = cols & set(FORBIDDEN_COLUMNS)
            assert not hit, f"{t} contains {hit}"
            print(f"  {t}: no forbidden columns")

        log("STRUCTURAL VERIFICATION (PK / FK / unique / indexes / nullability)")
        for t in ("defect_failure", "maintenance_requirement", "block_requirement"):
            print(f"--- {t} ---")
            print("  PK:", insp.get_pk_constraint(t))
            print("  columns:", json_dumps([(c["name"], str(c["type"]), c["nullable"])
                                             for c in insp.get_columns(t)]))
            print("  unique:", json_dumps([(u["name"], u["column_names"])
                                           for u in insp.get_unique_constraints(t)]))
            print("  indexes:", json_dumps([(i["name"], i["column_names"], i["unique"])
                                            for i in insp.get_indexes(t)]))
            print("  FKs:", json_dumps([
                (fk["name"], fk["constrained_columns"], fk["referred_table"],
                 fk["referred_columns"], fk["options"])
                for fk in insp.get_foreign_keys(t)
            ]))

        print("\nALL CHECKS PASSED")
    finally:
        with SessionLocal() as db:
            log("CLEANUP (FK-safe order)")
            asset_ids = assets_created

            print("  deleting block_requirement rows...")
            db.execute(text(
                "DELETE FROM block_requirement WHERE maintenance_requirement_id IN "
                "(SELECT id FROM maintenance_requirement WHERE asset_id = ANY(:ids))"
            ), {"ids": asset_ids})
            print("  deleting maintenance_requirement rows...")
            db.execute(text(
                "DELETE FROM maintenance_requirement WHERE asset_id = ANY(:ids)"
            ), {"ids": asset_ids})
            print("  deleting defect_failure rows...")
            db.execute(text(
                "DELETE FROM defect_failure WHERE asset_id = ANY(:ids)"
            ), {"ids": asset_ids})

            print("  deleting TMS source rows...")
            db.execute(text("DELETE FROM tms_maintenance WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            db.execute(text("DELETE FROM tms_defect WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            db.execute(text("DELETE FROM tms_inspection WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})

            print("  deleting TDMS source rows...")
            db.execute(text("DELETE FROM tdms_maintenance WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            db.execute(text("DELETE FROM tdms_failure WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            db.execute(text("DELETE FROM tdms_inspection WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})

            print("  deleting SMMS source rows...")
            db.execute(text("DELETE FROM smms_maintenance WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            db.execute(text("DELETE FROM smms_alert WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})
            db.execute(text("DELETE FROM smms_inspection WHERE asset_id = ANY(:ids)"), {"ids": asset_ids})

            print("  deleting synthetic assets...")
            db.execute(text("DELETE FROM asset_master WHERE id = ANY(:ids)"), {"ids": asset_ids})
            assets_created.clear()

            print("  deleting synthetic COA data (train/occupancy/windows)...")
            db.execute(text("DELETE FROM available_window"))
            db.execute(text(
                "DELETE FROM line_occupancy WHERE train_id = ANY(:ids)"
            ), {"ids": trains_created})
            db.execute(text(
                "DELETE FROM train_movement WHERE train_id = ANY(:ids)"
            ), {"ids": trains_created})
            db.execute(text(
                "DELETE FROM train_schedule WHERE train_id = ANY(:ids)"
            ), {"ids": trains_created})
            db.execute(text(
                "DELETE FROM operational_event WHERE train_id = ANY(:ids)"
            ), {"ids": trains_created})
            db.execute(text("DELETE FROM train WHERE id = ANY(:ids)"), {"ids": trains_created})
            trains_created.clear()
            db.commit()

            log("FINAL DATABASE STATE (must be clean)")
            for t in tables + ["asset_master", "train"]:
                print(f"  {t}: {db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")
            remnants = db.execute(text("SELECT count(*) FROM defect_failure")).scalar()
            assert remnants == 0, "defect_failure not clean"
            remnants = db.execute(text("SELECT count(*) FROM maintenance_requirement")).scalar()
            assert remnants == 0, "maintenance_requirement not clean"
            remnants = db.execute(text("SELECT count(*) FROM block_requirement")).scalar()
            assert remnants == 0, "block_requirement not clean"
            remnants = db.execute(text("SELECT count(*) FROM asset_master")).scalar()
            assert remnants == 0, "asset_master not clean"
            print("\nCLEANUP VERIFIED")


def json_dumps(items):
    import json
    return json.dumps(items)


if __name__ == "__main__":
    try:
        main()
    finally:
        if client is not None:
            client.close()
        stop_server()