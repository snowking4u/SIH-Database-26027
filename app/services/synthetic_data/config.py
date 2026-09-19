"""STEP 11 configuration: scale profiles, scenario overrides and run config.

Everything in this module is deterministic-safe configuration. The actual
random number generator is created from ``seed`` so the same configuration
always produces the same dataset.

DO NOT model production railway behaviour here. Values are documented
starting targets for a synthetic research dataset only.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

GENERATOR_VERSION = "STEP11-1.0"
MARKER = "SYNTHETIC_STEP11"
EXPECTED_ALEMBIC_HEAD = "e1a9c2f3b7d5"

DEFAULT_MANIFEST_NAME = "synthetic_dataset_manifest.json"


@dataclass(frozen=True)
class ScaleProfile:
    """Documented starting targets for a synthetic dataset scale.

    Values are the *target* volume the generator aims for; final counts are
    reported in the manifest and may differ slightly because the pipeline is
    relationship-driven (e.g. one planning task per maintenance requirement).
    """

    key: str
    assets: int
    trains: int
    inspections: int
    defects: int
    maintenance: int
    stations: int
    lines_per_station: int
    days: int
    resources: int
    dependency_rate: float
    description: str


SCALE_PROFILES: dict[str, ScaleProfile] = {
    "tiny": ScaleProfile(
        key="tiny",
        assets=10,
        trains=10,
        inspections=30,
        defects=10,
        maintenance=10,
        stations=3,
        lines_per_station=2,
        days=7,
        resources=6,
        dependency_rate=0.4,
        description="Minimal end-to-end dataset (tests + smoke runs).",
    ),
    "small": ScaleProfile(
        key="small",
        assets=100,
        trains=100,
        inspections=500,
        defects=150,
        maintenance=200,
        stations=10,
        lines_per_station=2,
        days=30,
        resources=40,
        dependency_rate=0.6,
        description="Small realistic dataset for local verification runs.",
    ),
    "medium": ScaleProfile(
        key="medium",
        assets=1000,
        trains=1000,
        inspections=10000,
        defects=3000,
        maintenance=4000,
        stations=40,
        lines_per_station=3,
        days=90,
        resources=200,
        dependency_rate=0.7,
        description="Medium dataset (large memory/disk, slow inserts).",
    ),
    "large": ScaleProfile(
        key="large",
        assets=10000,
        trains=10000,
        inspections=100000,
        defects=30000,
        maintenance=40000,
        stations=120,
        lines_per_station=3,
        days=365,
        resources=600,
        dependency_rate=0.8,
        description="Large dataset. Dry-run only in the default workflow.",
    ),
}

VALID_SCENARIOS = [
    "normal",
    "high_defect_load",
    "multi_department",
    "window_shortage",
    "resource_shortage",
    "dependency_conflict",
    "power_block_required",
    "traffic_block_required",
    "mixed",
]

# Window templates are (occupancy_start, occupancy_end) minutes-from-midnight
# pairs for one calendar day on one line. Between the occupied intervals the
# derivation service emits AVAILABLE windows. "tight" leaves barely any gaps.
WINDOW_TEMPLATE_NORMAL = [
    (0, 480),     # 00:00-08:00 occupied
    (570, 780),   # 09:30-13:00 occupied
    (900, 1140),  # 15:00-19:00 occupied
    (1260, 1440),  # 21:00-24:00 occupied
]
WINDOW_TEMPLATE_TIGHT = [
    (0, 420),     # 00:00-07:00
    (450, 1080),  # 07:30-18:00
    (1110, 1440),  # 18:30-24:00
]
WINDOW_TEMPLATE_VERY_TIGHT = [
    (0, 300),
    (330, 720),
    (750, 1080),
    (1110, 1440),
]


@dataclass(frozen=True)
class ScenarioConfig:
    """Deterministic behavioural adjustments for a scenario.

    Multipliers adjust the scale profile's documented totals; they never
    invent railway values. ``window_template``/``resource_factor`` change how
    much availability or resource data the generator produces.
    """

    key: str
    description: str
    defect_multiplier: float = 1.0
    severe_ratio: float = 0.25
    inspection_multiplier: float = 1.0
    window_template: str = "normal"
    resource_factor: float = 1.0
    dependency_rate: float = 0.0
    power_block_ratio: float = 0.0
    traffic_block_ratio: float = 0.0
    station_spread: float = 1.0


SCENARIOS: dict[str, ScenarioConfig] = {
    "normal": ScenarioConfig(
        key="normal",
        description="Baseline realistic distribution across TMS/TDMS/SMMS.",
        defect_multiplier=1.0,
        severe_ratio=0.25,
        inspection_multiplier=1.0,
        window_template="normal",
        resource_factor=1.0,
        dependency_rate=0.6,
        power_block_ratio=0.05,
        traffic_block_ratio=0.05,
    ),
    "high_defect_load": ScenarioConfig(
        key="high_defect_load",
        description="Elevated defect/failure density and severity share.",
        defect_multiplier=2.6,
        severe_ratio=0.6,
        inspection_multiplier=1.5,
        window_template="normal",
        resource_factor=1.0,
        dependency_rate=0.7,
        power_block_ratio=0.1,
        traffic_block_ratio=0.1,
    ),
    "multi_department": ScenarioConfig(
        key="multi_department",
        description="Work spread across many stations/departments.",
        defect_multiplier=1.0,
        severe_ratio=0.25,
        inspection_multiplier=1.0,
        window_template="normal",
        resource_factor=1.4,
        dependency_rate=0.6,
        power_block_ratio=0.05,
        traffic_block_ratio=0.05,
        station_spread=1.6,
    ),
    "window_shortage": ScenarioConfig(
        key="window_shortage",
        description="Reduced operational availability (fewer/short windows).",
        defect_multiplier=1.0,
        severe_ratio=0.25,
        inspection_multiplier=1.0,
        window_template="tight",
        resource_factor=1.0,
        dependency_rate=0.6,
        power_block_ratio=0.1,
        traffic_block_ratio=0.1,
    ),
    "resource_shortage": ScenarioConfig(
        key="resource_shortage",
        description="Scarce planning resources (many tasks UNAVAILABLE).",
        defect_multiplier=1.0,
        severe_ratio=0.25,
        inspection_multiplier=1.0,
        window_template="normal",
        resource_factor=0.4,
        dependency_rate=0.6,
        power_block_ratio=0.05,
        traffic_block_ratio=0.05,
    ),
    "dependency_conflict": ScenarioConfig(
        key="dependency_conflict",
        description="Dense task ordering dependencies.",
        defect_multiplier=1.0,
        severe_ratio=0.25,
        inspection_multiplier=1.0,
        window_template="tight",
        resource_factor=1.0,
        dependency_rate=1.6,
        power_block_ratio=0.1,
        traffic_block_ratio=0.1,
    ),
    "power_block_required": ScenarioConfig(
        key="power_block_required",
        description="Many tasks require power block access.",
        defect_multiplier=1.0,
        severe_ratio=0.25,
        inspection_multiplier=1.0,
        window_template="normal",
        resource_factor=1.0,
        dependency_rate=0.6,
        power_block_ratio=0.8,
        traffic_block_ratio=0.05,
    ),
    "traffic_block_required": ScenarioConfig(
        key="traffic_block_required",
        description="Many tasks require traffic block access.",
        defect_multiplier=1.0,
        severe_ratio=0.25,
        inspection_multiplier=1.0,
        window_template="normal",
        resource_factor=1.0,
        dependency_rate=0.6,
        power_block_ratio=0.05,
        traffic_block_ratio=0.8,
    ),
    "mixed": ScenarioConfig(
        key="mixed",
        description="Random blend of every scenario behaviour.",
        defect_multiplier=1.4,
        severe_ratio=0.35,
        inspection_multiplier=1.1,
        window_template="mixed",
        resource_factor=0.9,
        dependency_rate=0.9,
        power_block_ratio=0.3,
        traffic_block_ratio=0.3,
    ),
}


@dataclass
class SyntheticConfig:
    """Resolved configuration for one dataset generation run."""

    seed: int
    scale: str
    days: int
    start_date: date
    scenario: str
    batch_size: int
    export_dir: Path | None = None
    with_optimization: bool = False
    write_manifest: bool = True
    manifest_path: Path = field(default_factory=lambda: Path(DEFAULT_MANIFEST_NAME))
    profile: ScaleProfile = field(init=False)
    scenario_config: ScenarioConfig = field(init=False)
    rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.scale not in SCALE_PROFILES:
            raise ValueError(
                f"Unknown scale {self.scale!r}. Valid scales: {sorted(SCALE_PROFILES)}"
            )
        if self.scenario not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario {self.scenario!r}. Valid scenarios: {VALID_SCENARIOS}"
            )
        if self.days < 1:
            raise ValueError("days must be >= 1")
        if self.seed < 0:
            raise ValueError("seed must be >= 0")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.profile = SCALE_PROFILES[self.scale]
        self.scenario_config = SCENARIOS[self.scenario]
        self.rng = random.Random(self.seed)

    def window_template(self) -> list[tuple[int, int]]:
        key = self.scenario_config.window_template
        if key == "mixed":
            rng = random.Random(self.seed ^ 0x5EED)
            return rng.choice(
                [WINDOW_TEMPLATE_NORMAL, WINDOW_TEMPLATE_TIGHT, WINDOW_TEMPLATE_VERY_TIGHT]
            )
        return {
            "normal": WINDOW_TEMPLATE_NORMAL,
            "tight": WINDOW_TEMPLATE_TIGHT,
            "very_tight": WINDOW_TEMPLATE_VERY_TIGHT,
        }[key]

    def module_rng(self, salt: int) -> random.Random:
        """Stage-local RNG seeded from the run seed plus a fixed salt.

        Each pipeline stage draws from its own stream, so re-running over an
        already-populated database reproduces the same decisions without
        depending on the global consumption order.
        """
        return random.Random((self.seed + salt) & 0xFFFFFFFF)

    # ------------------------------------------------------------------ #
    # Derived synthetic-data volume targets
    # ------------------------------------------------------------------ #
    @property
    def asset_count(self) -> int:
        return self.profile.assets

    @property
    def train_count(self) -> int:
        return self.profile.trains

    @property
    def station_count(self) -> int:
        return max(
            1,
            round(self.profile.stations * self.scenario_config.station_spread),
        )

    @property
    def line_count(self) -> int:
        return self.station_count * self.profile.lines_per_station

    @property
    def inspection_count(self) -> int:
        return round(
            self.profile.inspections * self.scenario_config.inspection_multiplier
        )

    @property
    def defect_count(self) -> int:
        return round(
            self.profile.defects * self.scenario_config.defect_multiplier
        )

    @property
    def maintenance_count(self) -> int:
        return max(self.profile.maintenance, self.defect_count)

    @property
    def resource_count(self) -> int:
        return max(
            2,
            round(self.profile.resources * self.scenario_config.resource_factor),
        )

    @property
    def dependency_rate(self) -> float:
        return self.scenario_config.dependency_rate

    def configuration_summary(self) -> dict:
        return {
            "seed": self.seed,
            "scale": self.scale,
            "days": self.days,
            "start_date": self.start_date.isoformat(),
            "scenario": self.scenario,
            "batch_size": self.batch_size,
            "with_optimization": self.with_optimization,
            "window_template": self.scenario_config.window_template,
            "targets": {
                "assets": self.asset_count,
                "trains": self.train_count,
                "inspections": self.inspection_count,
                "defects": self.defect_count,
                "maintenance": self.maintenance_count,
                "stations": self.station_count,
                "resources": self.resource_count,
            },
        }