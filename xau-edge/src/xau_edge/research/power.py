"""Statistical power arithmetic for the research console (roadmap section 5.1 and 13.3).

Minimum detectable mean net R per trade, one-sided, i.i.d. approximation:
``(z(1 - 0.05/K) + z(power)) * sd / sqrt(n)``. It is an optimistic lower bound (the real
criteria use a day-block bootstrap and six more conditions). The same formula will back
``evaluation/power.py``.
"""

from __future__ import annotations

import math
from statistics import NormalDist

DEFAULT_SD = 1.3
DEFAULT_POWER = 0.8
UNDERPOWERED_MDE = 0.20
BASE_ALPHA = 0.05
_NORMAL = NormalDist()


def _check(k: int, n: int, sd: float, power: float) -> None:
    if k < 1 or n < 1 or not math.isfinite(sd) or sd <= 0 or not 0 < power < 1:
        msg = "k and n must be >= 1, sd > 0 and 0 < power < 1"
        raise ValueError(msg)


def mde(k: int, n: int, sd: float = DEFAULT_SD, power: float = DEFAULT_POWER) -> float:
    """Smallest mean net R per trade the test can detect with the given power."""
    _check(k, n, sd, power)
    z_alpha = _NORMAL.inv_cdf(1 - BASE_ALPHA / k)
    return (z_alpha + _NORMAL.inv_cdf(power)) * sd / math.sqrt(n)


def trades_needed(
    k: int, effect: float, sd: float = DEFAULT_SD, power: float = DEFAULT_POWER
) -> int:
    """Trades needed to detect ``effect`` R per trade."""
    _check(k, 1, sd, power)
    if not math.isfinite(effect) or effect <= 0:
        msg = "effect must be > 0"
        raise ValueError(msg)
    z_alpha = _NORMAL.inv_cdf(1 - BASE_ALPHA / k)
    return math.ceil(((z_alpha + _NORMAL.inv_cdf(power)) * sd / effect) ** 2)


def underpowered(
    k: int,
    n: int,
    sd: float = DEFAULT_SD,
    power: float = DEFAULT_POWER,
    cap: float = UNDERPOWERED_MDE,
) -> bool:
    """True if the MDE is above ``cap`` (the roadmap's "underpowered by design" rule)."""
    return mde(k, n, sd, power) > cap
