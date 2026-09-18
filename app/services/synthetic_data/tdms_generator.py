"""STEP 11 synthetic TDMS source data: track inspections, failures, maintenance.

Failure rows reference an optional inspection; maintenance rows reference an
optional failure, so the generator also emits a small number of "orphan"
maintenance records (no linked failure) to exercise that unified-layer edge
case on purpose.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tdms_failure import TDMSFailure
from app.models.tdms_inspection import TDMSInspection
from app.models.tdms_maintenance import TDMSMaintenance

from . import random_utils as ru
from .config import MARKER, SyntheticConfig
from .master_generator import AssetInfo

INSPECTION_TYPES = ["TRACK_GEOMETRY", "RAIL_PROFILE", "ZIG_ZAG", "GAUGE_SURVEY"]
FAILURE_CODES = [
    "TDMS-FAL-001",
    "TDMS-FAL-002",
    "TDMS-FAL-003",
    "TDMS-FAL-004",
    "TDMS-FAL-005",
]
SEVERITIES = ["minor", "minor", "major", "through"]
MAINTENANCE_TYPES = [
    "TRACK_RECONDITIONING",
    "RAIL_GRINDING",
    "SLEEPER_REPLACEMENT",
    "BALLAST_DESILTING",
    "JOINT_RENOVATION",
]
STATUSES = ["OPEN", "RECTIFIED"]

ORPHAN_MAINTENANCE_RATIO = 0.05


class TdmsGenerator:
    def __init__(self, db: Session, cfg: SyntheticConfig, assets: list[AssetInfo]):
        self.db = db
        self.cfg = cfg
        self.rng: random.Random = cfg.module_rng(0x4)
        self.assets = assets

    def generate(self) -> dict:
        stats = {"inspections": 0, "failures": 0, "maintenance": 0}
        per_asset_inspections = ru.distribution(
            self.cfg.inspection_count, len(self.assets), self.rng
        )
        per_asset_failures = ru.distribution(
            self.cfg.defect_count, len(self.assets), self.rng
        )
        for idx, asset in enumerate(self.assets):
            if self._has_existing(asset.id):
                continue
            stats["inspections"] += self._inspections_for(asset, per_asset_inspections[idx])
            stats["failures"] += self._failures_for(asset, per_asset_failures[idx])
            stats["maintenance"] += self._maintenance_for(asset)
        self.db.commit()
        return stats

    def _has_existing(self, asset_id: int) -> bool:
        return (
            self.db.scalar(
                select(TDMSInspection.id).where(
                    TDMSInspection.asset_id == asset_id,
                    TDMSInspection.remarks.like(f"%{MARKER}%"),
                ).limit(1)
            )
            is not None
        )

    # ------------------------------------------------------------------ #
    def _window_span(self) -> tuple[datetime, datetime]:
        return (
            ru.day_start(self.cfg.start_date, 0),
            ru.day_start(self.cfg.start_date, self.cfg.days) - timedelta(minutes=1),
        )

    def _inspection_for(self, asset: AssetInfo, day_offset: int) -> TDMSInspection:
        when = ru.day_start(self.cfg.start_date, day_offset) + timedelta(
            minutes=ru.int_between(self.rng, 30, 540)
        )
        inspection = TDMSInspection(
            asset_id=asset.id,
            inspection_date=when,
            inspection_type=INSPECTION_TYPES[asset.id % len(INSPECTION_TYPES)],
            parameter_code=f"TDMS-PARAM-{asset.id % 5 + 1}",
            parameter_value=str(ru.int_between(self.rng, 1, 40)),
            remarks=f"{MARKER} synthetic TDMS inspection.",
        )
        self.db.add(inspection)
        self.db.flush()
        return inspection

    def _inspections_for(self, asset: AssetInfo, count: int) -> int:
        created = 0
        for i in range(count):
            self._inspection_for(asset, i % max(1, self.cfg.days))
            created += 1
        return created

    def _failures_for(self, asset: AssetInfo, count: int) -> int:
        created = 0
        for i in range(count):
            inspection = self.db.scalar(
                select(TDMSInspection)
                .where(TDMSInspection.asset_id == asset.id)
                .order_by(TDMSInspection.inspection_date)
            )
            if inspection is None:
                break
            failure_date = inspection.inspection_date + timedelta(
                minutes=ru.int_between(self.rng, 30, 300)
            )
            if failure_date >= ru.day_start(self.cfg.start_date, self.cfg.days):
                failure_date = inspection.inspection_date
            severity = (
                "through"
                if ru.rand_boolean(self.rng, self.cfg.scenario_config.severe_ratio)
                else ru.pick(self.rng, SEVERITIES)
            )
            rectified = (
                ru.day_start(self.cfg.start_date, self.cfg.days) - timedelta(days=1)
                if ru.rand_boolean(self.rng, 0.5)
                else None
            )
            failure = TDMSFailure(
                asset_id=asset.id,
                inspection_id=inspection.id,
                failure_code=FAILURE_CODES[asset.id % len(FAILURE_CODES)],
                failure_description=(
                    f"{MARKER} synthetic TDMS failure after {inspection.inspection_type}."
                ),
                severity=severity,
                failure_date=failure_date,
                status="RECTIFIED" if rectified else ru.pick(self.rng, STATUSES),
                rectification_date=rectified,
                remarks=f"{MARKER} synthetic TDMS failure.",
            )
            self.db.add(failure)
            self.db.flush()
            created += 1
        return created

    def _maintenance_for(self, asset: AssetInfo) -> int:
        failures = self.db.scalars(
            select(TDMSFailure)
            .where(TDMSFailure.asset_id == asset.id)
            .order_by(TDMSFailure.id)
        ).all()
        created = 0
        for failure in failures:
            start = failure.failure_date + timedelta(
                minutes=ru.int_between(self.rng, 60, 600)
            )
            duration = ru.pick(self.rng, [30, 45, 60, 90, 120])
            end = start + timedelta(minutes=duration)
            last = ru.day_start(self.cfg.start_date, self.cfg.days)
            if end >= last:
                start = last - timedelta(minutes=duration + 10)
                end = start + timedelta(minutes=duration)
            missing_end = ru.rand_boolean(self.rng, 0.03)
            maintenance = TDMSMaintenance(
                asset_id=asset.id,
                failure_id=failure.id,
                maintenance_type=MAINTENANCE_TYPES[asset.id % len(MAINTENANCE_TYPES)],
                planned_date=start,
                start_date=start,
                end_date=None if missing_end else end,
                status="PLANNED",
                remarks=(
                    f"{MARKER} synthetic TDMS maintenance for {failure.failure_code}; "
                    f"planned duration {duration} minutes."
                ),
            )
            self.db.add(maintenance)
            self.db.flush()
            created += 1
        # Deliberate orphan records: maintenance not linked to any failure.
        if (
            self.assets
            and ru.rand_boolean(self.rng, ORPHAN_MAINTENANCE_RATIO)
            and failures
        ):
            start = ru.datetime_between(
                self.rng, *self._window_span()
            )
            start = ru.ensure_minute_aligned(start)
            duration = ru.pick(self.rng, [45, 60, 90])
            maintenance = TDMSMaintenance(
                asset_id=asset.id,
                failure_id=None,
                maintenance_type=MAINTENANCE_TYPES[asset.id % len(MAINTENANCE_TYPES)],
                planned_date=start,
                start_date=start,
                end_date=start + timedelta(minutes=duration),
                status="PLANNED",
                remarks=f"{MARKER} synthetic orphan TDMS maintenance (no linked failure).",
            )
            self.db.add(maintenance)
            self.db.flush()
            created += 1
        return created