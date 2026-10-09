"""Triple-barrier labels with gross-at-mid and net R, both directions at every bar (roadmap 11).

Frozen constants of the programme (not parameters): target +2a, stop -1a, timeout 24 H1 bars, entry
at the next bar's open, both barriers inside one bar means the stop first (pessimistic) with the
optimistic outcome recorded next to it. ``a`` is the ATR14 at the decision bar's close; 1R = 1a.

Costs follow Programme 1 so results are comparable: spread = max(recorded, 30) points at entry and
exit (half each way), slippage 3 points per fill (base) or 6 (pessimistic), swap from ``CostModel``
(current terminal values, a documented pessimistic anachronism for old years) per New York 17:00
rollover on Monday to Friday.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from xau_edge.research_v2.frame import H1Frame, weekday_of_key

UP_MULT = 2.0
DN_MULT = 1.0
HORIZON = 24
MAX_ENTRY_GAP_US = 90 * 60 * 1_000_000
SPREAD_FLOOR = 30.0
POINT = 0.01
SLIP_BASE = 3.0
SLIP_PESS = 6.0
SWAP_LONG = -76.05
SWAP_SHORT = -4.2


@dataclass(frozen=True)
class Outcomes:
    """Per decision bar, for long (0) and short (1): everything needed by every analysis."""

    valid: NDArray[np.bool_]
    gross_mid: NDArray[np.float64]
    net_base: NDArray[np.float64]
    net_pess: NDArray[np.float64]
    optimistic_gross: NDArray[np.float64]
    ambiguous: NDArray[np.bool_]
    label: NDArray[np.int8]
    """+1 target, -1 stop, 0 timeout."""
    exit_idx: NDArray[np.int64]
    bars_held: NDArray[np.int64]
    mfe: NDArray[np.float64]
    mae: NDArray[np.float64]
    entry_gap: NDArray[np.bool_]


def _nights(key_entry: int, key_exit: int) -> int:
    if key_exit <= key_entry:
        return 0
    ks = np.arange(key_entry + 1, key_exit + 1, dtype=np.int64)
    return int(np.sum(weekday_of_key(ks) < 5))


def _scan(  # noqa: PLR0917
    f: H1Frame, d: int, direction: int, up: float, dn: float, horizon: int
) -> tuple[float, float, int, bool, float, float, int] | None:
    """(gross_mid_r, optimistic_gross_r, label, ambiguous, mfe, mae, exit_idx) or None."""
    e = d + 1
    a = f.atr[d]
    if e >= f.n or not np.isfinite(a) or a <= 0:
        return None
    p0 = f.o[e]
    target = p0 + direction * up * a
    stop = p0 - direction * dn * a
    unit = dn * a
    last = min(e + horizon - 1, f.n - 1)
    mfe = mae = 0.0
    for j in range(e, last + 1):
        hi, lo = f.h[j], f.low[j]
        fav = (hi - p0) if direction > 0 else (p0 - lo)
        adv = (p0 - lo) if direction > 0 else (hi - p0)
        mfe, mae = max(mfe, fav), max(mae, adv)
        hit_t = hi >= target if direction > 0 else lo <= target
        hit_s = lo <= stop if direction > 0 else hi >= stop
        if hit_t or hit_s:
            ambiguous = hit_t and hit_s
            gap_stop = (f.o[j] <= stop) if direction > 0 else (f.o[j] >= stop)
            stop_px = f.o[j] if (j > e and gap_stop) else stop
            pess = direction * (stop_px - p0) / unit if hit_s else up / dn
            opt = up / dn if hit_t else pess
            return pess, opt, (-1 if hit_s else 1), ambiguous, mfe / unit, mae / unit, j
    px = f.c[last]
    r = direction * (px - p0) / unit
    return r, r, 0, False, mfe / unit, mae / unit, last


def compute_outcomes(
    f: H1Frame, *, up: float = UP_MULT, dn: float = DN_MULT, horizon: int = HORIZON
) -> tuple[Outcomes, Outcomes]:
    """Outcomes for every bar taken long and short (valid where a trade could be formed)."""
    n = f.n
    longs, shorts = (_empty(n), _empty(n))
    for d in range(n - 1):
        gap = f.t[d + 1] - f.t[d] > MAX_ENTRY_GAP_US
        for out, direction in ((longs, 1), (shorts, -1)):
            if gap:
                out.entry_gap[d] = True
                continue
            res = _scan(f, d, direction, up, dn, horizon)
            if res is None:
                continue
            gross, opt, label, amb, mfe, mae, ex = res
            e = d + 1
            unit = dn * f.atr[d]
            nights = _nights(int(f.day[e]), int(f.day[ex]))
            swap = (SWAP_LONG if direction > 0 else SWAP_SHORT) * POINT * nights
            spread = (max(f.spread[e], SPREAD_FLOOR) + max(f.spread[ex], SPREAD_FLOOR)) / 2 * POINT
            base_cost = spread + 2 * SLIP_BASE * POINT
            pess_cost = spread + 2 * SLIP_PESS * POINT
            out.valid[d] = True
            out.gross_mid[d] = gross
            out.optimistic_gross[d] = opt
            out.net_base[d] = gross - base_cost / unit + swap / unit
            out.net_pess[d] = gross - pess_cost / unit + swap / unit
            out.ambiguous[d] = amb
            out.label[d] = label
            out.exit_idx[d] = ex
            out.bars_held[d] = ex - e + 1
            out.mfe[d] = mfe
            out.mae[d] = mae
    return longs, shorts


def _empty(n: int) -> Outcomes:
    return Outcomes(
        valid=np.zeros(n, dtype=bool),
        gross_mid=np.full(n, np.nan),
        net_base=np.full(n, np.nan),
        net_pess=np.full(n, np.nan),
        optimistic_gross=np.full(n, np.nan),
        ambiguous=np.zeros(n, dtype=bool),
        label=np.zeros(n, dtype=np.int8),
        exit_idx=np.zeros(n, dtype=np.int64),
        bars_held=np.zeros(n, dtype=np.int64),
        mfe=np.full(n, np.nan),
        mae=np.full(n, np.nan),
        entry_gap=np.zeros(n, dtype=bool),
    )
