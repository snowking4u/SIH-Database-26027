"""STEP 11 COA/CTC source generator: trains, schedules, movements, occupancy.

A deterministic per-line "day template" of occupied intervals is produced for
every calendar day; the existing derivation service then turns the gaps into
``available_window`` rows. The generator exposes the same gaps so TMS/TDMS/
SMMS block requirements can target exactly those intervals (block assignment
is still done by the downstream planning layer, never invented by COA data).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.line_occupancy import LineOccupancy
from app.models.operational_event import OperationalEvent
from app.models.source_system import SourceSystem
from app.models.train import Train
from app.models.train_movement import TrainMovement
from app.models.train_schedule import TrainSchedule

from . import random_utils as ru
from .config import MARKER, SyntheticConfig
from .master_generator import line_number, station_code


@dataclass(frozen=True)
class GapSlot:
    """A derived "available" gap for a (station, line, day) pair."""

    day: datetime
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class CoaData:
    combos: list[tuple[str, str]] = field(default_factory=list)
    slots: dict[tuple[str, str], dict[int, list[GapSlot]]] = field(
        default_factory=dict
    )
    trains: list[Train] = field(default_factory=list)

    def gaps_for(self, scode: str, lcode: str, day_index: int) -> list[GapSlot]:
        return self.slots.get((scode, lcode), {}).get(day_index, [])


class CoaGenerator:
    def __init__(self, db: Session, cfg: SyntheticConfig):
        self.db = db
        self.cfg = cfg
        self.rng: random.Random = cfg.module_rng(0x2)

    # ------------------------------------------------------------------ #
    # Core generation
    # ------------------------------------------------------------------ #
    def generate(self) -> CoaData:
        combos: list[tuple[str, str]] = []
        for station in range(self.cfg.station_count):
            for line in range(self.cfg.profile.lines_per_station):
                combos.append(
                    (station_code(station), line_number(station, line))
                )

        day_offsets = range(self.cfg.days)

        trains = self._generate_trains(combos)
        self._trains = trains
        self._preload_existing_ids()
        combo_trains = self._map_trains_to_combos(trains, combos)
        self.slots = self._build_slots(combos, day_offsets)
        self._generate_occupancy(combos, day_offsets, combo_trains)
        self._generate_schedules(combos, day_offsets, combo_trains)
        self._generate_movements(combos, day_offsets, combo_trains)
        self._generate_events(combos, day_offsets, combo_trains)
        self.db.commit()

        return CoaData(combos=combos, slots=self.slots, trains=trains)

    def _preload_existing_ids(self) -> None:
        """Load source-event/schedule ids already stored for this generator.

        A single read per table lets every insert be a deterministic
        get-or-skip, so rerunning with the same seed is idempotent.
        """
        prefix = "SYN-COA-"
        self._occupied_ids = set(
            self.db.scalars(
                select(LineOccupancy.source_event_id).where(
                    LineOccupancy.source_event_id.startswith(prefix)
                )
            ).all()
        )
        self._sched_ids = set(
            self.db.scalars(
                select(TrainSchedule.source_schedule_id).where(
                    TrainSchedule.source_schedule_id.startswith(prefix)
                )
            ).all()
        )
        self._mov_ids = set(
            self.db.scalars(
                select(TrainMovement.source_event_id).where(
                    TrainMovement.source_event_id.startswith(prefix)
                )
            ).all()
        )
        self._evt_ids = set(
            self.db.scalars(
                select(OperationalEvent.source_event_id).where(
                    OperationalEvent.source_event_id.startswith(prefix)
                )
            ).all()
        )

    def _map_trains_to_combos(
        self, trains: list[Train], combos: list[tuple[str, str]]
    ) -> dict[tuple[str, str], list[Train]]:
        mapping: dict[tuple[str, str], list[Train]] = {}
        for n, train in enumerate(trains):
            mapping.setdefault(combos[n % len(combos)], []).append(train)
        return mapping

    # ------------------------------------------------------------------ #
    # Day template
    # ------------------------------------------------------------------ #
    def _template_gaps(self, day_start: datetime) -> list[tuple[datetime, datetime]]:
        template = self.cfg.window_template()
        gaps: list[tuple[datetime, datetime]] = []
        for prev, nxt in zip(template, template[1:]):
            gap_start = day_start + timedelta(minutes=prev[1])
            gap_end = day_start + timedelta(minutes=nxt[0])
            if gap_end > gap_start:
                gaps.append((gap_start, gap_end))
        return gaps

    def _occupied_intervals(self, day_start: datetime) -> list[tuple[datetime, datetime]]:
        template = self.cfg.window_template()
        return [
            (day_start + timedelta(minutes=start), day_start + timedelta(minutes=end))
            for start, end in template
        ]

    def _build_slots(
        self, combos: list[tuple[str, str]], day_offsets
    ) -> dict[tuple[str, str], dict[int, list[GapSlot]]]:
        slots: dict[tuple[str, str], dict[int, list[GapSlot]]] = {}
        for scode, lcode in combos:
            by_day: dict[int, list[GapSlot]] = {}
            for day in day_offsets:
                day_start = ru.day_start(self.cfg.start_date, day)
                by_day[day] = [
                    GapSlot(day=day_start, start=gap[0], end=gap[1])
                    for gap in self._template_gaps(day_start)
                ]
            slots[(scode, lcode)] = by_day
        return slots

    # ------------------------------------------------------------------ #
    # Datasets
    # ------------------------------------------------------------------ #
    def _generate_trains(self, combos: list[tuple[str, str]]) -> list[Train]:
        cfg = self.cfg
        source = self._source_system()
        existing = {
            t.train_id: t
            for t in self.db.scalars(
                select(Train).where(
                    Train.source_system_id == source.id,
                    Train.train_id.startswith("SYN-TRAIN-"),
                )
            ).all()
        }
        trains: list[Train] = []
        rows: list[Train] = []
        count = 0
        for n in range(cfg.train_count):
            train_id = f"SYN-TRAIN-{n + 1:06d}"
            train = existing.get(train_id)
            if train is None:
                train = Train(
                    train_id=train_id,
                    train_number=f"SYN{n + 1:04d}",
                    train_name=f"Synthetic Train {n + 1}",
                    schedule_date=cfg.start_date,
                    start_date=ru.day_start(cfg.start_date, 0),
                    loco_number=f"SYN-LOCO-{n % 50 + 1}",
                    direction="UP" if n % 2 == 0 else "DOWN",
                    source_system_id=source.id,
                )
                rows.append(train)
            trains.append(train)
            count += 1
            if count % cfg.batch_size == 0 and rows:
                self.db.add_all(rows)
                rows.clear()
                self.db.flush()
        if rows:
            self.db.add_all(rows)
            self.db.flush()
        return trains

    def _train_for(
        self,
        combo_trains: dict[tuple[str, str], list[Train]],
        scode: str,
        lcode: str,
        day: int,
    ) -> Train | None:
        trains = combo_trains.get((scode, lcode))
        if not trains:
            return None
        return trains[day % len(trains)]

    def _generate_occupancy(
        self,
        combos: list[tuple[str, str]],
        day_offsets,
        combo_trains: dict[tuple[str, str], list[Train]],
    ):
        cfg = self.cfg
        rows: list[LineOccupancy] = []
        count = 0
        for scode, lcode in combos:
            for day in day_offsets:
                day_start = ru.day_start(cfg.start_date, day)
                for interval_index, (start, end) in enumerate(
                    self._occupied_intervals(day_start)
                ):
                    status = "BLOCKED" if interval_index % 5 == 4 else "OCCUPIED"
                    train = self._train_for(combo_trains, scode, lcode, day)
                    source_event_id = (
                        f"SYN-COA-OCC-{scode}-{lcode}-{day:04d}-{interval_index}"
                    )
                    if source_event_id in self._occupied_ids:
                        continue
                    rows.append(
                        LineOccupancy(
                            station_code=scode,
                            line_number=lcode,
                            occupancy_start=start,
                            occupancy_end=end,
                            occupancy_status=status,
                            train_id=train.id if train is not None else None,
                            source_event_id=source_event_id,
                            remarks=f"{MARKER} synthetic line occupancy.",
                        )
                    )
                    count += 1
                    if count % cfg.batch_size == 0:
                        self.db.add_all(rows)
                        rows.clear()
                        self.db.flush()
        if rows:
            self.db.add_all(rows)
            self.db.flush()

    def _generate_schedules(
        self,
        combos: list[tuple[str, str]],
        day_offsets,
        combo_trains: dict[tuple[str, str], list[Train]],
    ):
        cfg = self.cfg
        rows: list[TrainSchedule] = []
        count = 0
        for scode, lcode in combos:
            for day in day_offsets:
                train = self._train_for(combo_trains, scode, lcode, day)
                if train is None:
                    continue
                source_schedule_id = (
                    f"SYN-COA-SCH-{scode}-{lcode}-{day:04d}"
                )
                if source_schedule_id in self._sched_ids:
                    continue
                day_start = ru.day_start(cfg.start_date, day)
                first_start, first_end = self._occupied_intervals(day_start)[0]
                arrival = first_start + timedelta(minutes=5)
                departure = arrival + timedelta(minutes=10)
                if departure >= first_end:
                    departure = first_end - timedelta(minutes=1)
                rows.append(
                    TrainSchedule(
                        train_id=train.id,
                        station_code=scode,
                        scheduled_arrival=arrival,
                        scheduled_departure=departure,
                        scheduled_run_through=None,
                        sequence_number=1,
                        line_number=lcode,
                        source_schedule_id=source_schedule_id,
                        remarks=f"{MARKER} synthetic timetable entry.",
                    )
                )
                count += 1
                if count % cfg.batch_size == 0:
                    self.db.add_all(rows)
                    rows.clear()
                    self.db.flush()
        if rows:
            self.db.add_all(rows)
            self.db.flush()

    def _generate_movements(
        self,
        combos: list[tuple[str, str]],
        day_offsets,
        combo_trains: dict[tuple[str, str], list[Train]],
    ):
        cfg = self.cfg
        rows: list[TrainMovement] = []
        count = 0
        train_combo = {
            train.id: combo
            for combo, trains in combo_trains.items()
            for train in trains
        }
        for train in self._trains:
            scode, lcode = train_combo[train.id]
            for day in day_offsets:
                day_start = ru.day_start(cfg.start_date, day)
                first_start = self._occupied_intervals(day_start)[0][0]
                arrival = first_start + timedelta(minutes=2)
                departure = arrival + timedelta(minutes=12)
                arr_id = f"SYN-COA-MOV-{train.train_id}-{day:04d}-A"
                dep_id = f"SYN-COA-MOV-{train.train_id}-{day:04d}-D"
                if arr_id in self._mov_ids and dep_id in self._mov_ids:
                    continue
                rows.append(
                    TrainMovement(
                        train_id=train.id,
                        station_code=scode,
                        movement_flag="A",
                        movement_datetime=arrival,
                        line_number=lcode,
                        source_event_id=arr_id,
                        remarks=f"{MARKER} synthetic arrival movement.",
                    )
                )
                rows.append(
                    TrainMovement(
                        train_id=train.id,
                        station_code=scode,
                        movement_flag="D",
                        movement_datetime=departure,
                        line_number=lcode,
                        source_event_id=dep_id,
                        remarks=f"{MARKER} synthetic departure movement.",
                    )
                )
                count += 2
                if count % cfg.batch_size == 0:
                    self.db.add_all(rows)
                    rows.clear()
                    self.db.flush()
        if rows:
            self.db.add_all(rows)
            self.db.flush()

    def _generate_events(
        self,
        combos: list[tuple[str, str]],
        day_offsets,
        combo_trains: dict[tuple[str, str], list[Train]],
    ):
        cfg = self.cfg
        rows: list[OperationalEvent] = []
        count = 0
        train_combo = {
            train.id: combo
            for combo, trains in combo_trains.items()
            for train in trains
        }
        for train in self._trains:
            scode, lcode = train_combo[train.id]
            for day in day_offsets[:3]:
                day_start = ru.day_start(cfg.start_date, day)
                event_dt = day_start + timedelta(hours=ru.int_between(self.rng, 6, 20))
                source_event_id = f"SYN-COA-EVT-{train.train_id}-{day}"
                if source_event_id in self._evt_ids:
                    continue
                rows.append(
                    OperationalEvent(
                        train_id=train.id,
                        station_code=scode,
                        event_type="SYNTHETIC_OPERATIONAL",
                        event_datetime=event_dt,
                        description=(
                            f"{MARKER} synthetic operational event for {train.train_id}."
                        ),
                        source_event_id=source_event_id,
                        remarks=f"{MARKER} synthetic event.",
                    )
                )
                count += 1
                if count % cfg.batch_size == 0:
                    self.db.add_all(rows)
                    rows.clear()
                    self.db.flush()
        if rows:
            self.db.add_all(rows)
            self.db.flush()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _source_system(self) -> SourceSystem:
        source = self.db.scalar(
            select(SourceSystem).where(SourceSystem.system_code == "COA")
        )
        if source is None:
            raise RuntimeError(
                "STEP 11 requires the COA source system; run "
                "scripts/seed_master_data.py first."
            )
        return source