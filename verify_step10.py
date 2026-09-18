"""STEP 10 live verification: optimization engine foundation (storage contract).

Runs a real uvicorn server against the live PostgreSQL database and verifies:

1. Alembic single head d2e6b9c4f1a7 on the live database.
2. All 8 STEP 10 tables exist with id primary keys, RESTRICT FKs, expected
   indexes/unique constraints, and NO forbidden AI columns.
3. Full CRUD E2E for every STEP 10 resource via /api/optimization/*:
   optimization_run, optimization_input (all roles), optimization_output
   (JSONB payload contract), block_plan, block_plan_task, plan_validation
   (deterministic /validate), controller_decision, execution_outcome.
4. Deterministic validation: WINDOW_FIT PASSED for a task that fits its
   candidate, DEPENDENCY FAILED for a FINISH_TO_START reversal, plan status
   unchanged, no controller decision auto-created.
5. HTTP semantics: 404 invalid FK, 409 duplicate unique, 422 invalid
   enum/date-range/all-null input.
6. Provenance from optimization records back to source systems.
7. Source/unified/planning/candidate rows unchanged by STEP 10 writes.
8. FK-safe cleanup, then a clean database with seed source systems intact.

No AI/ML/optimization/ranking/scoring algorithm is executed anywhere.
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

TAG = "VERIFY10"
TAG_CAUSE = "STEP10-SYNTHETIC"

FORBIDDEN_TOKENS = [
    "score", "confidence", "prediction", "recommended", "optimal",
    "embedding", "feature_vector", "probability", "priority", "risk", "rank",
]

STEP10_TABLES = [
    "optimization_run", "optimization_input", "optimization_output",
    "block_plan", "block_plan_task", "plan_validation",
    "controller_decision", "execution_outcome",
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


def create_tms_chain(asset, defect_code, maint_start, maint_end):
    insp = client.post("/api/tms/inspections", json={
        "asset_id": asset["id"],
        "inspection_date": "2026-05-11T09:00:00",
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
        "defect_code": defect_code,
        "defect_description": f"{TAG_CAUSE} TMS defect {defect_code}.",
        "severity": "HIGH",
        "detected_date": "2026-05-11T09:10:00",
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
        "start_date": maint_start,
        "end_date": maint_end,
        "status": "PLANNED",
        "remarks": f"{TAG_CAUSE} TMS maintenance record.",
    })
    assert maint.status_code == 201, maint.text
    return defect, maint.json()


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


def make_run(code):
    r = client.post("/api/optimization/runs", json={
        "run_code": code,
        "run_type": "PLANNING",
        "status": "REQUESTED",
        "objective_description": f"{TAG_CAUSE} objective.",
        "model_name": "STEP10-STATIC-GATE-BOX",
        "model_version": "0.1.0-frozen",
    })
    assert r.status_code == 201, r.text
    return r.json()


def make_plan(code, run_id):
    r = client.post("/api/optimization/plans", json={
        "plan_code": code,
        "plan_date": "2026-05-11",
        "status": "PROPOSED",
        "optimization_run_id": run_id,
        "planning_horizon_start": "2026-05-11T09:00:00",
        "planning_horizon_end": "2026-05-11T16:00:00",
        "description": f"{TAG_CAUSE} block plan.",
    })
    assert r.status_code == 201, r.text
    return r.json()


def add_plan_task(plan_id, task_id, candidate_id, start, end, duration, **extra):
    payload = {
        "block_plan_id": plan_id,
        "planning_task_id": task_id,
        "planned_start": start,
        "planned_end": end,
        "planned_duration_minutes": duration,
    }
    if candidate_id is not None:
        payload["candidate_block_window_id"] = candidate_id
    payload["status"] = "CONFIRMED"
    payload.update(extra)
    return client.post("/api/optimization/plan-tasks", json=payload)


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
        assert heads and heads[0][0] == "d2e6b9c4f1a7", heads
        print("source_systems:", [r[0] for r in q(
            "SELECT system_code FROM source_system ORDER BY id")])

        log("BASELINE COUNTS (pre-seeding)")
        all_tables = ("tms_inspection", "tms_defect", "tms_maintenance",
                      "defect_failure", "maintenance_requirement", "block_requirement",
                      "available_window", "candidate_block_window")
        all_tables = all_tables + tuple(PLANNING_TABLES) + tuple(STEP10_TABLES)
        for t in all_tables:
            print(f"  {t}: {q(f'SELECT count(*) FROM {t}')[0][0]}")
        assert all(q(f"SELECT count(*) FROM {t}")[0][0] == 0 for t in STEP10_TABLES)

        log("STRUCTURAL VERIFICATION (8 STEP 10 tables)")
        insp = inspect(ENG)
        for table in STEP10_TABLES:
            assert table in insp.get_table_names(), table
            pk = insp.get_pk_constraint(table)
            assert pk["constrained_columns"] == ["id"], (table, pk)
            cols = {c["name"] for c in insp.get_columns(table)}
            for column in cols:
                for token in FORBIDDEN_TOKENS:
                    assert token not in column, f"{table}.{column} contains {token}"
            fks = insp.get_foreign_keys(table)
            for fk in fks:
                assert fk["options"].get("ondelete") == "RESTRICT", (table, fk, fk["options"])
            print(f"  {table}: ok (FKs all RESTRICT, no forbidden columns)")
        print("  output_payload type:", [
            (c["name"], str(c["type"])) for c in insp.get_columns("optimization_output")
            if c["name"] == "output_payload"])
        assert any(
            c["name"] == "output_payload" and str(c["type"]) == "JSONB"
            for c in insp.get_columns("optimization_output")
        )
        uniq = {
            tuple(u["column_names"])
            for u in insp.get_unique_constraints("block_plan_task")
        }
        print("  block_plan_task unique:", uniq)
        assert ("block_plan_id", "planning_task_id") in uniq
        run_uniq = {tuple(u["column_names"]) for u in insp.get_unique_constraints("optimization_run")}
        print("  optimization_run unique:", run_uniq)
        assert ("run_code",) in run_uniq

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
        create_occupancy(train, "STA-7", "L7", "00:00", "10:00", "A1")
        create_occupancy(train, "STA-7", "L7", "14:00", "15:00", "A2")
        create_occupancy(train, "STA-7", "L7", "16:00", "20:00", "A3")
        create_occupancy(train, "STA-8", "L7", "00:00", "10:00", "B1")
        create_occupancy(train, "STA-8", "L7", "14:00", "20:00", "B2")
        create_occupancy(train, "STA-7", "L8", "00:00", "10:00", "C1")
        create_occupancy(train, "STA-7", "L8", "14:00", "20:00", "C2")
        gen = client.post("/api/coa/available-windows/generate")
        assert gen.status_code == 200, gen.text
        windows = client.get("/api/coa/available-windows").json()
        assert len(windows) == 4, windows
        by_key = {}
        for w in windows:
            by_key.setdefault((w["station_code"], w["line_number"]), []).append(w)
        w_sta7 = max(by_key[("STA-7", "L7")], key=lambda w: w["duration_minutes"])
        w_short = min(by_key[("STA-7", "L7")], key=lambda w: w["duration_minutes"])
        print("  windows STA-7/L7:", [
            (w["duration_minutes"], w["window_start"], w["window_end"])
            for w in by_key[("STA-7", "L7")]])

        log("SYNTHETIC TMS CHAINS (two tasks, same asset/station/line)")
        tms = get_source_system("TMS")
        asset = create_asset(tms["id"], "TMS")
        _, maint_a = create_tms_chain(asset, "TMS-DF-001",
                                      "2026-05-11T09:00:00", "2026-05-11T11:30:00")
        _, maint_b = create_tms_chain(asset, "TMS-DF-002",
                                      "2026-05-11T09:00:00", "2026-05-11T12:00:00")
        client.post("/api/unified/normalize/tms")
        requirements = client.get("/api/unified/maintenance").json()
        mr_a = [m for m in requirements
                if m["source_record_type"] == "TMS_MAINTENANCE"
                and m["source_record_id"] == maint_a["id"]][0]
        mr_b = [m for m in requirements
                if m["source_record_type"] == "TMS_MAINTENANCE"
                and m["source_record_id"] == maint_b["id"]][0]
        for mr, code in ((mr_a, "BR-A"), (mr_b, "BR-B")):
            r = client.post("/api/unified/block-requirements", json={
                "maintenance_requirement_id": mr["id"],
                "station_code": "STA-7",
                "line_number": "L7",
                "block_type": "INTEGRATED_BLOCK",
                "required_duration_minutes": 120,
                "power_block_required": False,
                "traffic_block_required": False,
                "resource_notes": f"{TAG_CAUSE} resource note.",
                "status": "REQUIRED",
                "remarks": f"{TAG_CAUSE} {code}.",
            })
            assert r.status_code == 201, r.text

        s1 = client.post("/api/planning/generate-tasks").json()
        print("generate-tasks summary:", s1)
        assert s1["created"] == 2
        tasks = client.get("/api/planning/tasks").json()
        task_a = [t for t in tasks if t["maintenance_requirement_id"] == mr_a["id"]][0]
        task_b = [t for t in tasks if t["maintenance_requirement_id"] == mr_b["id"]][0]
        print("  task A duration:", task_a["duration_minutes"])
        print("  task B duration:", task_b["duration_minutes"])
        assert task_a["duration_minutes"] == 150
        assert task_b["duration_minutes"] == 180

        log("CANDIDATE GENERATION (2 tasks x 4 windows = 8)")
        g1 = client.post("/api/candidates/generate").json()
        print("  summary:", g1)
        assert g1["processed"] == 8 and g1["created"] == 8, g1
        cand_a = [c for c in client.get(
            f"/api/candidates/windows?planning_task_id={task_a['id']}").json()
            if c["available_window_id"] == w_sta7["id"]][0]
        assert cand_a["feasible"] is True
        assert cand_a["candidate_start"].startswith("2026-05-11T10:00")
        print("  candidate A (STA-7/L7 240m):",
              cand_a["candidate_start"], cand_a["candidate_end"], cand_a["candidate_duration_minutes"])
        assert cand_a["candidate_duration_minutes"] == 150

        log("PLANNING CONSTRAINT + RESOURCE + DEPENDENCY (deterministic prerequisites)")
        constraint = client.post("/api/planning/constraints", json={
            "planning_task_id": task_a["id"],
            "constraint_type": "MAX_DURATION",
            "constraint_value": "240",
            "hard_constraint": True,
            "source": f"{TAG_CAUSE}",
        })
        assert constraint.status_code == 201, constraint.text
        constraint = constraint.json()
        resource = client.post("/api/planning/resources", json={
            "resource_code": f"{TAG}-RES-1",
            "resource_type": "ENGINEERING_TEAM",
            "resource_name": f"TEST/SYNTHETIC ({TAG_CAUSE})",
            "status": "AVAILABLE",
        })
        assert resource.status_code == 201, resource.text
        resource = resource.json()
        dep = client.post("/api/planning/dependencies", json={
            "predecessor_task_id": task_a["id"],
            "successor_task_id": task_b["id"],
            "dependency_type": "FINISH_TO_START",
            "lag_minutes": 0,
        })
        assert dep.status_code == 201, dep.text
        dep = dep.json()

        log("OPTIMIZATION RUN (create + duplicate 409 + filters)")
        first = make_run(f"RUN-{TAG}-1")
        dup = client.post("/api/optimization/runs", json={
            "run_code": first["run_code"], "run_type": "PLANNING", "status": "REQUESTED"})
        assert dup.status_code == 409, dup.text
        run = make_run(f"RUN-{TAG}-2")
        assert len(client.get("/api/optimization/runs?model_name=STEP10-STATIC-GATE-BOX").json()) == 2
        assert len(client.get("/api/optimization/runs?run_type=PLANNING").json()) == 2
        assert client.get(f"/api/optimization/runs/{run['id']}").json()["id"] == run["id"]
        assert client.get("/api/optimization/runs/999999").status_code == 404
        print("  run ok:", run["id"], run["model_name"])
        print("  duplicate run_code -> 409: OK")

        log("OPTIMIZATION INPUT (all roles, all-null 422, invalid FK 404)")
        role_cases = [
            ("TASK", {"planning_task_id": task_a["id"]}),
            ("CANDIDATE_WINDOW", {"candidate_block_window_id": cand_a["id"]}),
            ("CONSTRAINT", {"planning_constraint_id": constraint["id"]}),
            ("RESOURCE", {"planning_resource_id": resource["id"]}),
            ("DEPENDENCY", {"task_dependency_id": dep["id"]}),
        ]
        for role, ref in role_cases:
            r = client.post("/api/optimization/inputs", json={
                "optimization_run_id": run["id"], "input_role": role, **ref})
            assert r.status_code == 201, r.text
        assert client.post("/api/optimization/inputs", json={
            "optimization_run_id": run["id"], "input_role": "TASK"}).status_code == 422
        assert client.post("/api/optimization/inputs", json={
            "optimization_run_id": 999999, "planning_task_id": task_a["id"],
            "input_role": "TASK"}).status_code == 404
        assert len(client.get(
            f"/api/optimization/inputs?optimization_run_id={run['id']}&input_role=TASK"
        ).json()) == 1
        print("  inputs across all 5 roles: OK")

        log("OPTIMIZATION OUTPUT (JSONB payload contract)")
        payload = {
            "model_metadata": {"framework": "STATIC-GATE-BOX", "n": 1},
            "notes": ["no AI executed"],
            "nested": {"deep": {"truthy": True}},
        }
        out = client.post("/api/optimization/outputs", json={
            "optimization_run_id": run["id"],
            "planning_task_id": task_a["id"],
            "candidate_block_window_id": cand_a["id"],
            "output_type": "WINDOW_ASSIGNMENT",
            "output_status": "PROPOSED",
            "output_payload": payload,
        })
        assert out.status_code == 201, out.text
        out_id = out.json()["id"]
        assert out.json()["selected"] is False
        stored = client.get(f"/api/optimization/outputs/{out_id}").json()
        assert stored["output_payload"] == payload
        print("  JSONB payload round-trip (nested dict): OK")
        metadata_out = client.post("/api/optimization/outputs", json={
            "optimization_run_id": run["id"],
            "output_type": "PLAN_METADATA",
            "output_status": "UNASSIGNED",
            "selected": True,
            "output_payload": {"anything": [1, 2, None]},
        })
        assert metadata_out.status_code == 201, metadata_out.text

        log("BLOCK PLAN (create, horizon 422, FK 404, duplicate plan_code 409)")
        plan = make_plan(f"PLAN-{TAG}-1", run["id"])
        assert client.post("/api/optimization/plans", json={
            "plan_code": "X-IGNORED", "plan_date": "2026-05-11", "status": "DRAFT",
            "planning_horizon_start": "2026-05-11T16:00:00",
            "planning_horizon_end": "2026-05-11T09:00:00"}).status_code == 422
        assert client.post("/api/optimization/plans", json={
            "plan_code": "X-IGNORED", "plan_date": "2026-05-11", "status": "DRAFT",
            "optimization_run_id": 999999,
            "planning_horizon_start": "2026-05-11T09:00:00",
            "planning_horizon_end": "2026-05-11T16:00:00"}).status_code == 404
        assert client.post("/api/optimization/plans", json={
            "plan_code": plan["plan_code"], "plan_date": "2026-05-11",
            "status": "PROPOSED",
            "planning_horizon_start": "2026-05-11T09:00:00",
            "planning_horizon_end": "2026-05-11T16:00:00"}).status_code == 409

        log("BLOCK PLAN TASK (create A + B, duplicate 409)")
        pt_a = add_plan_task(plan["id"], task_a["id"], cand_a["id"],
                             "2026-05-11T10:00:00", "2026-05-11T11:00:00", 60)
        assert pt_a.status_code == 201, pt_a.text
        pt_a = pt_a.json()
        dup = add_plan_task(plan["id"], task_a["id"], None,
                            "2026-05-11T11:00:00", "2026-05-11T12:00:00", 60)
        assert dup.status_code == 409, dup.text
        pt_b = add_plan_task(plan["id"], task_b["id"], None,
                             "2026-05-11T10:30:00", "2026-05-11T12:30:00", 120)
        assert pt_b.status_code == 201, pt_b.text
        pt_b = pt_b.json()
        assert add_plan_task(plan["id"], 999999, None,
                             "2026-05-11T11:00:00", "2026-05-11T12:00:00", 60).status_code == 404
        assert add_plan_task(999999, task_a["id"], None,
                             "2026-05-11T11:00:00", "2026-05-11T12:00:00", 60).status_code == 404
        assert client.get(
            f"/api/optimization/plan-tasks?block_plan_id={plan['id']}").json().__len__() == 2
        print("  tasks A + B placed; duplicate -> 409; bad FK -> 404: OK")

        log("DETERMINISTIC VALIDATION (POST /plans/{id}/validate)")
        results = client.post(f"/api/optimization/plans/{plan['id']}/validate")
        assert results.status_code == 200, results.text
        results = results.json()
        print("  results:")
        for r in results:
            print("   ", r["validation_type"], r["validation_status"], r["validation_message"])
        win_fit = [r for r in results if r["validation_type"] == "WINDOW_FIT"]
        deps = [r for r in results if r["validation_type"] == "DEPENDENCY"]
        assert win_fit and win_fit[0]["validation_status"] == "PASSED", results
        assert deps and deps[0]["validation_status"] == "FAILED", results
        durs = [r for r in results if r["validation_type"] == "DURATION"]
        assert all(r["validation_status"] == "PASSED" for r in durs), results
        assert all(r["validator_version"] == "STEP10-DETERMINISTIC-1.0" for r in results)
        total = len(results)
        assert client.get(
            f"/api/optimization/validations?block_plan_id={plan['id']}").json().__len__() == total

        plan_after = client.get(f"/api/optimization/plans/{plan['id']}").json()
        print("  plan status after validation:", plan_after["status"])
        assert plan_after["status"] == "PROPOSED"
        assert client.get(
            f"/api/optimization/decisions?block_plan_id={plan['id']}").json() == []

        pt_a_good = add_plan_task  # noqa: F841 (kept as placeholder no-op reference)
        print("  WINDOW_FIT PASSED, DEPENDENCY FAILED, status unchanged: OK")

        log("CONTROLLER DECISION (no auto-approval)")
        decision = client.post("/api/optimization/decisions", json={
            "block_plan_id": plan["id"],
            "decision": "RETURNED_FOR_REVISION",
            "controller_code": "CTRL-1",
            "remarks": f"{TAG_CAUSE} decision.",
        })
        assert decision.status_code == 201, decision.text
        decision = decision.json()
        assert client.get(f"/api/optimization/plans/{plan['id']}").json()["status"] == "PROPOSED"
        assert client.post("/api/optimization/decisions", json={
            "block_plan_id": 999999, "decision": "APPROVED"}).status_code == 404
        assert client.post("/api/optimization/decisions", json={
            "block_plan_id": plan["id"], "decision": "MAYBE"}).status_code == 422
        print("  decision recorded; plan status unchanged; 404/422: OK")

        log("EXECUTION OUTCOME (record only, never invented)")
        outcome = client.post("/api/optimization/execution-outcomes", json={
            "block_plan_id": plan["id"],
            "block_plan_task_id": pt_a["id"],
            "execution_status": "COMPLETED",
            "actual_start": "2026-05-11T10:00:00",
            "actual_end": "2026-05-11T10:35:00",
            "actual_duration_minutes": 35,
            "outcome_code": "DONE",
        })
        assert outcome.status_code == 201, outcome.text
        outcome = outcome.json()
        assert client.post("/api/optimization/execution-outcomes", json={
            "block_plan_id": plan["id"],
            "execution_status": "COMPLETED",
            "actual_start": "2026-05-11T12:00:00",
            "actual_end": "2026-05-11T10:00:00"}).status_code == 422
        assert client.post("/api/optimization/execution-outcomes", json={
            "block_plan_id": 999999, "execution_status": "NOT_STARTED"}).status_code == 404
        listed = client.get(
            f"/api/optimization/execution-outcomes?block_plan_id={plan['id']}").json()
        assert len(listed) == 1 and listed[0]["id"] == outcome["id"]
        print("  outcome recorded + retrieved; 422/404: OK")

        log("MANUAL PLAN VALIDATION RECORD (POST /validations)")
        v = client.post("/api/optimization/validations", json={
            "block_plan_id": plan["id"],
            "validation_type": "GENERAL",
            "validation_status": "PASSED",
            "validation_message": "Manual reviewer note.",
            "validator_version": "MANUAL-1.0",
        })
        assert v.status_code == 201, v.text
        print("  manual validation record stored: OK")

        log("PROVENANCE (optimization records back to source systems)")
        rows = q("""
            SELECT oi.optimization_run_id, cbw.id AS cbw_id, pt.id AS pt_id,
                   mr.id AS mr_id, df.source_record_type, df.source_record_id
            FROM optimization_input oi
            JOIN candidate_block_window cbw
              ON cbw.id = oi.candidate_block_window_id
            JOIN planning_task pt ON pt.id = cbw.planning_task_id
            JOIN maintenance_requirement mr ON mr.id = pt.maintenance_requirement_id
            JOIN defect_failure df ON df.id = mr.defect_failure_id
            WHERE oi.optimization_run_id = :rid
        """, {"rid": run["id"]})
        print("  ", [dict(zip(r._mapping.keys(), r)) for r in rows])
        assert len(rows) == 1
        assert rows[0]._mapping["source_record_type"] == "TMS_DEFECT"
        bpm = q("""
            SELECT b.plan_code, bt.planning_task_id, bt.candidate_block_window_id,
                   pv.validation_type, cd.decision, eo.execution_status
            FROM block_plan b
            JOIN block_plan_task bt ON bt.block_plan_id = b.id
            LEFT JOIN plan_validation pv ON pv.block_plan_id = b.id
            LEFT JOIN controller_decision cd ON cd.block_plan_id = b.id
            LEFT JOIN execution_outcome eo ON eo.block_plan_id = b.id
            WHERE b.plan_code = :code ORDER BY bt.id
        """, {"code": plan["plan_code"]})
        for r in bpm:
            print("  ", dict(zip(r._mapping.keys(), [str(x) for x in r])))
        assert len(bpm) >= 2

        log("SOURCE / UNIFIED / PLANNING / CANDIDATE UNCHANGED BY STEP 10 WRITES")
        integrity_tables = ("tms_inspection", "tms_defect", "tms_maintenance",
                      "defect_failure", "maintenance_requirement", "block_requirement",
                      "available_window", "candidate_block_window")
        for t in integrity_tables + tuple(PLANNING_TABLES):
            print(f"  {t}: {q(f'SELECT count(*) FROM {t}')[0][0]}")
        assert q("SELECT count(*) FROM planning_task")[0][0] == 2
        assert q("SELECT count(*) FROM candidate_block_window")[0][0] == 8

        log("HTTP CONTRACT SUMMARY")
        bad_enums = [("runs", {"run_type": "NOT_A_TYPE", "status": "REQUESTED"}),
                     ("plans", {"plan_date": "2026-05-11", "status": "NOPE",
                                "planning_horizon_start": "2026-05-11T09:00:00",
                                "planning_horizon_end": "2026-05-11T16:00:00"})]
        for prefix, payload in bad_enums:
            r = client.post(f"/api/optimization/{prefix}", json=payload)
            assert r.status_code == 422, (prefix, r.text)
        print("  invalid enums -> 422: OK")
        print("ALL CHECKS PASSED")

    finally:
        with SessionLocal() as db:
            log("CLEANUP (FK-safe order)")
            run_ids_sql = (
                "SELECT id FROM optimization_run WHERE run_code LIKE 'RUN-"
                + TAG + "%'"
            )
            plan_ids_sql = (
                "SELECT id FROM block_plan WHERE plan_code LIKE 'PLAN-"
                + TAG + "%'"
            )
            print("  deleting execution_outcome rows...")
            db.execute(text(
                "DELETE FROM execution_outcome WHERE block_plan_id IN (" + plan_ids_sql + ")"))
            print("  deleting controller_decision rows...")
            db.execute(text(
                "DELETE FROM controller_decision WHERE block_plan_id IN (" + plan_ids_sql + ")"))
            print("  deleting plan_validation rows...")
            db.execute(text(
                "DELETE FROM plan_validation WHERE block_plan_id IN (" + plan_ids_sql + ")"))
            print("  deleting block_plan_task rows...")
            db.execute(text(
                "DELETE FROM block_plan_task WHERE block_plan_id IN (" + plan_ids_sql + ")"))
            print("  deleting block_plan rows...")
            db.execute(text(f"DELETE FROM block_plan WHERE plan_code LIKE 'PLAN-{TAG}%'"))
            print("  deleting optimization_output rows...")
            db.execute(text(
                "DELETE FROM optimization_output WHERE optimization_run_id IN ("
                + run_ids_sql + ")"))
            print("  deleting optimization_input rows...")
            db.execute(text(
                "DELETE FROM optimization_input WHERE optimization_run_id IN ("
                + run_ids_sql + ")"))
            print("  deleting optimization_run rows...")
            db.execute(text(f"DELETE FROM optimization_run WHERE run_code LIKE 'RUN-{TAG}%'"))

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
            db.execute(text("DELETE FROM planning_resource WHERE resource_code LIKE :tag"),
                       {"tag": f"{TAG}-%"})
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
            for t in STEP10_TABLES + PLANNING_TABLES + [
                "candidate_block_window", "available_window", "defect_failure",
                "maintenance_requirement", "block_requirement", "asset_master", "train",
            ]:
                count = db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                print(f"  {t}: {count}")
                assert count == 0, f"{t} not clean ({count})"
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