"""Deterministic available-window derivation from COA/CTC source data.

Purpose
-------
This is NOT AI/ML, NOT optimization, and NOT block planning. It is a fully
deterministic, explainable computation that derives candidate operational
availability intervals ("available_window") purely from COA/CTC source
records currently present in the database.

Exact derivation rule
---------------------
For each (station_code, line_number) key:

1. Collect *conflicting* source intervals:
   - line_occupancy rows whose occupancy_status is ``OCCUPIED`` or
     ``BLOCKED`` and which have a well-formed
     ``occupancy_start < occupancy_end`` interval. (``RELEASED`` and
     ``UNKNOWN`` records never create or extend a conflict.)
   - train_schedule rows where BOTH ``scheduled_arrival`` and
     ``scheduled_departure`` are present for the same station/line; a
     scheduled station stop is treated as recorded scheduled occupancy.
     ``scheduled_run_through`` is a point-in-time event and forms no
     interval, so it is ignored.

2. Merge overlapping/contained conflicting intervals into effective
   occupied intervals (union), so gaps are measured between the true end
   of one occupied interval and the true start of the next.

3. Between any two consecutive effective occupied intervals where
   ``next.start > prev.end`` (strictly positive gap), derive an
   ``AVAILABLE`` window ``[prev.end, next.start]``.

4. ``duration_minutes`` = integer whole minutes of
   ``(next.start - prev.end)``, never zero/negative, because negative or
   zero-duration windows are never emitted.

Important caveat
----------------
Absence of a recorded occupancy record is NOT proof that the physical
railway line is free. Every generated record is only *DERIVED
OPERATIONAL AVAILABILITY* based on the source information available in
this database at ``generated_at`` time. The ``calculation_source`` column
records the derivation rule version that produced it.

Safety guarantees
-----------------
- Only ``available_window`` is written.
- For idempotent re-generation the previously derived ``available_window``
  rows are replaced; source tables (``train``, ``train_movement``,
  ``train_schedule``, ``line_occupancy``, ``operational_event``) are never
  modified.
- No maintenance task is assigned, no optimization is performed, and no
  final railway block permission is created.
"""
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.available_window import AvailableWindow
from app.models.line_occupancy import LineOccupancy
from app.models.train_schedule import TrainSchedule

# Only these line_occupancy statuses count as recorded line conflicts.
OCCUPYING_STATUSES = ("OCCUPIED", "BLOCKED")

# Fixed, explainable label stored on every derived window. The source key
# (station_code + line_number) and the source FKs keep the traceability.
CALCULATION_SOURCE = "DETERMINISTIC:COA_SOURCE_DERIVATION_GAP"

WINDOW_STATUS_AVAILABLE = "AVAILABLE"


def _now_naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def derive_available_windows(db: Session) -> list[AvailableWindow]:
    """Recompute and store the current set of derived available windows.

    Deterministic: the same source data always yields the same windows.
    """
    schedule_rows = db.scalars(
        select(TrainSchedule).where(
            TrainSchedule.scheduled_arrival.is_not(None),
            TrainSchedule.scheduled_departure.is_not(None),
        )
    ).all()

    occupancy_rows = db.scalars(
        select(LineOccupancy).where(
            LineOccupancy.occupancy_status.in_(OCCUPYING_STATUSES),
            LineOccupancy.occupancy_start.is_not(None),
            LineOccupancy.occupancy_end.is_not(None),
        )
    ).all()

    conflicts: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    for row in occupancy_rows:
        if row.occupancy_start < row.occupancy_end:
            conflicts[(row.station_code, row.line_number)].append(
                (row.occupancy_start, row.occupancy_end, row.id, None)
            )
    for row in schedule_rows:
        if row.scheduled_arrival < row.scheduled_departure:
            conflicts[(row.station_code, row.line_number)].append(
                (row.scheduled_arrival, row.scheduled_departure, None, row.id)
            )

    windows: list[AvailableWindow] = []
    for (station_code, line_number), intervals in conflicts.items():
        intervals.sort(key=lambda item: (item[0], item[1]))

        merged: list[tuple] = []
        for start, end, source_occupancy_id, source_schedule_id in intervals:
            if merged and start <= merged[-1][1]:
                if end > merged[-1][1]:
                    merged[-1] = (
                        merged[-1][0],
                        end,
                        merged[-1][2] or source_occupancy_id,
                        merged[-1][3] or source_schedule_id,
                    )
            else:
                merged.append(
                    (start, end, source_occupancy_id, source_schedule_id)
                )

        for prev, nxt in zip(merged, merged[1:]):
            gap_start = prev[1]
            gap_end = nxt[0]
            minutes = int((gap_end - gap_start).total_seconds() // 60)
            if minutes <= 0:
                continue
            windows.append(
                AvailableWindow(
                    station_code=station_code,
                    line_number=line_number,
                    window_start=gap_start,
                    window_end=gap_end,
                    duration_minutes=minutes,
                    window_status=WINDOW_STATUS_AVAILABLE,
                    calculation_source=CALCULATION_SOURCE,
                    generated_at=_now_naive_utc(),
                    source_schedule_id=prev[3],
                    source_occupancy_id=prev[2],
                    remarks=(
                        f"Derived gap: effective occupied interval ending {gap_start} "
                        f"(source_occupancy_id={prev[2]}, source_schedule_id={prev[3]}) "
                        f"and next recorded conflict starting {gap_end} "
                        f"(source_occupancy_id={nxt[2]}, source_schedule_id={nxt[3]})."
                    ),
                )
            )

    if not windows:
        return []

    db.execute(delete(AvailableWindow))
    db.add_all(windows)
    db.commit()
    for window in windows:
        db.refresh(window)
    return windows