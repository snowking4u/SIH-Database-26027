"""STEP 11 synthetic data generator package.

Reusable, deterministic pipeline that builds clearly-marked synthetic railway
maintenance/planning data using the existing models and services. See
``dataset_generator.run_pipeline`` for the entry point and the CLI at
``backend/scripts/generate_synthetic_data.py``.
"""

from __future__ import annotations

from .candidate_generator import generate_candidates
from .cleanup import cleanup_synthetic
from .coa_generator import CoaData, CoaGenerator
from .config import (
    GENERATOR_VERSION,
    MARKER,
    SCALE_PROFILES,
    SCENARIOS,
    VALID_SCENARIOS,
    SyntheticConfig,
)
from .dataset_generator import run_pipeline, table_counts
from .master_generator import MasterGenerator
from .optimization_generator import generate_optimization_placeholder
from .planning_generator import PlanningGenerator
from .random_utils import make_rng
from .scenarios import SCENARIO_KEYS
from .smms_generator import SmmsGenerator
from .tdms_generator import TdmsGenerator
from .tms_generator import TMSGenerator
from .unified_generator import UnifiedGenerator
from .verification import verify_synthetic

__all__ = [
    "GENERATOR_VERSION",
    "MARKER",
    "SCALE_PROFILES",
    "SCENARIOS",
    "VALID_SCENARIOS",
    "SCENARIO_KEYS",
    "SyntheticConfig",
    "make_rng",
    "CoaData",
    "CoaGenerator",
    "MasterGenerator",
    "TMSGenerator",
    "TdmsGenerator",
    "SmmsGenerator",
    "UnifiedGenerator",
    "PlanningGenerator",
    "generate_candidates",
    "generate_optimization_placeholder",
    "run_pipeline",
    "table_counts",
    "cleanup_synthetic",
    "verify_synthetic",
]