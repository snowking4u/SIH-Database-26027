"""STEP 12 deterministic criticality & priority foundation.

Purpose
-------
Give every eligible planning task a structured, explainable priority
assessment stored in ``planning_priority``. The whole computation is
deterministic and reproducible: the same input data always produces the same
factors, score, band and reason text. NO ML, NO ranking, NO optimization, NO
AI prediction is performed anywhere in this module.

Scoring model
-------------
``CALCULATION_VERSION = "STEP12-DETERMINISTIC-1.0"``

This is a *project baseline scoring model* documented for reproducibility. It
is NOT an official Indian Railways scoring formula and must not be presented
as one.

Factor scores (normalized 0-100):

- criticality           LOW=10, MEDIUM=30, HIGH=60, CRITICAL=100
- urgency               LOW=10, MEDIUM=30, HIGH=60, IMMEDIATE=100
- safety_impact         NONE=0, LOW=20, MEDIUM=50, HIGH=80, CRITICAL=100
- asset_availability_impact  NONE=0, LOW=20, MEDIUM=50, HIGH=80, CRITICAL=100
- traffic_impact        NONE=0, LOW=20, MEDIUM=50, HIGH=80, CRITICAL=100
- failure_recurrence    NONE=0, LOW=25, MEDIUM=60, HIGH=100
- defect_age_days       bucket -> 0-7d =10, 8-30d =30, 31-90d =60, 91+d =100

priority_score = round(0.20*criticality + 0.15*urgency + 0.25*safety_impact
                       + 0.20*asset_availability_impact + 0.10*traffic_impact
                       + 0.05*failure_recurrence + 0.05*defect_age, 2)

The composite is clamped to [0, 100]. Rounding is done with Python
``round(value, 2)`` after the weighted sum (see ``calculate_priority_score``).
Using ``round`` makes the result reproducible across runs.

Priority band thresholds (on the rounded score):

    0   <= score <  25  -> LOW
    25  <= score <  50  -> MEDIUM
    50  <= score <  75  -> HIGH
    75  <= score <= 100 -> CRITICAL

(Numerically equivalent to the documented boundaries 24.99->LOW, 25.00->
MEDIUM, 49.99->MEDIUM, 50.00->HIGH, 74.99->HIGH, 75.00->CRITICAL.)

Deterministic factor derivation
-------------------------------
1. Safety impact: from the linked source defect/failure severity
   (``defect_failure.severity``). CRITICAL->CRITICAL, HIGH->HIGH,
   MEDIUM->MEDIUM, LOW->LOW; any other/unknown or missing value -> NONE.
   Unknown source tokens (e.g. speculative source-specific labels) are never
   mapped to a higher band.

2. Criticality: based on the same available source severity/condition
   information and mapped with the identical CRITICAL/HIGH/MEDIUM/LOW table.
   When no severity or asset condition is available the documented
   conservative default LOW is used (no source evidence to raise it). No
   railway-specific safety classification is invented.

3. Urgency: derived deterministically from the remaining time until
   ``block_requirement.latest_end`` at the calculation timestamp. No deadline
   -> LOW (unless another documented source factor raises it):
       remaining < 0 (already past deadline)      -> IMMEDIATE
       remaining <= 1 day                         -> IMMEDIATE
       remaining <= 7 days                        -> HIGH
       remaining <= 30 days                       -> MEDIUM
       otherwise                                  -> LOW

4. Asset availability impact: raised deterministically when the block
   requirement carries operational constraints (power/traffic block flags):
       power AND traffic required  -> HIGH
       exactly one of the two      -> MEDIUM
       no explicit constraint      -> LOW (conservative floor: a task with a
                                      block requirement still takes the asset
                                      out of service; never invented higher).
   Operational consequences are never invented.

5. Traffic impact: only from ``block_requirement.traffic_block_required``:
       True  -> HIGH
       False -> NONE (no source evidence of traffic impact)

6. Failure recurrence: counts ``defect_failure`` rows for the same asset
   within the documented lookback window of 365 days ending at the
   calculation timestamp:
       0 records -> NONE (insufficient history)
       1 record  -> LOW
       2 records -> MEDIUM
       3+        -> HIGH

7. Defect age: from the linked defect/failure ``detected_at`` to the
   calculation timestamp, rounded down to whole days and clamped to >= 0 so a
   future/negative age is never produced. A missing detection date is handled
   explicitly as age 0 and recorded in the reason.

Data integrity
--------------
No source fact is ever invented. When a factor cannot be reliably derived the
documented fallback above is used and the reason is recorded in
``calculation_reason``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.block_requirement import BlockRequirement
from app.models.defect_failure import DefectFailure
from app.models.maintenance_requirement import MaintenanceRequirement
from app.models.planning_priority import PlanningPriority
from app.models.planning_task import PlanningTask

CALCULATION_VERSION = "STEP12-DETERMINISTIC-1.0"

# Factor score tables (normalized 0-100).
CRITICALITY_SCORE = {"LOW": 10, "MEDIUM": 30, "HIGH": 60, "CRITICAL": 100}
URGENCY_SCORE = {"LOW": 10, "MEDIUM": 30, "HIGH": 60, "IMMEDIATE": 100}
SAFETY_IMPACT_SCORE = {
    "NONE": 0,
    "LOW": 20,
    "MEDIUM": 50,
    "HIGH": 80,
    "CRITICAL": 100,
}
ASSET_AVAILABILITY_IMPACT_SCORE = {
    "NONE": 0,
    "LOW": 20,
    "MEDIUM": 50,
    "HIGH": 80,
    "CRITICAL": 100,
}
TRAFFIC_IMPACT_SCORE = {
    "NONE": 0,
    "LOW": 20,
    "MEDIUM": 50,
    "HIGH": 80,
    "CRITICAL": 100,
}
RECURRENCE_SCORE = {"NONE": 0, "LOW": 25, "MEDIUM": 60, "HIGH": 100}

# Deterministic weights (documented project baseline only).
WEIGHTS = {
    "criticality": 0.20,
    "urgency": 0.15,
    "safety_impact": 0.25,
    "asset_availability_impact": 0.20,
    "traffic_impact": 0.10,
    "failure_recurrence": 0.05,
    "defect_age": 0.05,
}

# Source severity -> factor mapping. Unknown tokens are treated as missing.
SEVERITY_MAP = {
    "CRITICAL": "CRITICAL",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
}

# Documented failure-recurrence lookback window (days).
RECURRENCE_LOOKBACK_DAYS = 365

# Documented urgency time thresholds (days) applied to the remaining time.
URGENCY_IMMEDIATE_DAYS = 1
URGENCY_HIGH_DAYS = 7
URGENCY_MEDIUM_DAYS = 30


def _utc_now() -> datetime:
    """Naive UTC reference timestamp used for deterministic calculations."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Mapping helpers (pure, deterministic, directly testable)
