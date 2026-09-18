r"""STEP 11 CLI: generate/verify/cleanup synthetic railway datasets.

Usage
-----
.. code:: powershell

    .\venv\Scripts\python.exe scripts\generate_synthetic_data.py ^
        --seed 42 --scale small --days 30 --scenario normal --verify

Dry-run for large volumes (never touches the database):

    .\venv\Scripts\python.exe scripts\generate_synthetic_data.py ^
        --scale large --dry-run

Cleanup-only (no regeneration):

    .\venv\Scripts\python.exe scripts\generate_synthetic_data.py --cleanup

Exit codes: 0 = success, 1 = failure (verification problems / LARGE not
dry-run / unexpected Alembic head / DB connectivity error).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.synthetic_data import (
    SCALE_PROFILES,
    VALID_SCENARIOS,
    cleanup_synthetic,
    run_pipeline,
    verify_synthetic,
)
from app.services.synthetic_data.config import (
    EXPECTED_ALEMBIC_HEAD,
    GENERATOR_VERSION,
    MARKER,
    SyntheticConfig,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_DIR = BACKEND_DIR / "alembic"


def check_alembic_head(script_location: Optional[Path] = None) -> None:
    """Fail fast when the migrations are not on the expected head."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(script_location or ALEMBIC_DIR))
    script = ScriptDirectory.from_config(cfg)
    heads = sorted(script.get_heads())
    if heads != [EXPECTED_ALEMBIC_HEAD]:
        print(
            f"[STEP 11] FATAL: expected Alembic head '{EXPECTED_ALEMBIC_HEAD}' "
            f"but found {heads}. Run migrations or downgrade; the generator "
            "will never auto-migrate."
        )
        sys.exit(1)


def estimate(config: SyntheticConfig) -> dict:
    """Pure volume estimate used by --dry-run (no DB reads)."""
    combos = config.station_count * config.profile.lines_per_station
    template = config.window_template()
    gaps_per_day = max(0, len(template) - 1)
    windows = combos * config.days * gaps_per_day
    tasks = config.maintenance_count
    candidates = tasks * windows
    return {
        "combos": combos,
        "gaps_per_day_per_line": gaps_per_day,
        "estimated_windows": windows,
        "estimated_planning_tasks": tasks,
        "estimated_candidates": candidates,
    }


def export_csv_snapshot(db: Session, export_dir: Path) -> dict:
    """Best-effort CSV export of core pipeline tables (optional)."""
    import csv

    from app.models import (
        AvailableWindow,
        CandidateBlockWindow,
        PlanningTask,
        Train,
        TrainSchedule,
    )

    export_dir.mkdir(parents=True, exist_ok=True)
    rows_written: dict[str, int] = {}
    tables = {
        "train": Train,
        "train_schedule": TrainSchedule,
        "available_window": AvailableWindow,
        "planning_task": PlanningTask,
        "candidate_block_window": CandidateBlockWindow,
    }
    for name, model in tables.items():
        records = db.query(model).all()
        if not records:
            continue
        with (export_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([c.name for c in model.__table__.columns])
            for row in records:
                def fmt(value):
                    if value is None:
                        return ""
                    if isinstance(value, date):
                        return value.isoformat()
                    return value

                writer.writerow([fmt(getattr(row, c.name)) for c in model.__table__.columns])
        rows_written[name] = len(records)
    return rows_written


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_synthetic_data",
        description="STEP 11 synthetic railway dataset generator.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scale", choices=sorted(SCALE_PROFILES), default="small")
    parser.add_argument("--days", type=int, default=None, help="override profile days")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--scenario", choices=VALID_SCENARIOS, default="normal")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--db-url", default=None, help="SQLAlchemy URL override")
    parser.add_argument("--cleanup", action="store_true", help="remove synthetic rows first")
    parser.add_argument("--verify", action="store_true", help="verify after generating")
    parser.add_argument("--dry-run", action="store_true", help="estimate volumes only")
    parser.add_argument("--export-dir", default=None, help="optional CSV export folder")
    parser.add_argument("--with-optimization", action="store_true", help="record optimization placeholder run")
    args = parser.parse_args(argv)

    if args.scale == "large" and not args.dry_run:
        print("[STEP 11] FATAL: 'large' scale is dry-run only. Use --dry-run.")
        return 1

    # A plain `--cleanup` invocation must only clean up; generation is driven
    # by explicit generation-related flags.
    requested_generation = any(
        [
            args.days is not None,
            args.start_date is not None,
            args.scenario != "normal",
            args.batch_size != 1000,
            args.scale != "small",
            args.export_dir is not None,
            args.with_optimization,
            args.verify,
        ]
    )

    if args.dry_run:
        start_date = args.start_date or date.today()
        cfg = SyntheticConfig(
            seed=args.seed,
            scale=args.scale,
            days=args.days or SCALE_PROFILES[args.scale].days,
            start_date=start_date,
            scenario=args.scenario,
            batch_size=args.batch_size,
            write_manifest=False,
        )
        estimate_ = estimate(cfg)
        print(f"[STEP 11] DRY-RUN configuration ({GENERATOR_VERSION})")
        for key, value in cfg.configuration_summary().items():
            print(f"  {key}: {value}")
        for key, value in estimate_.items():
            print(f"  {key}: {value}")
        print("[STEP 11] DRY-RUN complete. No database changes were made.")
        return 0

    check_alembic_head()

    url = args.db_url or settings.database_url
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    start_date = args.start_date or date.today()
    cfg = SyntheticConfig(
        seed=args.seed,
        scale=args.scale,
        days=args.days or SCALE_PROFILES[args.scale].days,
        start_date=start_date,
        scenario=args.scenario,
        batch_size=args.batch_size,
        export_dir=Path(args.export_dir) if args.export_dir else None,
        with_optimization=args.with_optimization,
        write_manifest=True,
    )

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[STEP 11] FATAL: database connectivity error: {exc}")
        return 1

    try:
        if args.cleanup:
            t0 = time.monotonic()
            summary = cleanup_synthetic(db)
            print(f"[STEP 11] Cleanup removed {summary.get('total', 0)} rows "
                  f"in {time.monotonic() - t0:.2f}s.")

        if not requested_generation:
            print("[STEP 11] Cleanup-only invocation; no generation requested.")
            return 0

        t0 = time.monotonic()
        manifest = run_pipeline(db, cfg)
        elapsed = time.monotonic() - t0

        print(f"[STEP 11] Generated '{manifest['dataset_id']}' in {elapsed:.2f}s.")
        for name, count in sorted(manifest["table_counts"].items()):
            if count:
                print(f"  {name}: {count}")

        if cfg.export_dir is not None:
            exported = export_csv_snapshot(db, cfg.export_dir)
            print(f"[STEP 11] Exported {exported} to {cfg.export_dir}")

        if args.verify:
            verification = verify_synthetic(db, cfg)
            print("[STEP 11] Verification:", "PASS" if verification["pass"] else "FAIL")
            for problem in verification["problems"]:
                print(f"  PROBLEM: {problem}")
            for note in verification["info"][:12]:
                print(f"  info: {note}")
            print(f"  counts: {verification['counts']}")
            if not verification["pass"]:
                return 1

        print(f"[STEP 11] Done. Marker: {MARKER}. Manifest: "
              f"{cfg.manifest_path}")
        return 0
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())