# SIH 26027 — AI-Powered Automatic Block Planning for Indian Railways

> Smart Maintenance Block Planning, Asset Availability & Future AI
> Optimization

## 1. Project Overview

This project is developed for **Smart India Hackathon (SIH) Problem
Statement 26027**: **AI-Powered Automatic Block Planning to Maximize
Asset Availability for Train Operations on Indian Railways**.

The current implementation provides a structured foundation for
integrating railway maintenance and operational data, normalizing
maintenance requirements, deriving operationally available windows,
creating planning tasks and candidate block windows, and calculating
explainable deterministic criticality/priority. The future
AI/optimization layer will consume this foundation.

## 2. Core Architecture

``` text
TMS / TDMS / SMMS / COA-CTC
            |
            v
      Source Database
            |
            v
      Unified Maintenance
            |
            v
       Planning Layer
            |
            +--> Criticality & Priority
            |
            +--> Available Windows
            |
            v
     Candidate Block Windows
            |
            v
    Future AI / Optimizer
            |
            v
       Block Plan
            |
            v
       Validation
            |
            v
   Controller Decision
            |
            v
        Execution
            |
            v
   Execution Outcome
```

## 3. Technology Stack

| Layer          | Technology                     |
|----------------|--------------------------------|
| Backend        | Python                         |
| API            | FastAPI                        |
| ORM            | SQLAlchemy                     |
| Database       | PostgreSQL 18.4                |
| Migrations     | Alembic                        |
| Validation     | Pydantic                       |
| Testing        | Pytest                         |
| API Docs       | OpenAPI / Swagger UI           |
| Synthetic Data | Python deterministic generator |

## 4. Database Architecture

The database is organized into these logical layers:

``` text
MASTER
SOURCE
UNIFIED
PLANNING
PRIORITY
CANDIDATE
OPTIMIZATION / DECISION
INTEGRATION / LOGGING
```

### Master tables

#### `source_system`

Stores source-system identity. Current seeded systems include TMS, TDMS,
SMMS and COA.

#### `location_master`

Stores normalized railway location information.

#### `asset_master`

Central asset registry. Asset identity is unique per source using
`(source_system_id, source_asset_id)`.

#### `asset_parameter`

Stores asset parameters associated with an asset/source.

------------------------------------------------------------------------

## 5. TMS Source Layer

### `tms_inspection`

Stores track inspection information:

``` text
id, asset_id, inspection_date, inspection_type,
parameter_code, parameter_value, remarks
```

### `tms_defect`

Stores track defects:

``` text
id, asset_id, inspection_id, defect_code,
defect_description, severity, detected_date, status, remarks
```

### `tms_maintenance`

Stores source maintenance records:

``` text
id, asset_id, defect_id, maintenance_type,
planned_date, start_date, end_date, status, remarks
```

Traceability:

``` text
tms_maintenance -> tms_defect -> tms_inspection
                  -> asset_master -> source_system
```

------------------------------------------------------------------------

## 6. TDMS Source Layer

### `tdms_inspection`

``` text
id, asset_id, inspection_date, inspection_type,
parameter_code, parameter_value, remarks
```

### `tdms_failure`

``` text
id, asset_id, inspection_id, failure_code,
failure_description, severity, failure_date,
status, rectification_date, remarks
```

### `tdms_maintenance`

``` text
id, asset_id, failure_id, maintenance_type,
planned_date, start_date, end_date, status, remarks
```

Traceability:

``` text
tdms_maintenance -> tdms_failure -> tdms_inspection
                   -> asset_master -> source_system
```

------------------------------------------------------------------------

## 7. SMMS Source Layer

### `smms_inspection`

``` text
id, asset_id, inspection_date, inspection_type,
parameter_code, parameter_value, remarks
```

### `smms_alert`

Contains normalized alert/feedback information including:

``` text
alert_type_code
alert_feedback_code
alert_status_code
cause_code
incidence_date_time
rectification_date_time
incidence_duration
alert_feedback_date_time
remarks
maintainer_name
maintainer_designation
maintainer_mobile
```

`incidence_duration` is represented as a PostgreSQL interval.

### `smms_maintenance`

``` text
id, asset_id, alert_id, maintenance_type,
planned_date, start_date, end_date, status, remarks
```

------------------------------------------------------------------------

## 8. COA / CTC Operational Layer

### `train`

Stores:

``` text
train_id
train_number
train_name
schedule_date
start_date
loco_number
direction
source_system_id
```

### `train_movement`

Stores station-level train movement events:

``` text
train_id
station_code
movement_flag
movement_datetime
line_number
source_event_id
remarks
```

### `train_schedule`

Stores:

``` text
train_id
station_code
scheduled_arrival
scheduled_departure
scheduled_run_through
sequence_number
line_number
source_schedule_id
remarks
```

### `line_occupancy`

Stores operational occupancy intervals:

``` text
station_code
line_number
occupancy_start
occupancy_end
occupancy_status
train_id
source_event_id
remarks
```

Correct API endpoint:

``` text
GET /api/coa/line-occupancy
```

### `operational_event`

Stores operational events:

``` text
train_id
station_code
event_type
event_datetime
description
source_event_id
remarks
```

------------------------------------------------------------------------

## 9. Derived `available_window`

`available_window` is a **derived operational table**. It is not raw COA
data and is not an AI prediction.

Important fields:

``` text
station_code
line_number
window_start
window_end
duration_minutes
window_status
calculation_source
generated_at
source_schedule_id
source_occupancy_id
remarks
```

Derivation:

``` text
Train schedules + line occupancy
             |
             v
     Merge conflict intervals
             |
             v
       Find positive gaps
             |
             v
       AVAILABLE WINDOWS
```

Example:

``` text
10:00 - 10:20  OCCUPIED
10:20 - 10:40  AVAILABLE
10:40 - 11:00  OCCUPIED
```

------------------------------------------------------------------------

## 10. Unified Maintenance Layer

### `defect_failure`

Common representation of source defects/failures:

``` text
asset_id
source_system_id
source_record_type
source_record_id
defect_code
defect_description
severity
detected_at
status
rectified_at
remarks
```

### `maintenance_requirement`

Common maintenance representation:

``` text
asset_id
source_system_id
source_record_type
source_record_id
defect_failure_id
maintenance_type
description
required_duration_minutes
planned_date
status
remarks
```

### `block_requirement`

Connects maintenance work to operational block requirements:

``` text
maintenance_requirement_id
station_code
line_number
block_type
required_duration_minutes
earliest_start
latest_end
power_block_required
traffic_block_required
resource_notes
status
remarks
```

------------------------------------------------------------------------

## 11. Planning Layer

### `planning_task`

Planning unit consumed by later feasibility/optimization stages.

Important fields:

``` text
maintenance_requirement_id
block_requirement_id
asset_id
task_code
task_type
description
status
earliest_start
latest_end
duration_minutes
location_code
```

### `planning_constraint`

Represents planning rules:

``` text
DURATION
TIME_WINDOW
LOCATION
LINE
POWER_BLOCK
TRAFFIC_BLOCK
```

Fields include constraint type/value, hard/soft status, effective
period, description and source.

### `planning_resource`

Represents planning resources:

``` text
resource_code
resource_type
resource_name
description
capacity
unit
status
location_code
source_system_id
```

### `task_resource`

Connects tasks to resources:

``` text
planning_task_id
planning_resource_id
required_quantity
allocation_status
remarks
```

### `task_dependency`

Represents relationships between tasks:

``` text
predecessor_task_id
successor_task_id
dependency_type
lag_minutes
description
```

Self-dependencies are prevented.

------------------------------------------------------------------------

## 12. Criticality & Priority

The Step 12 layer adds a dedicated `planning_priority` table.

Relationship:

``` text
planning_task
      |
      v
planning_priority
```

Important fields:

``` text
planning_task_id
criticality_level
urgency_level
safety_impact
asset_availability_impact
traffic_impact
failure_recurrence
defect_age_days
priority_score
priority_band
calculation_version
calculated_at
calculation_reason
```

Current calculation version:

``` text
STEP12-DETERMINISTIC-1.0
```

### Baseline score

``` text
priority_score =
    0.20 * criticality
  + 0.15 * urgency
  + 0.25 * safety impact
  + 0.20 * asset availability impact
  + 0.10 * traffic impact
  + 0.05 * recurrence
  + 0.05 * defect age
```

Score range:

``` text
0 - 100
```

Bands:

``` text
0–24.99     LOW
25–49.99    MEDIUM
50–74.99    HIGH
75–100      CRITICAL
```

**Important:** this is a project baseline deterministic scoring model,
not an official Indian Railways scoring formula.