# --------------------------------------------------------------------------- #
def defect_age_bucket(days: int) -> int:
    """Map defect age in days to its normalized score (documented buckets)."""
    if days <= 7:
        return 10
    if days <= 30:
        return 30
    if days <= 90:
        return 60
    return 100


def calculate_priority_band(score: float) -> str:
    """Convert a rounded priority score into its documented band."""
    if score < 25.0:
        return "LOW"
    if score < 50.0:
        return "MEDIUM"
    if score < 75.0:
        return "HIGH"
    return "CRITICAL"


def calculate_priority_score(factors: dict) -> tuple[float, str]:
    """Weighted composite score (rounded to 2 places, clamped to 0-100).

    Returns ``(priority_score, priority_band)``. ``factors`` must contain the
    keys ``criticality_level``, ``urgency_level``, ``safety_impact``,
    ``asset_availability_impact``, ``traffic_impact``, ``failure_recurrence``
    and ``defect_age_days``.
    """
    raw = (
        WEIGHTS["criticality"] * CRITICALITY_SCORE[factors["criticality_level"]]
        + WEIGHTS["urgency"] * URGENCY_SCORE[factors["urgency_level"]]
        + WEIGHTS["safety_impact"] * SAFETY_IMPACT_SCORE[factors["safety_impact"]]
        + WEIGHTS["asset_availability_impact"]
        * ASSET_AVAILABILITY_IMPACT_SCORE[factors["asset_availability_impact"]]
        + WEIGHTS["traffic_impact"] * TRAFFIC_IMPACT_SCORE[factors["traffic_impact"]]
        + WEIGHTS["failure_recurrence"]
        * RECURRENCE_SCORE[factors["failure_recurrence"]]
        + WEIGHTS["defect_age"] * defect_age_bucket(factors["defect_age_days"])
    )
    score = min(100.0, max(0.0, round(raw, 2)))
    return score, calculate_priority_band(score)


# --------------------------------------------------------------------------- #
# Deterministic factor derivation from existing project data
# --------------------------------------------------------------------------- #
@dataclass
class PriorityFactors:
    criticality_level: str
    urgency_level: str
    safety_impact: str
    asset_availability_impact: str
    traffic_impact: str
    failure_recurrence: str
    defect_age_days: int
    reasons: list[str]


