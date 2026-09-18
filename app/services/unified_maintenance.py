"""Deterministic normalization of TMS/TDMS/SMMS maintenance information.

Purpose
-------
STEP 7 common / unified data layer. Source maintenance-related records are
normalized into:

- ``defect_failure``            <- TMS defects, TDMS failures, SMMS alerts
- ``maintenance_requirement``   <- TMS/TDMS/SMMS maintenance records

These are NOT AI/optimization outputs. No priority / risk / recommendation /
optimized-schedule values are produced. ``block_requirement`` matching against
``available_window`` is intentionally NOT performed here.

Provenance
----------
Every unified row keeps ``(source_system_id, source_record_type,
source_record_id)``. Because ``source_record_id`` can reference different
source tables per type (TMS_DEFECT / TDMS_FAILURE / SMMS_ALERT / ...), no
polymorphic database FK is created; source-record validity is enforced by this
service (assets and referenced source tables are loaded from the database) and
by the tests. Source tables are never mutated.

Idempotency
-----------
A UNIQUE(source_system_id, source_record_type, source_record_id) constraint
backs deterministic upsert-or-skip behavior:

- missing row  -> created
- existing row with differing values -> updated
- existing row with identical values -> skipped

Running normalization twice never creates duplicates.

Deterministic field fallbacks
-----------------------------
- ``detected_at`` is required: TMS uses ``defect.detected_date`` falling back to
  the inspection date; TDMS uses ``failure_date``; SMMS uses
  ``incidence_date_time``.
- required ``status`` falls back to ``UNKNOWN`` only when the source value is
  absent.
- ``required_duration_minutes`` is derived only from recorded ``start_date`` /
  ``end_date`` when both exist (never optimized, never negative).
- SMMS alerts with no descriptive text use ``cause_code`` as the description;
  cause/feedback codes are preserved in ``remarks`` with explicit labels.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.defect_failure import DefectFailure
from app.models.maintenance_requirement import MaintenanceRequirement
from app.models.smms_alert import SMMSAlert
from app.models.smms_maintenance import SMMSMaintenance
from app.models.source_system import SourceSystem
from app.models.tdms_failure import TDMSFailure
from app.models.tdms_maintenance import TDMSMaintenance
from app.models.tms_defect import TMSDefect
from app.models.tms_maintenance import TMSMaintenance

RECORD_TYPES = {
    "tms_defect": "TMS_DEFECT",
    "tms_maintenance": "TMS_MAINTENANCE",
    "tdms_failure": "TDMS_FAILURE",
    "tdms_maintenance": "TDMS_MAINTENANCE",
    "smms_alert": "SMMS_ALERT",
    "smms_maintenance": "SMMS_MAINTENANCE",
}


def _source_system(db: Session, code: str) -> SourceSystem:
    source = db.scalar(
        select(SourceSystem).where(SourceSystem.system_code == code)
    )
    if source is None:
        raise ValueError(f"{code} source system not configured")
    return source


def _duration_minutes(start, end) -> int | None:
    if start is None or end is None:
        return None
    minutes = int((end - start).total_seconds() // 60)
    return minutes if minutes > 0 else None


def _upsert_defect_failure(
    db: Session,
    *,
    asset_id: int,
    source_system_id: int,
    source_record_type: str,
    source_record_id: int,
    defect_code: str | None,
    defect_description: str | None,
    severity: str | None,
    detected_at,
    status: str,
    rectified_at,
    remarks: str | None,
):
    existing = db.scalar(
        select(DefectFailure).where(
            DefectFailure.source_system_id == source_system_id,
            DefectFailure.source_record_type == source_record_type,
            DefectFailure.source_record_id == source_record_id,
        )
    )
    values = {
        "asset_id": asset_id,
        "source_system_id": source_system_id,
        "source_record_type": source_record_type,
        "source_record_id": source_record_id,
        "defect_code": defect_code,
        "defect_description": defect_description,
        "severity": severity,
        "detected_at": detected_at,
        "status": status,
        "rectified_at": rectified_at,
        "remarks": remarks,
    }
    if existing is None:
        row = DefectFailure(**values)
        db.add(row)
        return row, "created"
    changed = any(getattr(existing, key) != value for key, value in values.items())
    if changed:
        for key, value in values.items():
            setattr(existing, key, value)
        return existing, "updated"
    return existing, "skipped"


def _upsert_maintenance_requirement(
    db: Session,
    *,
    asset_id: int,
    source_system_id: int,
    source_record_type: str,
    source_record_id: int,
    defect_failure_id: int | None,
    maintenance_type: str,
    description: str | None,
    required_duration_minutes: int | None,
    planned_date,
    status: str,
    remarks: str | None,
):
    existing = db.scalar(
        select(MaintenanceRequirement).where(
            MaintenanceRequirement.source_system_id == source_system_id,
            MaintenanceRequirement.source_record_type == source_record_type,
            MaintenanceRequirement.source_record_id == source_record_id,
        )
    )
    values = {
        "asset_id": asset_id,
        "source_system_id": source_system_id,
        "source_record_type": source_record_type,
        "source_record_id": source_record_id,
        "defect_failure_id": defect_failure_id,
        "maintenance_type": maintenance_type,
        "description": description,
        "required_duration_minutes": required_duration_minutes,
        "planned_date": planned_date,
        "status": status,
        "remarks": remarks,
    }
    if existing is None:
        row = MaintenanceRequirement(**values)
        db.add(row)
        return row, "created"
    changed = any(getattr(existing, key) != value for key, value in values.items())
    if changed:
        for key, value in values.items():
            setattr(existing, key, value)
        return existing, "updated"
    return existing, "skipped"


def _find_defect_failure(
    db: Session, source_system_id: int, source_record_type: str, source_record_id: int
) -> DefectFailure | None:
    return db.scalar(
        select(DefectFailure).where(
            DefectFailure.source_system_id == source_system_id,
            DefectFailure.source_record_type == source_record_type,
            DefectFailure.source_record_id == source_record_id,
        )
    )


def normalize_tms(db: Session) -> dict[str, int]:
    """Normalize TMS defects and TMS maintenance. Returns a count summary."""
    tms = _source_system(db, "TMS")
    stats = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}

    defects = db.scalars(
        select(TMSDefect).options(selectinload(TMSDefect.inspection))
    ).all()
    for defect in defects:
        stats["processed"] += 1
        detected_at = defect.detected_date
        if detected_at is None and defect.inspection is not None:
            detected_at = defect.inspection.inspection_date
        if detected_at is None:
            raise ValueError(f"TMS defect {defect.id} has no detectable date")
        _, action = _upsert_defect_failure(
            db,
            asset_id=defect.asset_id,
            source_system_id=tms.id,
            source_record_type=RECORD_TYPES["tms_defect"],
            source_record_id=defect.id,
            defect_code=defect.defect_code,
            defect_description=defect.defect_description,
            severity=defect.severity,
            detected_at=detected_at,
            status=defect.status or "UNKNOWN",
            rectified_at=None,
            remarks=defect.remarks,
        )
        stats[action] += 1

    db.flush()

    maintenances = db.scalars(select(TMSMaintenance)).all()
    for maintenance in maintenances:
        stats["processed"] += 1
        defect_failure = _find_defect_failure(
            db, tms.id, RECORD_TYPES["tms_defect"], maintenance.defect_id
        )
        _, action = _upsert_maintenance_requirement(
            db,
            asset_id=maintenance.asset_id,
            source_system_id=tms.id,
            source_record_type=RECORD_TYPES["tms_maintenance"],
            source_record_id=maintenance.id,
            defect_failure_id=defect_failure.id if defect_failure is not None else None,
            maintenance_type=maintenance.maintenance_type,
            description=maintenance.remarks,
            required_duration_minutes=_duration_minutes(
                maintenance.start_date, maintenance.end_date
            ),
            planned_date=maintenance.planned_date,
            status=maintenance.status or "UNKNOWN",
            remarks=None,
        )
        stats[action] += 1

    db.commit()
    return stats


def normalize_tdms(db: Session) -> dict[str, int]:
    """Normalize TDMS failures and TDMS maintenance. Returns a count summary."""
    tdms = _source_system(db, "TDMS")
    stats = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}

    failures = db.scalars(select(TDMSFailure)).all()
    for failure in failures:
        stats["processed"] += 1
        _, action = _upsert_defect_failure(
            db,
            asset_id=failure.asset_id,
            source_system_id=tdms.id,
            source_record_type=RECORD_TYPES["tdms_failure"],
            source_record_id=failure.id,
            defect_code=failure.failure_code,
            defect_description=failure.failure_description,
            severity=failure.severity,
            detected_at=failure.failure_date,
            status=failure.status,
            rectified_at=failure.rectification_date,
            remarks=failure.remarks,
        )
        stats[action] += 1

    db.flush()

    maintenances = db.scalars(select(TDMSMaintenance)).all()
    for maintenance in maintenances:
        stats["processed"] += 1
        defect_failure = None
        if maintenance.failure_id is not None:
            defect_failure = _find_defect_failure(
                db, tdms.id, RECORD_TYPES["tdms_failure"], maintenance.failure_id
            )
        _, action = _upsert_maintenance_requirement(
            db,
            asset_id=maintenance.asset_id,
            source_system_id=tdms.id,
            source_record_type=RECORD_TYPES["tdms_maintenance"],
            source_record_id=maintenance.id,
            defect_failure_id=defect_failure.id if defect_failure is not None else None,
            maintenance_type=maintenance.maintenance_type,
            description=maintenance.remarks,
            required_duration_minutes=_duration_minutes(
                maintenance.start_date, maintenance.end_date
            ),
            planned_date=maintenance.planned_date,
            status=maintenance.status,
            remarks=None,
        )
        stats[action] += 1

    db.commit()
    return stats


def normalize_smms(db: Session) -> dict[str, int]:
    """Normalize SMMS alerts and SMMS maintenance. Returns a count summary."""
    smms = _source_system(db, "SMMS")
    stats = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}

    alerts = db.scalars(select(SMMSAlert)).all()
    for alert in alerts:
        stats["processed"] += 1
        description = alert.remarks or alert.cause_code
        parts = []
        if alert.cause_code:
            parts.append(f"cause_code={alert.cause_code}")
        if alert.alert_feedback_code:
            parts.append(f"alert_feedback_code={alert.alert_feedback_code}")
        remarks = "; ".join(parts) if parts else (alert.remarks if alert.remarks else None)
        _, action = _upsert_defect_failure(
            db,
            asset_id=alert.asset_id,
            source_system_id=smms.id,
            source_record_type=RECORD_TYPES["smms_alert"],
            source_record_id=alert.id,
            defect_code=alert.alert_type_code,
            defect_description=description,
            severity=None,
            detected_at=alert.incidence_date_time,
            status=alert.alert_status_code,
            rectified_at=alert.rectification_date_time,
            remarks=remarks,
        )
        stats[action] += 1

    db.flush()

    maintenances = db.scalars(select(SMMSMaintenance)).all()
    for maintenance in maintenances:
        stats["processed"] += 1
        defect_failure = None
        if maintenance.alert_id is not None:
            defect_failure = _find_defect_failure(
                db, smms.id, RECORD_TYPES["smms_alert"], maintenance.alert_id
            )
        _, action = _upsert_maintenance_requirement(
            db,
            asset_id=maintenance.asset_id,
            source_system_id=smms.id,
            source_record_type=RECORD_TYPES["smms_maintenance"],
            source_record_id=maintenance.id,
            defect_failure_id=defect_failure.id if defect_failure is not None else None,
            maintenance_type=maintenance.maintenance_type,
            description=maintenance.remarks,
            required_duration_minutes=_duration_minutes(
                maintenance.start_date, maintenance.end_date
            ),
            planned_date=maintenance.planned_date,
            status=maintenance.status,
            remarks=None,
        )
        stats[action] += 1

    db.commit()
    return stats