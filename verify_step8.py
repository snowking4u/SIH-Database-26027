"""STEP 8 live verification: Planning Foundation layer.

Runs a real uvicorn server against the live PostgreSQL database, creates
synthetic TMS/TDMS source chains, normalizes them, creates a block
requirement, then exercises the /api/planning endpoints (task generation,
constraint generation, resources, task-resource links, dependencies),
verifies provenance / idempotency / available-window preservation /
no-forbidden-columns, then cleans up all synthetic data.

The seeded source systems (TMS, TDMS, SMMS, COA) are reused and never deleted.
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

TAG = "VERIFY8"
TAG_CAUSE = "STEP8-SYNTHETIC"

FORBIDDEN_COLUMNS = [
    "priority_score", "risk_score", "predicted_failure", "recommended_block",
    "optimization_score", "optimized_schedule", "ai_recommendation",
    "candidate_block_window", "optimization_run", "optimization_input",
    "optimization_output", "block_plan", "block_plan_task", "plan_validation",
    "controller_decision", "execution_outcome", "validation_result",
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
        heads = [list(r) for r in q("SELECT version_num FROM alembic_version")]
        assert heads and heads[0][0] == "a4f1c9b2e8d3", heads
        print("source_systems:", [r[0] for r in q("SELECT system_code FROM source_system ORDER BY id")])

        log("BASELINE COUNTS (pre-seeding)")
        tables = [
            "tms_inspection", "tms_defect", "tms_maintenance",
            "tdms_inspection", "tdms_failure", "tdms_maintenance",
            "defect_failure", "maintenance_requirement", "block_requirement",
            "available_window",
        ] + PLANNING_TABLES
        for t in tables:
            print(f"  {t}: {q(f'SELECT count(*) FROM {t}')[0][0]}")

        log("COA AVAILABLE WINDOW (context, must stay unchanged)")
        coa = get_source_system("COA")
        train = client.post("/api/coa/trains", json={
            "train_id": f"{TAG}-COA-TRAIN-1",
            "train_number": "7998",
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
        print("available windows before planning:", windows_before)

        log("SYNTHETIC SOURCE CHAINS (TMS + TDMS)")
        tms = get_source_system("TMS")
        tdms = get_source_system("TDMS")
        assets = {}
        assets["TMS"] = create_asset(tms["id"], "TMS")
        assets["TDMS"] = create_asset(tdms["id"], "TDMS")

        _, tms_defect, tms_maint = create_tms_chain(assets["TMS"])
        _, tdms_failure, tdms_maint = create_tdms_chain(assets["TDMS"])

        log("NORMALIZATION")
        r1 = client.post("/api/unified/normalize/tms").json()
        r2 = client.post("/api/unified/normalize/tdms").json()
        print("TMS :", r1)
        print("TDMS:", r2)
        requirements = client.get("/api/unified/maintenance").json()
        mr_tms = [m for m in requirements if m["source_record_type"] == "TMS_MAINTENANCE"][0]
        mr_tdms = [m for m in requirements if m["source_record_type"] == "TDMS_MAINTENANCE"][0]

        log("BLOCK REQUIREMENT CREATION (HTTP)")
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

        log("PLANNING TASK GENERATION (run 1)")
        s1 = client.post("/api/planning/generate-tasks").json()
        print("summary:", s1)
        assert s1["processed"] == 2
        assert s1["created"] == 2
        assert s1["skipped"] == 0
        tasks = client.get("/api/planning/tasks").json()
        print("tasks:", len(tasks))
        task_tms = [t for t in tasks if t["maintenance_requirement_id"] == mr_tms["id"]][0]
        task_tdms = [t for t in tasks if t["maintenance_requirement_id"] == mr_tdms["id"]][0]
        assert task_tms["block_requirement_id"] == br["id"]
        assert task_tms["asset_id"] == assets["TMS"]["id"]
        assert task_tms["duration_minutes"] == 150
        assert task_tms["earliest_start"] == "2026-05-11T00:00:00"
        assert task_tms["latest_end"] == "2026-05-11T23:59:59"
        assert task_tms["location_code"] == "STA-7"
        assert task_tms["status"] == "OPEN"
        assert task_tdms["block_requirement_id"] is None
        assert task_tdms["duration_minutes"] == 180
        single = client.get(f"/api/planning/tasks/{task_tms['id']}")
        assert single.status_code == 200 and single.json()["id"] == task_tms["id"]
        by_mr = client.get(f"/api/planning/tasks?maintenance_requirement_id={mr_tms['id']}").json()
        assert len(by_mr) == 1
        print("task_tms:", task_tms["task_code"], "| task_tdms:", task_tdms["task_code"])

        log("PLANNING TASK GENERATION (run 2 -> idempotent)")
        s2 = client.post("/api/planning/generate-tasks").json()
        print("summary:", s2)
        assert s2["created"] == 0
        assert s2["skipped"] == s1["processed"]
        assert q("SELECT count(*) FROM planning_task")[0][0] == 2

        log("PLANNING CONSTRAINT GENERATION (run 1)")
        c1 = client.post("/api/planning/generate-constraints").json()
        print("summary:", c1)
        assert c1["processed"] == 2
        assert c1["created"] == 6
        assert c1["skipped"] == 1
        constraints = client.get("/api/planning/constraints").json()
        print("constraints:", len(constraints))
        task_constraints = [c for c in constraints if c["planning_task_id"] == task_tms["id"]]
        assert len(task_constraints) == 6
        types = {c["constraint_type"]: c["constraint_value"] for c in task_constraints}
        assert types["DURATION"] == "120"
        assert types["LOCATION"] == "STA-7"
        assert types["LINE"] == "L7"
        assert types["POWER_BLOCK"] == "TRUE"
        assert types["TRAFFIC_BLOCK"] == "TRUE"
        assert types["TIME_WINDOW"] == "2026-05-11T00:00:00|2026-05-11T23:59:59"
        for c in task_constraints:
            assert c["hard_constraint"] is True
            assert c["source"] == "BLOCK_REQUIREMENT"
        tdms_constraints = [c for c in constraints if c["planning_task_id"] == task_tdms["id"]]
        assert tdms_constraints == []
        print("constraint types:", sorted(types))

        log("PLANNING CONSTRAINT GENERATION (run 2 -> idempotent)")
        c2 = client.post("/api/planning/generate-constraints").json()
        print("summary:", c2)
        assert c2["created"] == 0
        assert c2["skipped"] == c1["created"] + c1["skipped"]
        assert q("SELECT count(*) FROM planning_constraint")[0][0] == 6

        log("RESOURCES / TASK-RESOURCES / DEPENDENCIES (HTTP)")
        res = client.post("/api/planning/resources", json={
            "resource_code": f"{TAG}-RES-001",
            "resource_type": "TEAM",
            "resource_name": f"TEST/SYNTHETIC Track Team ({TAG_CAUSE})",
            "capacity": 4,
            "unit": "workers",
            "status": "AVAILABLE",
            "location_code": "STA-7",
            "source_system_id": tms["id"],
        })
        assert res.status_code == 201, res.text
        res = res.json()
        dup_res = client.post("/api/planning/resources", json={
            "resource_code": f"{TAG}-RES-001",
            "resource_type": "TEAM",
            "resource_name": "duplicate",
            "status": "AVAILABLE",
        })
        assert dup_res.status_code == 409, dup_res.text
        sep_id = client.post("/api/planning/resources", json={
            "resource_code": f"{TAG}-RES-002",
            "resource_type": "VEHICLE",
            "resource_name": f"TEST/SYNTHETIC Motor Trolley ({TAG_CAUSE})",
            "status": "AVAILABLE",
        }).json()
        assert sep_id["source_system_id"] is None

        link = client.post("/api/planning/task-resources", json={
            "planning_task_id": task_tms["id"],
            "planning_resource_id": res["id"],
            "required_quantity": 2,
            "allocation_status": "REQUIRED",
        })
        assert link.status_code == 201, link.text
        link = link.json()
        dup_link = client.post("/api/planning/task-resources", json={
            "planning_task_id": task_tms["id"],
            "planning_resource_id": res["id"],
            "required_quantity": 1,
            "allocation_status": "REQUIRED",
        })
        assert dup_link.status_code == 409, dup_link.text

        dep = client.post("/api/planning/dependencies", json={
            "predecessor_task_id": task_tms["id"],
            "successor_task_id": task_tdms["id"],
            "dependency_type": "FINISH_TO_START",
            "lag_minutes": 10,
        })
        assert dep.status_code == 201, dep.text
        dep = dep.json()
        dup_dep = client.post("/api/planning/dependencies", json={
            "predecessor_task_id": task_tms["id"],
            "successor_task_id": task_tdms["id"],
            "dependency_type": "FINISH_TO_START",
            "lag_minutes": 0,
        })
        assert dup_dep.status_code == 409, dup_dep.text
        self_dep = client.post("/api/planning/dependencies", json={
            "predecessor_task_id": task_tms["id"],
            "successor_task_id": task_tms["id"],
            "dependency_type": "FINISH_TO_START",
        })
        assert self_dep.status_code == 422, self_dep.text
        filt = client.get(f"/api/planning/dependencies?predecessor_task_id={task_tms['id']}").json()
        assert len(filt) == 1
        print("resource:", res["resource_code"], "| link id:", link["id"], "| dep id:", dep["id"])

        log("INVALID / VALIDATION HTTP CHECKS")
        bad_constraint_fk = client.post("/api/planning/constraints", json={
            "planning_task_id": 999999,
            "constraint_type": "OPERATIONAL",
            "constraint_value": "X",
        })
        assert bad_constraint_fk.status_code == 404, bad_constraint_fk.text
        bad_link_fk = client.post("/api/planning/task-resources", json={
            "planning_task_id": task_tms["id"],
            "planning_resource_id": 999999,
            "required_quantity": 1,
            "allocation_status": "REQUIRED",
        })
        assert bad_link_fk.status_code == 404, bad_link_fk.text
        bad_quantity = client.post("/api/planning/task-resources", json={
            "planning_task_id": task_tms["id"],
            "planning_resource_id": res["id"],
            "required_quantity": 0,
            "allocation_status": "REQUIRED",
        })
        assert bad_quantity.status_code == 422, bad_quantity.text
        bad_range = client.post("/api/planning/constraints", json={
            "planning_task_id": task_tms["id"],
            "constraint_type": "TIME_WINDOW",
            "constraint_value": "NIGHT",
            "effective_start": "2026-05-11T23:00:00",
            "effective_end": "2026-05-11T22:00:00",
        })
        assert bad_range.status_code == 422, bad_range.text
        manual = client.post("/api/planning/constraints", json={
            "planning_task_id": task_tms["id"],
            "constraint_type": "OPERATIONAL",
            "constraint_value": "WORK-ONLY-AT-NIGHT",
            "hard_constraint": True,
            "description": f"{TAG_CAUSE} operational constraint.",
            "source": "TEST",
        })
        assert manual.status_code == 201, manual.text
        print("  404 invalid FK: OK | 422 invalid quantity/range: OK | manual constraint: OK")

        log("FULL PROVENANCE JOIN (source -> defect/failure -> MR -> block -> task -> constraints/resource/dep)")
        rows = q("""
            SELECT pt.id AS pt_id, pt.task_code, pt.status,
                   mr.id AS mr_id, mr.source_record_type, mr.required_duration_minutes AS mr_duration,
                   df.id AS df_id, ss.system_code,
                   br.id AS br_id, br.block_type,
                   a.id AS asset_id, a.source_asset_id
            FROM planning_task pt
            JOIN maintenance_requirement mr ON mr.id = pt.maintenance_requirement_id
            JOIN defect_failure df ON df.id = mr.defect_failure_id
            JOIN source_system ss ON ss.id = df.source_system_id
            JOIN asset_master a ON a.id = pt.asset_id
            LEFT JOIN block_requirement br ON br.id = pt.block_requirement_id
            ORDER BY pt.id
        """)
        for r in rows:
            print("  ", dict(zip(r._mapping.keys(), [str(x) if x is not None else None for x in r])))
        assert len(rows) == 2
        tms_row = [r for r in rows if r._mapping["system_code"] == "TMS"][0]
        tdms_row = [r for r in rows if r._mapping["system_code"] == "TDMS"][0]
        assert tms_row._mapping["br_id"] == br["id"]
        assert tms_row._mapping["mr_id"] == mr_tms["id"]
        assert tms_row._mapping["asset_id"] == assets["TMS"]["id"]
        assert tdms_row._mapping["br_id"] is None

        prov = q("""
            SELECT tr.id AS tr_id, pr.resource_code, tr.required_quantity,
                   td.id AS td_id, td.dependency_type, td.lag_minutes,
                   pc.id AS pc_id
            FROM task_resource tr
            JOIN planning_resource pr ON pr.id = tr.planning_resource_id
            LEFT JOIN task_dependency td ON td.predecessor_task_id = tr.planning_task_id
            LEFT JOIN planning_constraint pc
              ON pc.planning_task_id = tr.planning_task_id AND pc.source = 'BLOCK_REQUIREMENT'
            WHERE tr.planning_task_id = :id
            LIMIT 1
        """, {"id": task_tms["id"]})
        assert prov and prov[0] is not None, "task_resource provenance join failed"
        prov = prov[0]
        print("  ", dict(zip(prov._mapping.keys(), [str(x) for x in prov])))
        assert prov._mapping["resource_code"] == f"{TAG}-RES-001"
        assert prov._mapping["required_quantity"] == 2
        assert prov._mapping["dependency_type"] == "FINISH_TO_START"

        log("SOURCE/UNIFIED RECORDS UNCHANGED AFTER GENERATION")
        for t in (
            "tms_inspection", "tms_defect", "tms_maintenance",
            "tdms_inspection", "tdms_failure", "tdms_maintenance",
            "defect_failure", "maintenance_requirement", "block_requirement",
        ):
            count = q(f"SELECT count(*) FROM {t}")[0][0]
            print(f"  {t}: {count}")
        unchanged = q(
            "SELECT defect_description, status FROM tms_defect WHERE id = :id",
            {"id": tms_defect["id"]},
        )[0]
        assert unchanged[0] == f"{TAG_CAUSE} TMS defect observed."
        assert unchanged[1] == "OPEN"

        log("AVAILABLE WINDOW UNCHANGED AFTER PLANNING")
        windows_after = client.get("/api/coa/available-windows").json()
        assert windows_after == windows_before, (windows_before, windows_after)
        print("  available window rows identical before/after planning:", windows_after)

        log("AI / OPTIMIZATION SAFETY (forbidden columns absent in planning tables)")
        insp = inspect(ENG)
        for t in PLANNING_TABLES:
            cols = {c["name"] for c in insp.get_columns(t)}
            hit = cols & set(FORBIDDEN_COLUMNS)
            assert not hit, f"{t} contains {hit}"
            print(f"  {t}: no forbidden columns")

        log("STRUCTURAL VERIFICATION (planning tables)")
        for t in PLANNING_TABLES:
            print(f"--- {t} ---")
            pk = insp.get_pk_constraint(t)
            print("  PK:", pk)
            assert pk["constrained_columns"], f"{t} has no PK"
            print("  columns:", json.dumps([(c["name"], str(c["type"]), c["nullable"])
                                            for c in insp.get_columns(t)]))
            print("  unique:", json.dumps([(u["name"], u["column_names"])
                                           for u in insp.get_unique_constraints(t)]))
            print("  indexes:", json.dumps([(i["name"], i["column_names"], i["unique"])
                                            for i in insp.get_indexes(t)]))
            fks = insp.get_foreign_keys(t)
            for fk in fks:
                assert fk["options"].get("ondelete") == "RESTRICT", (t, fk["options"])
            print("  FKs:", json.dumps([
                (fk["name"], fk["constrained_columns"], fk["referred_table"],
                 fk["referred_columns"], fk["options"])
                for fk in fks
            ]))

        log("CHECK CONSTRAINTS PRESENT")
        dep_checks = {c["name"] for c in insp.get_check_constraints("task_dependency")}
        print("  task_dependency:", dep_checks)
        assert dep_checks == {
            "ck_task_dependency_predecessor_ne_successor",
            "ck_task_dependency_lag_minutes_non_negative",
        }
        assert insp.get_check_constraints("planning_resource") == []

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
            print("  deleting planning_task rows...")
            db.execute(text(
                "DELETE FROM planning_task WHERE asset_id = ANY(:ids)"
            ), {"ids": asset_ids})
            print("  deleting planning_resource rows...")
            db.execute(text(
                "DELETE FROM planning_resource WHERE resource_code LIKE :tag"
            ), {"tag": f"{TAG}-%"} or f"{TAG}-%")

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
            for t in PLANNING_TABLES:
                remnants = db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                assert remnants == 0, f"{t} not clean ({remnants})"
            remnants = db.execute(text("SELECT count(*) FROM defect_failure")).scalar()
            assert remnants == 0, "defect_failure not clean"
            remnants = db.execute(text("SELECT count(*) FROM maintenance_requirement")).scalar()
            assert remnants == 0, "maintenance_requirement not clean"
            remnants = db.execute(text("SELECT count(*) FROM block_requirement")).scalar()
            assert remnants == 0, "block_requirement not clean"
            remnants = db.execute(text("SELECT count(*) FROM asset_master")).scalar()
            assert remnants == 0, "asset_master not clean"
            print("\nCLEANUP VERIFIED")


if __name__ == "__main__":
    try:
        main()
    finally:
        if client is not None:
            client.close()
        stop_server()