def _derive_safety_and_criticality(severity: str | None) -> tuple[str, str, str]:
    mapped = SEVERITY_MAP.get((severity or "").upper())
    if mapped is None:
        return ("NONE", "LOW", "severity missing/unknown -> safety NONE, criticality LOW")
    return (mapped, mapped, f"source severity {severity.upper()} mapped")


def _derive_urgency(latest_end: datetime | None, ref: datetime) -> tuple[str, str]:
    if latest_end is None:
        return ("LOW", "no deadline (block_requirement.latest_end) -> urgency LOW")
    remaining = latest_end - ref
    total_seconds = max(remaining.total_seconds(), 0)  # never negative
    remaining_days = total_seconds / 86400.0
    if remaining.total_seconds() < 0:
        return ("IMMEDIATE", "deadline already passed -> urgency IMMEDIATE")
    if remaining_days <= URGENCY_IMMEDIATE_DAYS:
        return ("IMMEDIATE", f"deadline within {remaining_days:.1f}d -> IMMEDIATE")
    if remaining_days <= URGENCY_HIGH_DAYS:
        return ("HIGH", f"deadline within {remaining_days:.1f}d -> HIGH")
    if remaining_days <= URGENCY_MEDIUM_DAYS:
        return ("MEDIUM", f"deadline within {remaining_days:.1f}d -> MEDIUM")
    return ("LOW", f"deadline in {remaining_days:.1f}d -> LOW")


def _derive_availability_impact(block: BlockRequirement | None) -> tuple[str, str]:
    if block is None:
        return ("LOW", "no block requirement -> availability impact LOW (floor)")
    power = bool(block.power_block_required)
    traffic = bool(block.traffic_block_required)
    if power and traffic:
        return ("HIGH", "power and traffic block required -> HIGH")
    if power:
        return ("MEDIUM", "power block required -> MEDIUM")
    if traffic:
        return ("MEDIUM", "traffic block required -> MEDIUM")
    return ("LOW", "no explicit operational block constraints -> LOW (floor)")


def _derive_recurrence(db: Session, asset_id: int, ref: datetime) -> tuple[str, str]:
    lookback_start = ref - timedelta(days=RECURRENCE_LOOKBACK_DAYS)
    count = (
        db.scalar(
            select(func.count())
            .select_from(DefectFailure)
            .where(
                DefectFailure.asset_id == asset_id,
                DefectFailure.detected_at >= lookback_start,
            )
        )
        or 0
    )
    if count <= 0:
        return ("NONE", "no defect/failure history in lookback window")
    if count == 1:
        return ("LOW", f"{count} defect/failure record(s) in 365d lookback")
    if count == 2:
        return ("MEDIUM", f"{count} defect/failure records in 365d lookback")
    return ("HIGH", f"{count} defect/failure records in 365d lookback")


