import json

from sqlalchemy import create_engine, inspect, text

from app.models.train import Train
from app.services.available_window_derivation import derive_available_windows
from app.core.database import SessionLocal

ENG = create_engine("postgresql+psycopg2://postgres:root@localhost:5432/sih_26027")

TAG = "VERIFY-COA-TRN-REPORT-1"


def main():
    insp = inspect(ENG)

    print("=== CURRENT DATABASE ===")
    with ENG.connect() as c:
        print("current_database:", c.execute(text("SELECT current_database()")).scalar())
        print("alembic_version:", [list(r) for r in c.execute(text("SELECT version_num FROM alembic_version"))])
        print("source_systems:", [r[0] for r in c.execute(text("SELECT system_code FROM source_system ORDER BY id"))])

    db = SessionLocal()
    try:
        coa_id = db.execute(text("SELECT id FROM source_system WHERE system_code='COA'")).scalar()

        train = Train(
            train_id=TAG,
            train_number="99999",
            train_name="SYNTHETIC COA verify train",
            schedule_date=None,
            start_date=None,
            loco_number="LOCO-VERIFY",
            direction="DOWN",
            source_system_id=coa_id,
        )
        db.add(train)
        db.flush()
        from app.models.train_movement import TrainMovement
        from app.models.train_schedule import TrainSchedule
        from app.models.line_occupancy import LineOccupancy
        from app.models.operational_event import OperationalEvent
        from datetime import datetime

        dt = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")

        db.add_all([
            TrainMovement(train_id=train.id, station_code="STA-1", movement_flag="A",
                          movement_datetime=dt("2026-03-01T10:05:00"), line_number="L1",
                          source_event_id="SRC-MOV-1"),
            TrainSchedule(train_id=train.id, station_code="STA-2", scheduled_arrival=dt("2026-03-01T10:00:00"),
                          scheduled_departure=dt("2026-03-01T10:30:00"), sequence_number=1, line_number="L2",
                          source_schedule_id="SRC-SCH-1"),
            TrainSchedule(train_id=train.id, station_code="STA-2", scheduled_arrival=dt("2026-03-01T10:50:00"),
                          scheduled_departure=dt("2026-03-01T11:20:00"), sequence_number=2, line_number="L2",
                          source_schedule_id="SRC-SCH-2"),
            LineOccupancy(station_code="STA-1", line_number="L1", occupancy_start=dt("2026-03-01T10:00:00"),
                          occupancy_end=dt("2026-03-01T10:20:00"), occupancy_status="OCCUPIED",
                          train_id=train.id, source_event_id="SRC-OCC-1"),
            LineOccupancy(station_code="STA-1", line_number="L1", occupancy_start=dt("2026-03-01T10:40:00"),
                          occupancy_end=dt("2026-03-01T11:00:00"), occupancy_status="OCCUPIED",
                          train_id=train.id, source_event_id="SRC-OCC-2"),
            OperationalEvent(train_id=train.id, station_code="STA-1", event_type="CAUTION",
                             event_datetime=dt("2026-03-01T10:10:00"), source_event_id="SRC-EVT-1"),
        ])
        db.commit()

        print("\n=== SOURCE COUNTS BEFORE DERIVATION ===")
        for t in ("train", "train_movement", "train_schedule", "line_occupancy", "operational_event"):
            print(f"  {t}: {db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")

        from app.models.available_window import AvailableWindow
        print("\n=== DERIVATION ===")
        windows = derive_available_windows(db)
        for w in windows:
            print(
                f"  window id={w.id} {w.station_code}/{w.line_number} "
                f"{w.window_start}->{w.window_end} dur={w.duration_minutes} status={w.window_status} "
                f"source_occupancy_id={w.source_occupancy_id} calc={w.calculation_source}"
            )

        print("\n=== TRACEABILITY JOIN: window -> occupancy -> train -> source_system ===")
        rows = db.execute(text("""
            SELECT aw.id, aw.station_code, aw.line_number, aw.window_start, aw.window_end,
                   aw.duration_minutes, aw.window_status, aw.source_occupancy_id,
                   am.id AS source_occ, tt.id AS train_id, tt.train_id AS source_train_id, ss.system_code
            FROM available_window aw
            LEFT JOIN line_occupancy am ON am.id = aw.source_occupancy_id
            LEFT JOIN train tt ON tt.id = am.train_id
            LEFT JOIN source_system ss ON ss.id = tt.source_system_id
            ORDER BY aw.station_code
        """)).fetchall()
        for r in rows:
            print("  ", dict(zip(r._mapping.keys(), [str(x) if x is not None else None for x in r])))

        print("\n=== TRAIN CHILD RELATIONSHIP COUNTS ===")
        for t in ("train_movement", "train_schedule", "line_occupancy", "operational_event"):
            n = db.execute(text(f"SELECT count(*) FROM {t} WHERE train_id = :id"), {"id": train.id}).scalar()
            print(f"  train#{train.id} -> {t}: {n}")

        print("\n=== CLEANUP ===")
        db.execute(text("DELETE FROM available_window"))
        db.execute(text("DELETE FROM line_occupancy WHERE train_id = :id"), {"id": train.id})
        db.execute(text("DELETE FROM operational_event WHERE train_id = :id"), {"id": train.id})
        db.execute(text("DELETE FROM train_schedule WHERE train_id = :id"), {"id": train.id})
        db.execute(text("DELETE FROM train_movement WHERE train_id = :id"), {"id": train.id})
        db.execute(text("DELETE FROM train WHERE id = :id"), {"id": train.id})
        db.commit()
        for t in ("available_window", "train", "train_movement", "train_schedule", "line_occupancy", "operational_event"):
            print(f"  {t}: {db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")
    finally:
        db.close()

    print("\n=== COA TABLE STRUCTURE (live introspection) ===")
    for t in ("train", "train_movement", "train_schedule", "line_occupancy", "operational_event", "available_window"):
        print(f"\n--- {t} ---")
        print("PK:", json.dumps(insp.get_pk_constraint(t)))
        print("COLUMNS:", json.dumps([
            {"name": c["name"], "type": str(c["type"]), "nullable": c["nullable"]} for c in insp.get_columns(t)
        ]))
        print("INDEXES:", json.dumps([
            (ix["name"], ix["column_names"], ix["unique"]) for ix in insp.get_indexes(t)
        ]))
        print("UNIQUE_CONSTRAINTS:", json.dumps([
            (uc["name"], uc["column_names"]) for uc in insp.get_unique_constraints(t)
        ]))
        print("FKs:", json.dumps([
            (fk["name"], fk["constrained_columns"], fk["referred_table"], fk["referred_columns"], fk["options"])
            for fk in insp.get_foreign_keys(t)
        ]))

    print("\n=== FORBIDDEN COLUMN CHECK (excl. allowed available_window) ===")
    forbidden = [
        "priority_score", "risk_score", "predicted_failure", "recommended_block",
        "optimization_score", "candidate_block", "optimization_run", "optimization_input",
        "optimization_output", "planned_block", "controller_decision", "planning_task",
        "planning_constraint", "candidate_block_window", "validation_result", "execution_outcome",
    ]
    issues = []
    for t in ("train", "train_movement", "train_schedule", "line_occupancy", "operational_event", "available_window"):
        cols = {c["name"] for c in insp.get_columns(t)}
        hit = cols & set(forbidden)
        if hit:
            issues.append((t, sorted(hit)))
    print("ISSUES:", json.dumps(issues) if issues else "NONE")


if __name__ == "__main__":
    main()