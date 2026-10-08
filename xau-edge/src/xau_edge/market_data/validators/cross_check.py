"""Compare two bar frames (for example derived vs broker-supplied) without repairing either."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

import polars as pl

DEFAULT_COLUMNS: Final = (
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)
_PRICE_COLUMNS: Final = frozenset({"open", "high", "low", "close"})
_MAX_SAMPLES: Final = 5


@dataclass(frozen=True)
class CrossCheckReport:
    """Outcome of comparing ``derived`` with ``reference`` on shared timestamps."""

    matched: int
    only_in_derived: int
    only_in_reference: int
    mismatches: dict[str, int] = field(default_factory=dict)
    sample: dict[str, tuple[datetime, ...]] = field(default_factory=dict)

    @property
    def exact(self) -> bool:
        """True when both frames cover the same timestamps and no column differs."""
        return not self.mismatches and not self.only_in_derived and not self.only_in_reference


def cross_check(
    derived: pl.DataFrame,
    reference: pl.DataFrame,
    *,
    price_tolerance: float = 0.0,
    columns: tuple[str, ...] = DEFAULT_COLUMNS,
) -> CrossCheckReport:
    """Join on ``timestamp`` and count per-column differences.

    Prices may differ by up to ``price_tolerance``; other columns must be equal (nulls compare
    equal to nulls). Rows present on only one side are counted separately.
    """
    ref = reference.select("timestamp", *columns).rename({c: f"{c}__ref" for c in columns})
    joined = derived.select("timestamp", *columns).join(ref, on="timestamp", how="inner")

    mismatches: dict[str, int] = {}
    sample: dict[str, tuple[datetime, ...]] = {}
    for col in columns:
        a, b = pl.col(col), pl.col(f"{col}__ref")
        differs = (a - b).abs() > price_tolerance if col in _PRICE_COLUMNS else ~a.eq_missing(b)
        bad = joined.filter(differs.fill_null(True))
        if bad.height:
            mismatches[col] = bad.height
            sample[col] = tuple(bad["timestamp"].head(_MAX_SAMPLES).to_list())

    return CrossCheckReport(
        matched=joined.height,
        only_in_derived=derived.join(
            reference.select("timestamp"), on="timestamp", how="anti"
        ).height,
        only_in_reference=reference.join(
            derived.select("timestamp"), on="timestamp", how="anti"
        ).height,
        mismatches=mismatches,
        sample=sample,
    )
