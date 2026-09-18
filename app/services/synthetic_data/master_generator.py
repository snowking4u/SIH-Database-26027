"""STEP 11 master data generator: synthetic locations, assets, parameters.

All synthetic business identifiers use a deterministic ``SYN-*`` prefix and
every row with a free-text field carries the ``SYNTHETIC_STEP11`` marker so
marker-based cleanup never touches real master data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import AssetMaster
from app.models.asset_parameter import AssetParameter
from app.models.location import LocationMaster
from app.models.source_system import SourceSystem

from . import random_utils as ru
from .config import MARKER, SyntheticConfig

ASSET_TYPES = [
    "TRACK",
    "SIGNAL",
    "OCS",
    "BRIDGE",
    "LEVEL_CROSSING",
    "TRACK_CIRCUIT",
    "POINT_MACHINE",
]

ZONE_NAMES = [
    "SYNTHETIC NORTHERN ZONE",
    "SYNTHETIC SOUTHERN ZONE",
    "SYNTHETIC EASTERN ZONE",
]

STATUSES = ["IN_SERVICE", "IN_SERVICE", "IN_SERVICE", "UNDER_MAINTENANCE"]

PARAMETER_POOL = [
    ("RAIL_WEAR_MM", "Rail head wear", "mm"),
    ("TUBE_DEFLECTION_MM", "Tube deflection", "mm"),
    ("POINT_FRICTION_N", "Point friction force", "N"),
    ("SIGNAL_LAMP_LUX", "Signal lamp intensity", "lux"),
    ("CONTACT_WIRE_HT_MM", "Contact wire height", "mm"),
    ("BRIDGE_CRACK_WIDTH_MM", "Bridge crack width", "mm"),
]


@dataclass
class AssetInfo:
    id: int
    station_idx: int
    line_idx: int
    station_code: str
    line_number: str
    asset_type: str
    source_system_code: str
    installation_date: date
    status: str


def station_code(station_idx: int) -> str:
    return f"SYN-ST{station_idx + 1:03d}"


def line_number(station_idx: int, line_idx: int) -> str:
    return f"SYN-L{station_idx * 10 + line_idx + 1:03d}"


def asset_id(n: int) -> str:
    return f"SYN-ASSET-{n + 1:06d}"


class MasterGenerator:
    """Generate synthetic location_master, asset_master and asset_parameter."""

    PRIMARY_CHAIN = ["TMS", "TDMS", "SMMS"]

    def __init__(self, db: Session, cfg: SyntheticConfig):
        self.db = db
        self.cfg = cfg
        self.rng: random.Random = cfg.module_rng(0x1)

    # ------------------------------------------------------------------ #
    # Locations
    # ------------------------------------------------------------------ #
    def generate_locations(self) -> list[LocationMaster]:
        cfg = self.cfg
        locations: list[LocationMaster] = []
        rng = self.rng
        for station in range(cfg.station_count):
            zone_name = ZONE_NAMES[station % len(ZONE_NAMES)]
            zone_code = f"SYN-ZONE-{station % len(ZONE_NAMES) + 1}"
            division_code = f"SYN-DIV-{station + 1}"
            section_code = f"SYN-SEC-{station + 1}"
            for line in range(cfg.profile.lines_per_station):
                km_start = ru.int_between(rng, 0, 120)
                locations.append(
                    LocationMaster(
                        zone_code=zone_code,
                        zone_name=f"{zone_name} (STEP 11 SYNTHETIC)",
                        division_code=division_code,
                        division_name=f"Synthetic Division {station + 1}",
                        section_code=section_code,
                        section_name=f"Synthetic Section {station + 1}",
                        station_code=station_code(station),
                        station_name=f"Synthetic Station {station + 1:03d}",
                        line_code=line_number(station, line),
                        line_name=f"Synthetic Line {line + 1}",
                        km_start=km_start,
                        km_end=km_start + ru.int_between(rng, 20, 60),
                        latitude=20.0 + station * 0.1,
                        longitude=71.0 + line * 0.1,
                    )
                )
        existing = set(
            self.db.scalars(
                select(LocationMaster.station_code).where(
                    LocationMaster.station_code.like("SYN-ST%")
                )
            ).all()
        )
        fresh = [loc for loc in locations if loc.station_code not in existing]
        if fresh:
            self.db.add_all(fresh)
            self.db.flush()
        return fresh

    # ------------------------------------------------------------------ #
    # Assets
    # ------------------------------------------------------------------ #
    def generate_assets(self, locations: list[LocationMaster]) -> list[AssetInfo]:
        cfg = self.cfg
        sources = self._source_systems()
        existing = {
            (ssid, asset_code)
            for ssid, asset_code in self.db.execute(
                select(
                    AssetMaster.source_system_id, AssetMaster.source_asset_id
                ).where(AssetMaster.source_asset_id.like("SYN-%"))
            ).all()
        }

        infos: list[AssetInfo] = []
        rows: list[AssetMaster] = []
        meta: list[tuple] = []
        count = 0
        for n in range(cfg.asset_count):
            source = sources[self.PRIMARY_CHAIN[n % len(self.PRIMARY_CHAIN)]]
            sid = asset_id(n)
            if (source.id, sid) in existing:
                count += 1
                continue
            station = n % cfg.station_count
            line = (n // cfg.station_count) % cfg.profile.lines_per_station
            scode = station_code(station)
            lcode = line_number(station, line)
            raw_type = ASSET_TYPES[n % len(ASSET_TYPES)]
            ins_date = ru.datetime_between(
                self.rng,
                datetime(cfg.start_date.year - 20, 1, 1),
                datetime(cfg.start_date.year - 1, 12, 31),
                minute_step=1440,
            ).date()
            status = STATUSES[n % len(STATUSES)]
            asset = AssetMaster(
                source_system_id=source.id,
                source_asset_id=sid,
                asset_type=raw_type,
                asset_subtype=f"{raw_type}-MODEL-{n % 5}",
                asset_name=f"Synthetic {raw_type.lower().replace('_', ' ')} {n + 1}",
                location_id=locations[n % len(locations)].id,
                installation_date=ins_date,
                status=status,
                remarks=(
                    f"{MARKER} Synthetic master asset; source={source.system_code} "
                    f"station={scode} line={lcode}."
                ),
            )
            rows.append(asset)
            meta.append((station, line, raw_type, source.system_code, ins_date, status))
            count += 1
            if count % cfg.batch_size == 0:
                infos.extend(self._flush_asset_batch(rows, meta))
        if rows:
            infos.extend(self._flush_asset_batch(rows, meta))
        return infos

    def _flush_asset_batch(
        self, rows: list[AssetMaster], meta: list[tuple]
    ) -> list[AssetInfo]:
        # Flush assigns primary keys; AssetInfo requires a real asset id.
        self.db.add_all(rows)
        self.db.flush()
        infos: list[AssetInfo] = []
        while rows:
            asset = rows.pop(0)
            station, line, raw_type, sys_code, ins_date, status = meta.pop(0)
            infos.append(
                AssetInfo(
                    id=asset.id,
                    station_idx=station,
                    line_idx=line,
                    station_code=station_code(station),
                    line_number=line_number(station, line),
                    asset_type=raw_type,
                    source_system_code=sys_code,
                    installation_date=ins_date,
                    status=status,
                )
            )
        return infos

    def generate_parameters(self, infos: list[AssetInfo]) -> int:
        cfg = self.cfg
        sources = self._source_systems()
        rows: list[AssetParameter] = []
        count = 0
        for info in infos:
            if ru.rand_boolean(self.rng, probability=0.6):
                continue
            code, name, unit = PARAMETER_POOL[info.station_idx % len(PARAMETER_POOL)]
            recorded = datetime.combine(info.installation_date, time(0, 0)) + timedelta(
                days=self.rng.randrange(0, 400)
            )
            rows.append(
                AssetParameter(
                    asset_id=info.id,
                    source_system_id=sources[info.source_system_code].id,
                    parameter_code=code,
                    parameter_name=name,
                    parameter_value=ru.int_between(self.rng, 2, 40),
                    unit=unit,
                    recorded_date=recorded,
                )
            )
            count += 1
            if count % cfg.batch_size == 0:
                self.db.flush()
        if rows:
            self.db.add_all(rows)
            self.db.flush()
        return count

    def generate(self) -> dict:
        locations = self.generate_locations()
        infos = self.generate_assets(locations)
        param_count = self.generate_parameters(infos)
        return {
            "locations": len(locations),
            "assets": len(infos),
            "asset_parameters": param_count,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _source_systems(self) -> dict[str, SourceSystem]:
        rows = self.db.scalars(
            select(SourceSystem).where(
                SourceSystem.system_code.in_(["TMS", "TDMS", "SMMS"])
            )
        ).all()
        if len(rows) != 3:
            raise RuntimeError(
                "STEP 11 requires TMS/TDMS/SMMS source systems; run "
                "scripts/seed_master_data.py first."
            )
        return {row.system_code: row for row in rows}