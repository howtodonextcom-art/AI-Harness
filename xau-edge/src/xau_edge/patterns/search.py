"""Leakage-safe k-nearest-neighbour search over pattern windows (ADR-0013).

For a query whose window ends at bar ``q`` (``window`` bars: ``q - W + 1 .. q``) a candidate window
ending at bar ``e`` is admissible only if its OUTCOME window ``e + 1 .. e + H`` finishes before the
query window starts: ``e + H < q - W + 1``, i.e. ``e <= q - W - H``. That one rule excludes the
query itself, every window overlapping it, and every candidate whose outcome would overlap the
pattern being matched or lie in the query's future.

The search never reads beyond bar ``q``: the value array is sliced to ``q + 1`` rows before any
computation, so later data cannot influence a result even through floating-point effects.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, field_validator

from xau_edge.patterns.distances import METHODS, dtw_distance
from xau_edge.patterns.representation import window_validity, window_view

Floats = NDArray[np.float64]
_CHUNK = 4096


class SearchConfig(BaseModel):
    """Window length, the longest outcome horizon to protect, and neighbour selection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    window: int = Field(default=30, ge=2)
    horizon: int = Field(default=60, ge=1)
    k: int = Field(default=20, ge=1)
    min_separation: int | None = Field(default=None, ge=1)
    method: str = "euclidean"
    dtw_radius: int | None = Field(default=None, ge=0)

    @field_validator("method")
    @classmethod
    def _known_method(cls, value: str) -> str:
        if value not in METHODS:
            msg = f"unknown method {value!r}; choose from {sorted(METHODS)}"
            raise ValueError(msg)
        return value

    @property
    def separation(self) -> int:
        """Minimum distance in bars between two selected matches (default: the window length)."""
        return self.window if self.min_separation is None else self.min_separation


@dataclass(frozen=True)
class Match:
    """One historical analogue: the bar where its window ends and its distance to the query."""

    end_index: int
    distance: float
    rank: int


@dataclass(frozen=True)
class SearchResult:
    """Matches (best first) plus context for judging similarity quality."""

    query_end: int
    matches: tuple[Match, ...]
    n_candidates: int
    best_distance: float | None
    median_distance: float | None


class PatternIndex:
    """Search the history of a ``(bars, features)`` pattern array (rows = bars, oldest first)."""

    def __init__(self, values: Floats, config: SearchConfig | None = None) -> None:
        arr = np.asarray(values, dtype=np.float64)
        if arr.ndim != 2:
            msg = f"values must be 2-D (bars, features), got shape {arr.shape}"
            raise ValueError(msg)
        self._values = arr
        self.config = config or SearchConfig()

    def candidate_ends(self, query_end: int) -> NDArray[np.intp]:
        """Admissible end indices of candidate windows for a query ending at ``query_end``."""
        cfg = self.config
        last = query_end - cfg.window - cfg.horizon
        first = cfg.window - 1
        if last < first:
            return np.empty(0, dtype=np.intp)
        return np.arange(first, last + 1, dtype=np.intp)

    def search(
        self, query_end: int, *, method: str | None = None, k: int | None = None
    ) -> SearchResult:
        """Find the ``k`` most similar admissible windows to the one ending at ``query_end``."""
        cfg = self.config
        name = cfg.method if method is None else method
        if k is not None and k < 1:
            msg = f"k must be >= 1, got {k}"
            raise ValueError(msg)
        if name not in METHODS:
            msg = f"unknown method {name!r}; choose from {sorted(METHODS)}"
            raise ValueError(msg)
        if not 0 <= query_end < self._values.shape[0]:
            msg = f"query_end {query_end} outside 0..{self._values.shape[0] - 1}"
            raise ValueError(msg)
        past = self._values[: query_end + 1]  # nothing after the query bar is visible below
        w = cfg.window
        if query_end < w - 1:
            msg = f"query window needs {w} bars; query_end is {query_end}"
            raise ValueError(msg)
        query = past[query_end - w + 1 : query_end + 1]
        if not np.isfinite(query).all():
            msg = "query window contains missing values"
            raise ValueError(msg)

        ends = self.candidate_ends(query_end)
        if ends.size == 0:
            return SearchResult(query_end, (), 0, None, None)
        view = window_view(past, w)
        valid = window_validity(past, w)[: ends.size]
        distances = np.full(ends.size, np.inf)
        fn = METHODS[name]
        for start in range(0, ends.size, _CHUNK):
            stop = min(start + _CHUNK, ends.size)
            chunk = np.nan_to_num(
                np.ascontiguousarray(view[start:stop]), nan=0.0, posinf=0.0, neginf=0.0
            )
            if name == "dtw":
                distances[start:stop] = dtw_distance(query, chunk, radius=cfg.dtw_radius)
            else:
                distances[start:stop] = fn(query, chunk)
        distances[~valid] = np.inf

        finite = np.isfinite(distances)
        n_valid = int(finite.sum())
        if n_valid == 0:
            return SearchResult(query_end, (), 0, None, None)
        picked = self._select(distances, ends, cfg.k if k is None else k)
        matches = tuple(
            Match(int(ends[i]), float(distances[i]), rank) for rank, i in enumerate(picked, start=1)
        )
        return SearchResult(
            query_end,
            matches,
            n_valid,
            matches[0].distance if matches else None,
            float(np.median(distances[finite])),
        )

    def _select(self, distances: Floats, ends: NDArray[np.intp], k: int) -> list[int]:
        order = np.argsort(distances, kind="stable")  # ties: earlier window first
        sep = self.config.separation
        chosen: list[int] = []
        for i in order:
            if not np.isfinite(distances[i]):
                break
            if all(abs(int(ends[i]) - int(ends[j])) >= sep for j in chosen):
                chosen.append(int(i))
                if len(chosen) == k:
                    break
        return chosen