The score is explainable because the individual factors are stored.

### Priority APIs

``` text
GET  /api/planning/priority
GET  /api/planning/priority/{priority_id}
GET  /api/planning/tasks/{task_id}/priority

POST /api/planning/tasks/{task_id}/priority/recalculate
POST /api/planning/priority/recalculate
```

Example:

``` bash
curl -X POST http://127.0.0.1:8011/api/planning/priority/recalculate
```

------------------------------------------------------------------------

## 13. Candidate Block Windows

### `candidate_block_window`

Connects planning tasks to operationally available windows.

Important fields:

``` text
planning_task_id
block_requirement_id
available_window_id
candidate_start
candidate_end
candidate_duration_minutes
feasible
feasibility_status
feasibility_reason
```

Deterministic feasibility considers factors such as:

- Required duration
- Task time bounds
- Location
- Line
- Power-block requirement
- Traffic-block requirement
- Available window compatibility

Where authoritative operational confirmation is missing, a candidate can
require review rather than being treated as automatically confirmed.

API:

``` text
GET /api/candidates/windows
```

------------------------------------------------------------------------

## 14. Optimization / Block Plan Foundation

The database contains storage for the future optimization and decision
workflow:

``` text
optimization_run
optimization_input
optimization_output
block_plan
block_plan_task
plan_validation
controller_decision
execution_outcome
```

Current implementation stores the foundation. It does not yet claim to
perform final AI-based optimization.

Plan validation endpoint:

``` text
POST /api/optimization/plans/{id}/validate
```

------------------------------------------------------------------------

## 15. End-to-End Working

``` text
TMS / TDMS / SMMS / COA
          |
          v
      Source Data
          |
          v
 Unified Maintenance
          |
          v
Maintenance Requirement
          |
          v
   Block Requirement
          |
          v
     Planning Task
          |
    +-----+-----+
    |           |
    v           v
 Priority   Constraints
    |           |
    +-----+-----+
          |
          v
 Available COA Windows
          |
          v
 Candidate Block Windows
          |
          v
 Future AI / Optimizer
          |
          v
      Block Plan
          |
          v
       Validation
          |
          v
 Controller Decision
          |
          v
       Execution
          |
          v
 Execution Outcome
```

------------------------------------------------------------------------

## 16. Synthetic Data Generator

Location:

``` text
backend/scripts/generate_synthetic_data.py
```

Example:

``` bash
python scripts/generate_synthetic_data.py   --seed 42   --scale tiny   --days 7   --scenario normal
```

Verification:

``` bash
python scripts/generate_synthetic_data.py   --seed 42   --scale tiny   --days 7   --scenario normal   --verify
```

Pipeline:

``` text
Master data
  -> COA/CTC source data
  -> Available windows
  -> TMS/TDMS/SMMS source data
  -> Unified normalization
  -> Block requirements
  -> Planning tasks
  -> Constraints
  -> Resources
  -> Dependencies
  -> Candidate windows
```

Synthetic identifiers are clearly marked, for example:

``` text
SYNTHETIC_STEP11
SYN-ASSET
SYN-TRAIN
SYN-COA
SYN-RES
```

Synthetic data is for development/testing/demo only.

------------------------------------------------------------------------

## 17. API / Swagger

Start the backend from the `backend` directory:

``` bash
uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
```

Base URL:

``` text
http://127.0.0.1:8011
```

Swagger:

``` text
http://127.0.0.1:8011/docs
```

OpenAPI:

``` text
http://127.0.0.1:8011/openapi.json
```

### Main endpoints

#### COA

``` text
GET  /api/coa/trains
GET  /api/coa/schedules
GET  /api/coa/movements
GET  /api/coa/line-occupancy
GET  /api/coa/events
GET  /api/coa/available-windows
POST /api/coa/available-windows/generate
```

#### Planning

``` text
GET /api/planning/constraints
GET /api/planning/resources
GET /api/planning/dependencies
```

#### Priority

``` text
GET  /api/planning/priority
GET  /api/planning/priority/{priority_id}
GET  /api/planning/tasks/{task_id}/priority
POST /api/planning/tasks/{task_id}/priority/recalculate
POST /api/planning/priority/recalculate
```

#### Candidates

``` text
GET /api/candidates/windows
```

#### Validation

``` text
POST /api/optimization/plans/{id}/validate
```

------------------------------------------------------------------------

