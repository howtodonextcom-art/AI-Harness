"""Which datasets a DESCRIPTIVE pattern study may read. The default answer is no.

Classes: SYNTHETIC (generated), BURNED (already consumed by outcome tests of other hypotheses; its
outcome value is spent, so descriptive, outcome-free statistics add no new contamination of it),
RESERVED (untouched for outcomes and kept clean for a future honest evaluation), LOCKED (Test-H and
Holdout), FORBIDDEN (contains locked data). Anything not listed is UNKNOWN and refused.

Precedent for descriptive use of Development-2 before any outcome: ``event-counts-dev2.json`` of
Edge Program V2 (decision D-2, frequency counts only). That precedent is the only authority used
here; it is not a general permission and it does not extend to outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

DEV2_START = datetime(2011, 1, 1, tzinfo=UTC)
DEV2_END = datetime(2019, 1, 1, tzinfo=UTC)


class ForbiddenDatasetError(PermissionError):
    """A dataset that is locked, reserved, forbidden or unknown was requested."""


@dataclass(frozen=True)
class DatasetPolicy:
    name: str
    classification: str
    descriptive_allowed: bool
    reason: str


POLICY: dict[str, DatasetPolicy] = {
    p.name: p
    for p in (
        DatasetPolicy(
            "random_walk", "SYNTHETIC", True, "generated in memory; no market information"
        ),
        DatasetPolicy(
            "dev2_h1",
            "BURNED",
            True,
            "Development-2 2011-01-01..2018-12-31 was consumed by Batch A (V2) and F1/F3 (V3) "
            "Stage 1 outcome tests; counts-only use has the precedent event-counts-dev2.json (D-2)",
        ),
        DatasetPolicy(
            "val2_h1",
            "RESERVED",
            False,
            "Validation-2 2019-2021 has no Stage 1 survivor, so it is untouched and is the "
            "cleanest data left for an honest future evaluation; looking at it would spend it",
        ),
        DatasetPolicy("testH", "LOCKED", False, "Test-H 2022-01-01..2025-04-30; freeze guard"),
        DatasetPolicy("holdout", "LOCKED", False, "Holdout 2026-05-01..2026-10-07; freeze guard"),
        DatasetPolicy(
            "ftmo_2025_plus",
            "FORBIDDEN",
            False,
            "data/raw/XAUUSD starts 2025-05-01 and runs to 2026-10-07, so it contains the Holdout",
        ),
        DatasetPolicy(
            "live_market",
            "FORBIDDEN",
            False,
            "data/market is the live ledger and includes Holdout dates",
        ),
    )
}


def require_descriptive(name: str) -> DatasetPolicy:
    """The policy for ``name`` if a descriptive study may read it, else raise."""
    policy = POLICY.get(name)
    if policy is None:
        raise ForbiddenDatasetError(f"dataset {name!r} is UNKNOWN: not used")
    if not policy.descriptive_allowed:
        raise ForbiddenDatasetError(f"dataset {name!r} is {policy.classification}: {policy.reason}")
    return policy


def load_dev2_h1(parquet: Path) -> pl.DataFrame:
    """Development-2 H1 bars only. The filter is applied inside the scan, so bars at or after
    2019-01-01 (Validation-2, Test-H) are never materialised, and the result is asserted."""
    require_descriptive("dev2_h1")
    frame = (
        pl.scan_parquet(parquet)
        .filter((pl.col("timestamp") >= DEV2_START) & (pl.col("timestamp") < DEV2_END))
        .select("timestamp", "open", "high", "low", "close")
        .sort("timestamp")
        .collect()
    )
    if frame.height == 0:
        raise ForbiddenDatasetError("no Development-2 bars found in the file")
    latest = frame.select(pl.col("timestamp").max()).item()
    if latest is None or latest >= DEV2_END:  # pragma: no cover - the filter makes this unreachable
        raise ForbiddenDatasetError("a bar at or after the Development-2 end was loaded")
    return frame


def block_shuffled_null(
    h: np.ndarray,
    lo: np.ndarray,
    c: np.ndarray,
    seed: int,
    block: int,  # type: ignore[type-arg,unused-ignore]
) -> tuple[np.ndarray, ...]:  # type: ignore[type-arg,unused-ignore]
    """Rebuild a series from the same bars cut into blocks and re-ordered at random.

    Each bar keeps its log-return and its own high/low shape, and consecutive bars inside a block
    stay together (so short-range volatility clustering survives); what is destroyed is the order of
    the blocks, i.e. any longer-range price structure. A frequency reference, not an outcome
    model."""
    ret = np.diff(np.log(c))
    up = np.log(h[1:] / c[1:])
    down = np.log(c[1:] / lo[1:])
    n = ret.size
    starts = np.arange(0, n, block)
    order = np.random.default_rng(seed).permutation(len(starts))
    index = np.concatenate([np.arange(starts[k], min(starts[k] + block, n)) for k in order])
    close = c[0] * np.exp(np.concatenate([[0.0], np.cumsum(ret[index])]))
    high = close.copy()
    low = close.copy()
    high[1:] = close[1:] * np.exp(up[index])
    low[1:] = close[1:] * np.exp(-down[index])
    return high, low, close