def _derive_defect_age(detected_at: datetime | None, ref: datetime) -> tuple[int, str]:
    if detected_at is None:
        return (0, "no detection date -> defect age 0 (explicit missing-date handling)")
    age_seconds = max((ref - detected_at).total_seconds(), 0)
    age_days = int(age_seconds // 86400)
    return (age_days, f"defect age {age_days} day(s) since detection")


def derive_priority_factors(
    db: Session, task: PlanningTask, reference_time: datetime | None = None
) -> PriorityFactors:
    """Derive deterministic factors for one planning task from existing data.

    ``reference_time`` defaults to the current UTC time and is the only
    time-dependent input; every rule is a pure function of the recorded data
    plus this timestamp. Never invents safety, severity, traffic or other
    source facts.
    """
    ref = reference_time or _utc_now()

    mr = db.get(MaintenanceRequirement, task.maintenance_requirement_id)
    block = None
    if task.block_requirement_id is not None:
        block = db.get(BlockRequirement, task.block_requirement_id)

    severity: str | None = None
    detected_at: datetime | None = None
    if mr is not None and mr.defect_failure_id is not None:
        defect = db.get(DefectFailure, mr.defect_failure_id)
        if defect is not None:
            severity = defect.severity
            detected_at = defect.detected_at
    else:
        # Fall back to newest defect/failure on the same asset so the
        # assessment stays grounded in actual source records.
        defect = db.scalar(
            select(DefectFailure)
            .where(DefectFailure.asset_id == task.asset_id)
            .order_by(DefectFailure.detected_at.desc())
            .limit(1)
        )
        if defect is not None:
            severity = defect.severity
            detected_at = defect.detected_at

    safety_impact, criticality, safety_reason = _derive_safety_and_criticality(severity)

    latest_end = block.latest_end if block is not None else None
    urgency, urgency_reason = _derive_urgency(latest_end, ref)

    traffic_flag = _traffic_flag(block)
    traffic_impact = "HIGH" if traffic_flag else "NONE"
    traffic_reason = (
        "block_requirement.traffic_block_required -> HIGH"
        if traffic_flag
        else "no traffic block evidence -> NONE"
    )

    availability_impact, availability_reason = _derive_availability_impact(
        block
    )

    recurrence, recurrence_reason = _derive_recurrence(db, task.asset_id, ref)

    defect_age_days, age_reason = _derive_defect_age(detected_at, ref)

    reasons = [
        f"criticality={criticality}",
        f"urgency={urgency}",
        f"safety_impact={safety_impact}",
        f"asset_availability_impact={availability_impact}",
        f"traffic_impact={traffic_impact}",
        f"failure_recurrence={recurrence}",
        f"defect_age_days={defect_age_days}",
        safety_reason,
        urgency_reason,
        availability_reason,
        traffic_reason,
        recurrence_reason,
        age_reason,
    ]

    return PriorityFactors(
        criticality_level=criticality,
        urgency_level=urgency,
        safety_impact=safety_impact,
        asset_availability_impact=availability_impact,
        traffic_impact=traffic_impact,
        failure_recurrence=recurrence,
        defect_age_days=defect_age_days,
        reasons=reasons,
    )


def _traffic_flag(block: BlockRequirement | None) -> bool:
    return block is not None and bool(block.traffic_block_required)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def create_or_update_priority(
    db: Session, task: PlanningTask, reference_time: datetime | None = None
) -> PlanningPriority:
    """Create or update the single priority assessment for a planning task.

    A planning task has at most one current assessment (UNIQUE
    ``planning_priority.planning_task_id``); recalculating always updates the
    existing row and never creates a duplicate.
    """
    ref = reference_time or _utc_now()
    factors = derive_priority_factors(db, task, reference_time=ref)
    score, band = calculate_priority_score(
        {
            "criticality_level": factors.criticality_level,
            "urgency_level": factors.urgency_level,
            "safety_impact": factors.safety_impact,
            "asset_availability_impact": factors.asset_availability_impact,
            "traffic_impact": factors.traffic_impact,
            "failure_recurrence": factors.failure_recurrence,
            "defect_age_days": factors.defect_age_days,
        }
    )
    reason = "; ".join(factors.reasons) if factors.reasons else "no reason recorded"

    existing = db.scalar(
        select(PlanningPriority).where(
            PlanningPriority.planning_task_id == task.id
        )
    )
    values = {
        "planning_task_id": task.id,
        "criticality_level": factors.criticality_level,
        "urgency_level": factors.urgency_level,
        "safety_impact": factors.safety_impact,
        "asset_availability_impact": factors.asset_availability_impact,
        "traffic_impact": factors.traffic_impact,
        "failure_recurrence": factors.failure_recurrence,
        "defect_age_days": factors.defect_age_days,
        "priority_score": Decimal(str(score)),
        "priority_band": band,
        "calculation_version": CALCULATION_VERSION,
        "calculated_at": ref,
        "calculation_reason": reason,
    }
    if existing is None:
        existing = PlanningPriority(**values)
        db.add(existing)
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    db.commit()
    db.refresh(existing)
    return existing


def recalculate_task_priority(
    db: Session, task_id: int, reference_time: datetime | None = None
) -> PlanningPriority | None:
    """Recalculate the priority of one planning task.

    Returns ``None`` when the planning task does not exist.
    """
    task = db.get(PlanningTask, task_id)
    if task is None:
        return None
    return create_or_update_priority(db, task, reference_time=reference_time)


def recalculate_all_priorities(
    db: Session, reference_time: datetime | None = None
) -> dict[str, int]:
    """Recalculate every planning task's priority assessment.

    Idempotent: existing assessments are updated in place, missing ones are
    created; a single shared ``reference_time`` keeps the batch consistent.
    """
    ref = reference_time or _utc_now()
    stats = {"processed": 0, "created": 0, "updated": 0}

    tasks = db.scalars(select(PlanningTask).order_by(PlanningTask.id)).all()
    for task in tasks:
        stats["processed"] += 1
        exists = db.scalar(
            select(PlanningPriority.id).where(
                PlanningPriority.planning_task_id == task.id
            )
        )
        create_or_update_priority(db, task, reference_time=ref)
        if exists is None:
            stats["created"] += 1
        else:
            stats["updated"] += 1

    db.commit()
    return stats