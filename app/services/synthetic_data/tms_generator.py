"""STEP 11 synthetic TMS source data: inspections, defects, maintenance.

Each defect points back at one inspection and each maintenance record points
back at one defect, preserving the source observation chain that the unified
layer normalizes later. All timestamps stay inside the configured window and
maintain inspection < defect < maintenance ordering.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tms_defect import TMSDefect
from app.models.tms_inspection import TMSInspection
from app.models.tms_maintenance import TMSMaintenance

from . import random_utils as ru
from .config import MARKER, SyntheticConfig
from .master_generator import AssetInfo

INSPECTION_TYPES = ["USFD", "UT", "WEST", "THERMOVISION", "RAIL_WEAR"]

DEFECT_CODES = [
    "TMS-DEF-001",
    "TMS-DEF-002",
    "TMS-DEF-003",
    "TMS-DEF-004",
]

MAINTENANCE_TYPES = [
    "REPLACEMENT",
    "REPAIR",
    "LUBRICATION",
    "ADJUSTMENT",
    "RESTORATION",
]

SEVERITIES = ["LOW", "MEDIUM", "HIGH"]
STATUSES = ["OPEN", "OPEN", "PENDING_REVIEW"]


class TMSGenerator:
    def __init__(self, db: Session, cfg: SyntheticConfig, assets: list[AssetInfo]):
        self.db = db
        self.cfg = cfg
        self.rng: random.Random = cfg.module_rng(0x3)
        self.assets = assets

    def generate(self) -> dict:
        stats = {"inspections": 0, "defects": 0, "maintenance": 0}
        per_asset_inspections = ru.distribution(
            self.cfg.inspection_count, len(self.assets), self.rng
        )
        defects_per_asset = ru.distribution(
            self.cfg.defect_count, len(self.assets), self.rng
        )
        for idx, asset in enumerate(self.assets):
            if self._has_existing(asset.id):
                continue
            stats["inspections"] += self._inspections_for(asset, per_asset_inspections[idx])
            defects = self._defects_for(asset, defects_per_asset[idx])
            stats["defects"] += defects
            stats["maintenance"] += self._maintenance_for(asset, defects)
        self.db.commit()
        return stats

    def _has_existing(self, asset_id: int) -> bool:
        return (
            self.db.scalar(
                select(TMSInspection.id).where(
                    TMSInspection.asset_id == asset_id,
                    TMSInspection.remarks.like(f"%{MARKER}%"),
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

    def _inspection_for(self, asset: AssetInfo) -> TMSInspection:
        start, end = self._window_span()
        idx = asset.id % 1000
        day_offset = min(self.cfg.days - 1, idx % max(1, self.cfg.days))
        when = ru.day_start(self.cfg.start_date, day_offset) + timedelta(
            minutes=ru.int_between(self.rng, 30, 540)
        )
        inspection = TMSInspection(
            asset_id=asset.id,
            inspection_date=when,
            inspection_type=INSPECTION_TYPES[asset.id % len(INSPECTION_TYPES)],
            parameter_code=f"TMS-PARAM-{asset.id % 6 + 1}",
            parameter_value=ru.int_between(self.rng, 1, 60),
            remarks=f"{MARKER} synthetic TMS inspection.",
        )
        self.db.add(inspection)
        self.db.flush()
        return inspection

    def _inspections_for(self, asset: AssetInfo, count: int) -> int:
        created = 0
        for i in range(count):
            insp = self._inspection_for(asset)
            created += 1
        return created

    def _defects_for(self, asset: AssetInfo, defect_count: int) -> int:
        insp = self.db.scalar(
            select(TMSInspection)
            .where(TMSInspection.asset_id == asset.id)
            .order_by(TMSInspection.inspection_date)
        )
        created = 0
        for _ in range(defect_count):
            if insp is None:
                break
            detected = insp.inspection_date + timedelta(
                minutes=ru.int_between(self.rng, 30, 300)
            )
            if detected >= ru.day_start(self.cfg.start_date, self.cfg.days):
                detected = insp.inspection_date
            severity = (
                "HIGH"
                if ru.rand_boolean(self.rng, self.cfg.scenario_config.severe_ratio)
                else ru.pick(self.rng, SEVERITIES)
            )
            defect = TMSDefect(
                asset_id=asset.id,
                inspection_id=insp.id,
                defect_code=DEFECT_CODES[asset.id % len(DEFECT_CODES)],
                defect_description=(
                    f"{MARKER} synthetic TMS defect observed on {insp.inspection_date.isoformat()}."
                ),
                severity=severity,
                detected_date=detected,
                status=ru.pick(self.rng, STATUSES),
                remarks=f"{MARKER} synthetic TMS defect.",
            )
            self.db.add(defect)
            self.db.flush()
            created += 1
        return created

    def _maintenance_for(self, asset: AssetInfo, defects: int) -> int:
        defects_rows = self.db.scalars(
            select(TMSDefect)
            .where(TMSDefect.asset_id == asset.id)
            .order_by(TMSDefect.id)
        ).all()
        created = 0
        for defect in defects_rows:
            start = defect.detected_date + timedelta(
                minutes=ru.int_between(self.rng, 60, 600)
            )
            duration = ru.pick(self.rng, [30, 45, 60, 90, 120])
            end = start + timedelta(minutes=duration)
            if end >= ru.day_start(self.cfg.start_date, self.cfg.days):
                start = ru.day_start(self.cfg.start_date, self.cfg.days) - timedelta(
                    minutes=duration + 10
                )
                end = start + timedelta(minutes=duration)
            # ~3% of records intentionally lack an end date so the unified
            # layer sees an unknown duration (edge case coverage).
            missing_end = ru.rand_boolean(self.rng, 0.03)
            maintenance = TMSMaintenance(
                asset_id=asset.id,
                defect_id=defect.id,
                maintenance_type=MAINTENANCE_TYPES[asset.id % len(MAINTENANCE_TYPES)],
                planned_date=start,
                start_date=start,
                end_date=None if missing_end else end,
                status="PLANNED",
                remarks=(
                    f"{MARKER} synthetic TMS maintenance for {defect.defect_code}; "
                    f"planned duration {duration} minutes."
                ),
            )
            self.db.add(maintenance)
            self.db.flush()
            created += 1
        return created