"""STEP 11 block-requirement synthesis from normalized maintenance data.

Turns normalized maintenance requirements into ``block_requirement`` records
that point at the exact derived operationally-available gap produced by the COA
generator, so downstream candidate evaluation has genuinely feasible inputs.
No AI/optimization: block assignments are deterministic source-derived data.
"""

from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.block_requirement import BlockRequirement
from app.models.maintenance_requirement import MaintenanceRequirement

from . import random_utils as ru
from .coa_generator import CoaData
from .config import MARKER, SyntheticConfig

NO_BLOCK_RATIO = 0.05


class UnifiedGenerator:
    def __init__(
        self,
        db: Session,
        cfg: SyntheticConfig,
        coa: CoaData,
        asset_map: dict[int, tuple[str, str]],
    ):
        self.db = db
        self.cfg = cfg
        self.rng: random.Random = cfg.rng
        self.coa = coa
        self.asset_map = asset_map

    def generate(self) -> dict:
        stats = {"requirements_processed": 0, "block_requirements_created": 0,
                 "skipped_no_block_edge": 0, "skipped_existing": 0}
        requirements = self.db.scalars(
            select(MaintenanceRequirement).order_by(MaintenanceRequirement.id)
        ).all()
        for mr in requirements:
            stats["requirements_processed"] += 1
            has_block = self.db.scalar(
                select(BlockRequirement).where(
                    BlockRequirement.maintenance_requirement_id == mr.id
                ).limit(1)
            )
            if has_block is not None:
                stats["skipped_existing"] += 1
                continue
            if self._no_block_edge(mr):
                stats["skipped_no_block_edge"] += 1
                continue
            self._create_block_requirement(mr)
            stats["block_requirements_created"] += 1
        self.db.commit()
        return stats

    # ------------------------------------------------------------------ #
    def _no_block_edge(self, mr: MaintenanceRequirement) -> bool:
        """Deterministic small share of MRs intentionally left without a BR."""
        return ru.rand_boolean(self.rng, NO_BLOCK_RATIO)

    def _location_for(self, asset_id: int) -> tuple[str, str] | None:
        return self.asset_map.get(asset_id)

    def _choose_gap(self, mr: MaintenanceRequirement, scode: str, lcode: str):
        gaps = self.coa.gaps_for(scode, lcode, mr.id % max(1, self.cfg.days))
        if not gaps:
            for combo in self.coa.combos:
                cand = self.coa.gaps_for(
                    combo[0], combo[1], mr.id % max(1, self.cfg.days)
                )
                if cand:
                    scode, lcode = combo
                    gaps = cand
                    break
        if not gaps:
            return None, None, None
        slot = gaps[mr.id % len(gaps)]
        return scode, lcode, slot

    def _create_block_requirement(self, mr: MaintenanceRequirement) -> None:
        location = self._location_for(mr.asset_id)
        if location is None:
            return
        scode, lcode = location
        scode, lcode, slot = self._choose_gap(mr, scode, lcode)
        if slot is None:
            return

        power = ru.rand_boolean(self.rng, self.cfg.scenario_config.power_block_ratio)
        traffic = ru.rand_boolean(self.rng, self.cfg.scenario_config.traffic_block_ratio)
        if power and traffic:
            traffic = False
        block_type = (
            "POWER_ONLY"
            if power
            else "TRAFFIC_ONLY"
            if traffic
            else "NORMAL"
        )
        self.db.add(
            BlockRequirement(
                maintenance_requirement_id=mr.id,
                station_code=scode,
                line_number=lcode,
                block_type=block_type,
                required_duration_minutes=mr.required_duration_minutes,
                earliest_start=slot.start,
                latest_end=slot.end,
                power_block_required=power,
                traffic_block_required=traffic,
                resource_notes=f"{MARKER} synthetic resource-requirement note.",
                status="PENDING",
                remarks=f"{MARKER} synthetic block requirement.",
            )
        )