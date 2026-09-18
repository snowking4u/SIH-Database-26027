"""STEP 11 scenarios: deterministic behavioural overrides for a dataset run.

Scenario definitions live in ``config.SCENARIOS``; this module re-exports the
public scenario API so callers can use either import location. Scenarios only
change *how much* synthetic data is produced; they never invent railway
values that are not already supported by the existing deterministic services.
"""

from __future__ import annotations

from .config import SCENARIOS, VALID_SCENARIOS, ScenarioConfig

__all__ = ["SCENARIOS", "VALID_SCENARIOS", "ScenarioConfig"]

SCENARIO_KEYS = list(VALID_SCENARIOS)