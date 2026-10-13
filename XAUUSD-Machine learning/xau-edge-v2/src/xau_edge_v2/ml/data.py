"""Read the H1 history for ML V0 (read-only; never past the open window)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from xau_edge_v2.data.bar_store import MAX_LIMIT, BarStore
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.ml.features import Bars
from xau_edge_v2.ml.guard import DEV_UNTIL, Unlock, require_development_window

EARLIEST = datetime(2004, 1, 1, tzinfo=UTC)


def load_h1(root: Path, until: datetime = DEV_UNTIL, *, unlock: Unlock | None = None) -> Bars:
    """Closed H1 bars with open time ``< until``.

    ``until`` beyond the development window needs an ``Unlock`` (see ``guard.issue_unlock``).
    """
    if unlock is None:
        require_development_window(until)
    store = BarStore(root)
    parts: list[np.ndarray] = []
    cursor = EARLIEST
    while cursor < until:
        frame = store.window(Timeframe.H1, cursor, until, MAX_LIMIT)
        if frame.height == 0:
            break
        parts.append(
            np.column_stack(
                [
                    frame["timestamp"].dt.epoch("s").to_numpy().astype(np.float64),
                    frame["high"].to_numpy(),
                    frame["low"].to_numpy(),
                    frame["close"].to_numpy(),
                ]
            )
        )
        last = datetime.fromtimestamp(float(parts[-1][-1, 0]), UTC)
        cursor = last + timedelta(seconds=1)
        if frame.height < MAX_LIMIT:
            break
    if not parts:
        return Bars(np.zeros(0, dtype=np.int64), np.zeros(0), np.zeros(0), np.zeros(0))
    data = np.concatenate(parts)
    return Bars(data[:, 0].astype(np.int64), data[:, 1], data[:, 2], data[:, 3])


def dataset_hash(bars: Bars) -> str:
    """sha256 of the bars used (times, high, low, close): the registry's ``dataset_hash``."""
    h = hashlib.sha256()
    for arr in (bars.open_s, bars.high, bars.low, bars.close):
        h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()
