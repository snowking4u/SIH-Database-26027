# SIH 26027 Backend — Railway Maintenance & Planning

Backend for the **SIH 2026 (Smart India Hackathon) railway maintenance & planning** project. It manages train / track / signal maintenance data end-to-end:

**Source systems → Unified defect & requirement layer → Planning foundation → Candidate block windows → Plan validation**

plus a **deterministic synthetic data generator** for research and testing.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Directory Layout](#directory-layout)
- [Database Design (36 tables)](#database-design-36-tables)
- [Core Services](#core-services)
- [API (12 routers)](#api-12-routers)
- [Core Plumbing](#core-plumbing)
- [STEP 11 — Deterministic Synthetic Data Generator](#step-11--deterministic-synthetic-data-generator)
- [Tests (215, all passing)](#tests-215-all-passing)
- [How to Run](#how-to-run)
- [Design Principles](#design-principles)
- [Project Status](#project-status)

---

## Tech Stack

| Piece       | Technology                                             |
|-------------|--------------------------------------------------------|
| API         | FastAPI (title "SIH 26027 API")                        |
| ORM         | SQLAlchemy 2.0 (DeclarativeBase, typed `Mapped` columns) |
| Database    | PostgreSQL 18.4 (live: `sih_26027`), SQLite in-memory for tests |
| Migrations  | Alembic (current head: `d2e6b9c4f1a7`)                 |
| Validation  | Pydantic v2 (`pydantic-settings` for config)           |
| Driver      | `psycopg2-binary`                                      |
| Server      | Uvicorn                                                |
| Tests       | pytest + FastAPI `TestClient` + httpx                  |

`requirements.txt`: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `alembic`, `pydantic-settings`, `python-dotenv`, `pytest`, `httpx`.

---

## Directory Layout

```
backend/
├── .env                       # DATABASE_URL (psycopg2 → PostgreSQL)
├── alembic/                   # env.py + 9 version scripts (one per step/feature)
├── alembic.ini
├── app/
│   ├── main.py                # FastAPI app, 12 routers, /, /health, /health/db
│   ├── core/
│   │   ├── config.py          # pydantic Settings (DATABASE_URL from .env)
│   │   └── database.py        # Base, engine, SessionLocal, get_db dependency
│   ├── models/                # 36 SQLAlchemy models
│   ├── schemas/               # ~34 Pydantic request/response schemas
│   ├── routers/               # 12 API routers
│   └── services/              # Business logic + synthetic_data package
├── scripts/
│   ├── seed_master_data.py          # seeds TMS/TDMS/SMMS/COA source systems
│   └── generate_synthetic_data.py   # STEP 11 CLI (synthetic data generator)
├── tests/                     # 12 test modules, 215 tests
├── verify_step6/7/8/9/10.py   # per-step live verification scripts
└── README.md
```

---

## Database Design (36 tables)

### STEP 4 — Master data
`source_system` · `location_master` · `asset_master` · `asset_parameter`

### STEP 5 — Source data (TMS / TDMS / SMMS)
- **TMS** (track-side): `tms_inspection`, `tms_defect`, `tms_maintenance`
- **TDMS** (track/estimating): `tdms_inspection`, `tdms_failure`, `tdms_maintenance`
- **SMMS** (structure): `smms_inspection`, `smms_alert`, `smms_maintenance`

### STEP 6 — COA/CTC + availability
`train` · `train_schedule` · `train_movement` · `line_occupancy` · `operational_event` · `available_window`

### STEP 7 — Unified layer
`defect_failure` · `maintenance_requirement` · `block_requirement`

### STEP 8 — Planning foundation
`planning_task` · `planning_constraint` · `planning_resource` · `task_resource` · `task_dependency`

### STEP 9 — Candidate block windows
`candidate_block_window`

### STEP 10 — Optimization foundation
`optimization_run` · `optimization_input` · `optimization_output` · `block_plan` · `block_plan_task` · `plan_validation` · `controller_decision` · `execution_outcome`

---

## Core Services

### `unified_maintenance.py` (STEP 7)
Deterministic normalization of TMS/TDMS/SMMS rows into the unified layer:
- TMS defects / TDMS failures / SMMS alerts → `defect_failure`
- TMS/TDMS/SMMS maintenance → `maintenance_requirement`
- Idempotent **upsert-or-skip** backed by a `UNIQUE(source_system_id, source_record_type, source_record_id)`; provenance is kept on every unified row.
- `required_duration_minutes` is only derived when both `start_date` / `end_date` exist; `status` falls back to `UNKNOWN`; SMMS cause/feedback codes are preserved in `remarks`.

### `available_window_derivation.py` (STEP 6)
Pure deterministic gap-derivation: collects conflicting occupancy + scheduled-stop intervals per (station, line), merges overlaps, and emits `AVAILABLE` windows in the gaps. Never invents availability; regenerating replaces only the `available_window` table.

### `planning_foundation.py` (STEP 8)
- `generate_planning_tasks` → one `planning_task` per requirement, only when a known duration exists (never invents durations).
- `generate_planning_constraints` → DURATION / TIME_WINDOW / LOCATION / LINE / POWER_BLOCK / TRAFFIC_BLOCK constraints from each block requirement (hard constraints, upsert-or-skip).

### `candidate_window.py` (STEP 9)
Exhaustive deterministic evaluation of every (planning task, available window) pair → `candidate_block_window` with explicit `FEASIBLE` / `INFEASIBLE` / `REQUIRES_REVIEW` status and reason codes (duration, location, line, power/traffic confirmation, missing context). No ranking or selection.

### `plan_validation.py` (STEP 10)
Deterministic block-plan validation producing `PASSED` / `FAILED` / `WARNING` results: duration, window-fit, location/line match, time conflicts, dependencies, resources, power/traffic confirmation warnings. **Never optimizes, approves, or changes plan status** — only a human `controller_decision` can approve a plan.

---

## API (12 routers)

All under `/api/...`:

| Router          | Purpose                                                        |
|-----------------|----------------------------------------------------------------|
| `source_systems`| create/list source systems (TMS, TDMS, SMMS, COA)              |
| `locations`     | location master CRUD                                           |
| `assets`        | asset master CRUD                                              |
| `tms`           | TMS inspections / defects / maintenance                        |
| `tdms`          | TDMS inspections / failures / maintenance                      |
| `smms`          | SMMS inspections / alerts / maintenance                        |
| `coa`           | trains, schedules, movements, occupancy, events                |
| `unified`       | `POST /api/unified/normalize/{tms\|tdms\|smms}` + maintenance & block-requirement endpoints |
| `planning`      | `POST /api/planning/generate-tasks`, tasks, constraints, resources, task-resources, dependencies |
| `candidates`    | `POST /api/candidates/generate`, `GET /api/candidates/windows` |
| `optimization`  | runs, inputs, outputs, plans, plan-tasks, validations, decisions, execution-outcomes |
| health          | `GET /`, `GET /health`, `GET /health/db`                       |

---

## Core Plumbing

- **`app/core/config.py`** — `Settings` with `DATABASE_URL` (from `.env`, `extra="ignore"`), cached via `lru_cache`.
- **`app/core/database.py`** — `Base` (DeclarativeBase), single engine with `pool_pre_ping=True`, `SessionLocal`, and the FastAPI `get_db` dependency.
- **Schemas (`app/schemas/`)** — one Pydantic model set per table (Create/Read response shapes) enforcing validation (dates, durations > 0, status enums) and returning 422 for bad input.

---

## STEP 11 — Deterministic Synthetic Data Generator

`app/services/synthetic_data/` (18 files) + CLI `scripts/generate_synthetic_data.py`.

### Pipeline

```
master data → COA source → available windows → TMS/TDMS/SMMS sources
→ unified normalization → block requirements → planning foundation
→ resources & dependencies → candidate block windows
→ optional SYN-OPT- placeholder run (inputs only, no outputs)
```

### Key properties

- **Deterministic & idempotent**: per-stage salted RNG (`module_rng(0x1..0x7)`); re-running never duplicates data (verified: re-runs create **0 new rows**).
- **Safe by design**: all rows carry `SYNTHETIC_STEP11` / `SYN-*` ids; `--cleanup` removes only synthetic rows and preserves the seeded source systems; `--dry-run` always safe; **LARGE scale is dry-run only**; Alembic-head guard before generating; never changes schema; no AI scoring / selection / ranking.
- **Manifest**: `synthetic_dataset_manifest.json` written after each run (dataset id `SYN-STEP11-{date}-0001`, table-count snapshot, config summary).

### Scales & Scenarios

| Scale  | Description |
|--------|-------------|
| tiny   | minimal dataset for fast tests |
| small  | small but realistic dataset |
| medium | medium volume dataset |
| large  | full-scale dataset (dry-run only) |

9 scenarios: `normal`, `high_defect_load`, `multi_department`, `window_shortage`, `resource_shortage`, `dependency_conflict`, `power_block_required`, `traffic_block_required`, `mixed`.

### CLI examples

```powershell
# generate a small dataset, seed 42, 30 days, normal scenario, verify + manifest
.\venv\Scripts\python scripts\generate_synthetic_data.py `
  --seed 42 --scale small --days 30 --scenario normal --verify

# plan-only (estimate) for large scale without touching the DB
.\venv\Scripts\python scripts\generate_synthetic_data.py --scale large --dry-run

# remove all synthetic data (keeps seeded source systems)
.\venv\Scripts\python scripts\generate_synthetic_data.py --cleanup
```

> **Note:** Postgres sequences are not reset between runs, so same-seed datasets are byte-identical only on a fresh database with matched sequences.

---

## Tests (215, all passing)

Test modules: `test_master_data`, `test_tms`, `test_tdms`, `test_smms`, `test_coa`, `test_unified`, `test_planning_foundation`, `test_candidate_window`, `test_optimization_foundation`, `test_synthetic_data` (41), plus a shared `conftest.py` (SQLite in-memory, `StaticPool`, `PRAGMA foreign_keys=ON`, `db_session` / `client` fixtures).

### Guarantees covered by tests

- **No-AI contract** — forbidden tokens (`score`, `optimal`, `prediction`, `rank`, …) excluded from STEP 10 columns & functions.
- **No automatic approval** — validation never changes plan status.
- **Provenance** — traceability from source record → defect/failure → requirement → task → candidate → plan → outcome.
- **`ondelete=RESTRICT`** FK wiring on all optimization tables.
- **Determinism / idempotency / cleanup** of the synthetic generator.

`verify_step6/7/8/9/10.py` are standalone live-DB verification scripts that run against the live API (port 8011).

---

## How to Run

```powershell
# 1. Setup
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt

#    .env must contain:
#    DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/sih_26027

# 2. Migrate + seed
.\venv\Scripts\python -m alembic upgrade head          # current head: d2e6b9c4f1a7
.\venv\Scripts\python scripts\seed_master_data.py       # seeds TMS/TDMS/SMMS/COA

# 3. Run the API
.\venv\Scripts\python -m uvicorn app.main:app --reload --port 8011

# 4. Run tests
.\venv\Scripts\python -m pytest tests -q
```

---

## Design Principles

1. **No fabrications** — whole-dataset determinism; no AI/ML scoring, ranking, prediction, or approval anywhere.
2. **Provenance first** — every derived row traces back to a concrete source record.
3. **Idempotent** — re-running normalization/generation never duplicates data.
4. **Safe cleanups** — only explicitly-marked synthetic rows are ever deleted.
5. **Sandboxed** — the generator guards schema/DB/migration head and never auto-migrates.

---

## Project Status

| Step | Feature | Status |
|------|---------|--------|
| STEP 4  | Master data (sources, locations, assets) | ✅ Complete |
| STEP 5  | Source data (TMS / TDMS / SMMS) | ✅ Complete |
| STEP 6  | COA/CTC + available-window derivation | ✅ Complete |
| STEP 7  | Unified layer (defects, requirements, block requirements) | ✅ Complete |
| STEP 8  | Planning foundation (tasks, constraints, resources, deps) | ✅ Complete |
| STEP 9  | Candidate block windows | ✅ Complete |
| STEP 10 | Optimization foundation + plan validation (deterministic only) | ✅ Complete |
| STEP 11 | Deterministic synthetic data generator + CLI | ✅ Complete |

Current suite: **215 passed / 0 failed**.