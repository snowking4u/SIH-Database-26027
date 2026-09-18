"""STEP 11 synthetic SMMS source data: signal/maintenance inspections, alerts,
maintenance.

Maintainer fields are deliberately non-personal synthetic values: names from
a fixed pool, a fixed designation, and a deterministic non-realistic mobile
number (``9`` + 9 digits) via ``random_utils.synthetic_mobile``.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.smms_alert import SMMSAlert
from app.models.smms_inspection import SMMSInspection
from app.models.smms_maintenance import SMMSMaintenance

from . import random_utils as ru
from .config import MARKER, SyntheticConfig
from .master_generator import AssetInfo

INSPECTION_TYPES = ["SIGNAL_AUDIT", "RELAY_CHECK", "PANEL_CHECK", "CIRCUIT_CHECK"]
ALERT_TYPES = [
    "SMMS-ALT-001",
    "SMMS-ALT-002",
    "SMMS-ALT-003",
    "SMMS-ALT-004",
]
FEEDBACK_CODES = ["FB-OK", "FB-PENDING", "FB-CORRECTED"]
ALERT_STATUSES = ["NEW", "ASSIGNED", "NEW", "ASSIGNED", "RESOLVED"]
CAUSE_CODES = ["CAUSE-ELEC", "CAUSE-MECH", "CAUSE-CIRCUIT", "CAUSE-UNKNOWN"]
MAINTENANCE_TYPES = [
    "SIGNAL_RESET",
    "RELAY_REPLACEMENT",
    "WIRING_RECTIFICATION",
    "PANEL_INSPECTION",
]

MAINTAINER_NAMES = [
    "MAINTAINER-ALPHA",
    "MAINTAINER-BRAVO",
    "MAINTAINER-CHARLIE",
    "MAINTAINER-DELTA",
]
MAINTAINER_DESIGNATIONS = [
    "TECHNICIAN",
    "ASSISTANT_ENGINEER",
    "SUPERVISOR",
]


class SmmsGenerator:
    def __init__(self, db: Session, cfg: SyntheticConfig, assets: list[AssetInfo]):
        self.db = db
        self.cfg = cfg
        self.rng: random.Random = cfg.module_rng(0x5)
        self.assets = assets

    def generate(self) -> dict:
        stats = {"inspections": 0, "alerts": 0, "maintenance": 0}
        per_asset_inspections = ru.distribution(
            self.cfg.inspection_count, len(self.assets), self.rng
        )
        per_asset_alerts = ru.distribution(
            self.cfg.defect_count, len(self.assets), self.rng
        )
        for idx, asset in enumerate(self.assets):
            if self._has_existing(asset.id):
                continue
            stats["inspections"] += self._inspections_for(asset, per_asset_inspections[idx])
            stats["alerts"] += self._alerts_for(asset, per_asset_alerts[idx])
            stats["maintenance"] += self._maintenance_for(asset)
        self.db.commit()
        return stats

    def _has_existing(self, asset_id: int) -> bool:
        return (
            self.db.scalar(
                select(SMMSInspection.id).where(
                    SMMSInspection.asset_id == asset_id,
                    SMMSInspection.remarks.like(f"%{MARKER}%"),
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

    def _inspection_for(self, asset: AssetInfo, day_offset: int) -> SMMSInspection:
        when = ru.day_start(self.cfg.start_date, day_offset) + timedelta(
            minutes=ru.int_between(self.rng, 30, 540)
        )
        inspection = SMMSInspection(
            asset_id=asset.id,
            inspection_date=when,
            inspection_type=INSPECTION_TYPES[asset.id % len(INSPECTION_TYPES)],
            parameter_code=f"SMMS-PARAM-{asset.id % 4 + 1}",
            parameter_value=str(ru.int_between(self.rng, 1, 30)),
            remarks=f"{MARKER} synthetic SMMS inspection.",
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

    def _alerts_for(self, asset: AssetInfo, count: int) -> int:
        created = 0
        for i in range(count):
            inspection = self.db.scalar(
                select(SMMSInspection)
                .where(SMMSInspection.asset_id == asset.id)
                .order_by(SMMSInspection.inspection_date)
            )
            incidence = (
                ru.day_start(self.cfg.start_date, min(self.cfg.days - 1, i % max(1, self.cfg.days)))
                + timedelta(minutes=ru.int_between(self.rng, 30, 720))
                if inspection is None
                else inspection.inspection_date
                + timedelta(minutes=ru.int_between(self.rng, 30, 300))
            )
            if incidence >= ru.day_start(self.cfg.start_date, self.cfg.days):
                incidence = ru.day_start(self.cfg.start_date, self.cfg.days) - timedelta(minutes=60)
            rectified = (
                incidence + timedelta(minutes=ru.int_between(self.rng, 30, 240))
                if ru.rand_boolean(self.rng, 0.5)
                else None
            )
            if rectified and rectified >= ru.day_start(self.cfg.start_date, self.cfg.days):
                rectified = None
            duration = rectified - incidence if rectified else None
            alert = SMMSAlert(
                asset_id=asset.id,
                inspection_id=inspection.id if inspection else None,
                alert_type_code=ALERT_TYPES[asset.id % len(ALERT_TYPES)],
                alert_feedback_code=ru.pick(self.rng, FEEDBACK_CODES),
                alert_status_code=ru.pick(self.rng, ALERT_STATUSES),
                cause_code=CAUSE_CODES[asset.id % len(CAUSE_CODES)],
                incidence_date_time=incidence,
                rectification_date_time=rectified,
                incidence_duration=duration,
                alert_feedback_date_time=incidence + timedelta(minutes=10),
                remarks=f"{MARKER} synthetic SMMS alert.",
                maintainer_name=MAINTAINER_NAMES[asset.id % len(MAINTAINER_NAMES)],
                maintainer_designation=MAINTAINER_DESIGNATIONS[
                    asset.id % len(MAINTAINER_DESIGNATIONS)
                ],
                maintainer_mobile=ru.synthetic_mobile(self.rng),
            )
            self.db.add(alert)
            self.db.flush()
            created += 1
        return created

    def _maintenance_for(self, asset: AssetInfo) -> int:
        alerts = self.db.scalars(
            select(SMMSAlert)
            .where(SMMSAlert.asset_id == asset.id)
            .order_by(SMMSAlert.id)
        ).all()
        created = 0
        for alert in alerts:
            start = alert.incidence_date_time + timedelta(
                minutes=ru.int_between(self.rng, 60, 600)
            )
            duration = ru.pick(self.rng, [30, 45, 60, 90, 120])
            end = start + timedelta(minutes=duration)
            last = ru.day_start(self.cfg.start_date, self.cfg.days)
            if end >= last:
                start = last - timedelta(minutes=duration + 10)
                end = start + timedelta(minutes=duration)
            missing_end = ru.rand_boolean(self.rng, 0.03)
            maintenance = SMMSMaintenance(
                asset_id=asset.id,
                alert_id=alert.id,
                maintenance_type=MAINTENANCE_TYPES[asset.id % len(MAINTENANCE_TYPES)],
                planned_date=start,
                start_date=start,
                end_date=None if missing_end else end,
                status="PLANNED",
                remarks=(
                    f"{MARKER} synthetic SMMS maintenance for {alert.alert_type_code}; "
                    f"planned duration {duration} minutes."
                ),
            )
            self.db.add(maintenance)
            self.db.flush()
            created += 1
        return created