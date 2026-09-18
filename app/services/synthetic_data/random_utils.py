"""Deterministic random helpers backed by ``random.Random(seed)``.

Every function takes the run's ``rng`` explicitly. Nothing here uses the
global ``random`` module, so identical configuration reproduces identical
synthetic source data.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta


def make_rng(seed: int) -> random.Random:
    return random.Random(seed)


def int_between(rng: random.Random, low: int, high: int) -> int:
    """Uniform int in [low, high] inclusive."""
    return rng.randint(low, high)


def weighted_pick(rng: random.Random, choices: dict[str, float]):
    """Pick a key from ``choices`` using the given relative weights."""
    total = sum(choices.values())
    pick = rng.uniform(0.0, total)
    upto = 0.0
    for key, weight in choices.items():
        upto += weight
        if pick <= upto:
            return key
    return max(choices, key=choices.get)


def pick(rng: random.Random, seq: list):
    return seq[rng.randrange(len(seq))]


def datetime_between(
    rng: random.Random,
    start: datetime,
    end: datetime,
    *,
    minute_step: int = 5,
) -> datetime:
    span = int((end - start).total_seconds() // 60)
    if span <= 0:
        return start
    offset = rng.randrange(0, span + 1, max(1, minute_step))
    return start + timedelta(minutes=offset)


def ensure_minute_aligned(value: datetime, minute_step: int = 5) -> datetime:
    total = (value.hour * 60 + value.minute) // minute_step * minute_step
    return value.replace(
        hour=total // 60,
        minute=total % 60,
        second=0,
        microsecond=0,
    )


def clone_minute_aligned(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def rand_boolean(rng: random.Random, probability: float) -> bool:
    return rng.random() < probability


def synthetic_mobile(rng: random.Random) -> str:
    """Synthetic, obviously non-realistic mobile number.

    Format ``7XX000XXXX``-style would risk collision with real numbers; a
    plain invented ``9`` prefix plus random digits is used and documented as
    synthetic. Never copied from real employee records.
    """
    return "9" + "".join(str(rng.randrange(0, 10)) for _ in range(9))


def distribution(defect_count: int, assets: int, rng: random.Random) -> list[int]:
    """Split ``defect_count`` defect slots across ``assets``.

    Deterministic per (count, assets, rng): start with one per asset then
    randomly add the remainder. Always returns exactly ``assets`` entries.
    """
    if assets <= 0:
        return []
    per = [1] * min(defect_count, assets)
    per.extend([0] * (assets - len(per)))
    remaining = defect_count - sum(per)
    for _ in range(remaining):
        per[rng.randrange(0, assets)] += 1
    return per


def date_span(start_date: date, days: int) -> tuple[date, date]:
    return start_date, start_date + timedelta(days=days - 1)


def utc_midnight(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def day_start(start_date: date, day_index: int) -> datetime:
    return datetime.combine(start_date + timedelta(days=day_index), time(0, 0))