## 18. Database Migrations

Alembic is used for schema versioning.

Current Step 12 head:

``` text
e1a9c2f3b7d5
```

Check:

``` bash
alembic current
```

Upgrade:

``` bash
alembic upgrade head
```

------------------------------------------------------------------------

## 19. Testing

Run:

``` bash
pytest
```

Current verified project status after the Step 12 route-conflict fix:

``` text
257 passed
0 failed
```

Step 12 tests:

``` text
42 passed
```

Verified areas include:

- Models
- Foreign keys
- Constraints
- API endpoints
- Score calculation
- Priority-band boundaries
- Missing-data fallback
- Idempotency
- Provenance
- Source-data preservation
- Route regression

------------------------------------------------------------------------

## 20. Data Integrity & Traceability

The project preserves provenance from source records into the planning
layer.

Example:

``` text
TMS Defect
   |
   v
defect_failure
   |
   v
maintenance_requirement
   |
   v
block_requirement
   |
   v
planning_task
   |
   v
planning_priority
   |
   v
candidate_block_window
```

Major relationships use `ON DELETE RESTRICT` where appropriate to
prevent accidental deletion of referenced source/planning records.

Important uniqueness rules include:

``` text
asset_master:
(source_system_id, source_asset_id)

defect_failure:
(source_system_id, source_record_type, source_record_id)

maintenance_requirement:
(source_system_id, source_record_type, source_record_id)

planning_priority:
(planning_task_id)
```

------------------------------------------------------------------------

## 21. Idempotency

The system is designed to avoid duplicate derived records during
repeated processing.

Example priority recalculation:

``` text
First run:
processed = 31
created   = 31
updated   = 0

Second run:
processed = 31
created   = 0
updated   = 31
```

The exact numbers depend on the current dataset.

------------------------------------------------------------------------

## 22. Current Implementation Status

| Step   | Module                                     | Status   |
|--------|--------------------------------------------|----------|
| 1      | FastAPI + PostgreSQL + Alembic foundation  | Complete |
| 2      | Master data                                | Complete |
| 3      | TMS source layer                           | Complete |
| 4      | TDMS source layer                          | Complete |
| 5      | SMMS source layer                          | Complete |
| 6      | COA/CTC + available windows                | Complete |
| 7      | Unified maintenance layer                  | Complete |
| 8      | Planning/resource/constraint layer         | Complete |
| 9      | Candidate block-window feasibility         | Complete |
| 10     | Optimization/block-plan storage foundation | Complete |
| 11     | Synthetic data generator                   | Complete |
| 12     | Criticality & priority foundation          | Complete |
| Future | AI/ML optimization                         | Planned  |

------------------------------------------------------------------------

## 23. Future AI / Optimization

The future AI/optimization layer can consume:

``` text
Planning Tasks
+
Priority Factors
+
Priority Score
+
Available Windows
+
Candidate Windows
+
Constraints
+
Resources
+
Dependencies
+
Train / operational information
```

Possible future objectives include:

- Maximize asset availability
- Reduce maintenance downtime
- Coordinate compatible maintenance activities
- Respect hard operational constraints
- Use available block windows efficiently
- Consider resource availability
- Support weekly/monthly maintenance planning
- Learn from execution outcomes

The current implementation intentionally does not perform these final AI
decisions.

------------------------------------------------------------------------

## 24. Design Principles

### Source separation

Source tables represent source/normalized source information and do not
contain AI decisions.

### Traceability

Planning records preserve source provenance.

### Determinism

Normalization, availability derivation, feasibility and baseline
priority are reproducible.

### Explainability

Priority factors and calculation reasons are stored.

### Human validation

Final operational decisions remain subject to validation/controller
workflow.

### Idempotency

Repeated processing does not unnecessarily create duplicates.

### Extensibility

The future optimizer can consume the current planning foundation without
redesigning source tables.

### Testability

Each major implementation step is covered by automated tests and
verification scripts.

------------------------------------------------------------------------

## 25. Demo Sequence

``` text
1. Start PostgreSQL
2. Start FastAPI
3. Open /docs
4. Show trains
5. Show schedules
6. Show line occupancy
7. Show available windows
8. Show planning tasks
9. Recalculate priority
10. Show priority scores/bands
11. Show candidate windows
12. Show block-plan foundation
13. Validate a plan
14. Explain future AI optimizer
```

------------------------------------------------------------------------

