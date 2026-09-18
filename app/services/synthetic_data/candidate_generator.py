"""STEP 11 candidate-window generation.

Strictly delegates to the existing STEP 9 service ``generate_candidate_windows``
so the synthetic pipeline reuses the same deterministic rules (and the same
idempotency) as the rest of the application. This module exists to keep the
pipeline staged and observable; it adds no new logic.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.candidate_window import generate_candidate_windows

from .config import SyntheticConfig


def generate_candidates(db: Session, cfg: SyntheticConfig) -> dict:
    return generate_candidate_windows(db)