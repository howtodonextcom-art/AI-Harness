"""Stage B: from signals to PAPER trades, with the desk's own fill rules (no outcome is invented).

Pure NumPy. The rules are the ones in ``core/paper.py`` (entry at the executable quote plus 3 points
of adverse slippage; managed on closed M1 bars that open at or after the fill minute; stop first when
one bar reaches both levels; a stop fills with adverse slippage, a target exactly at its level; swap
ASSUMED per rollover) and the V1 governor, unchanged. Nothing is deducted twice: the planning
``net_rr`` is a gate, ``cost_R`` is a screen, and only the realised price path charges the trade.

Spec: ``docs/research/cand_v2_spec.json`` (definitions.episode, episode_to_trade, execution_timing,
management).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray

from xau_edge_v2.core.costs import SLIPPAGE_POINTS, SWAP_LONG_POINTS, SWAP_SHORT_POINTS
from xau_edge_v2.core.paper import (
    CloseRecord,
    GovernorConfig,
    OpenRecord,
    entry_fill,
    governor_check,
    rollover_nights,
)

POINT = 0.01
EPISODE_GAP = timedelta(minutes=60)
HORIZON = timedelta(days=10)
FALSE_POSITIVE_BARS = 6
BAR_M5 = timedelta(minutes=5)
EQUITY = 10_000.0
RISK_PCT = 0.25
RISK_USD = EQUITY * RISK_PCT / 100.0
_MICROS = 1_000_000


@dataclass(frozen=True)
class M1Series:
    """Closed M1 bars (bid chart), sorted by open time."""

    open_us: NDArray[np.int64]
    open: NDArray[np.float64]
    high: NDArray[np.float64]
    low: NDArray[np.float64]
    close: NDArray[np.float64]
    spread: NDArray[np.float64]


@dataclass(frozen=True)
class Resolution:
    reason: str
    exit_price: float
    exit_us: int
    bars_held: int
    ambiguous: bool
    gap: bool


@dataclass(frozen=True)
class Trade:
    variant: str
    episode: int
    opened_at: datetime
    closed_at: datetime
    side: str
    session: str
    entry_quote: float
    fill: float
    stop: float
    target: float
    exit_price: float
    reason: str
    ambiguous: bool
    gap: bool
    risk_dist: float
    r_price: float
    r_spread: float
    r_slip: float
    r_swap: float
    r_net: float
    bars_held: int
    false_positive: bool
    net_rr_plan: float
    cost_r_plan: float | None


def us(at: datetime) -> int:
    return int(at.timestamp() * _MICROS)


def resolve(
    side: str,
    stop: float,
    target: float,
    opened_us: int,
    m1: M1Series,
    *,
    horizon: timedelta = HORIZON,
) -> Resolution | None:
    """Manage the position on closed M1 bars from the fill minute; None without any later bar."""
    lo = int(np.searchsorted(m1.open_us, opened_us, side="left"))
    hi = int(
        np.searchsorted(
            m1.open_us, opened_us + int(horizon.total_seconds() * _MICROS), side="right"
        )
    )
    if hi <= lo:
        return None
    high, low, spread = m1.high[lo:hi], m1.low[lo:hi], m1.spread[lo:hi] * POINT
    slip = SLIPPAGE_POINTS * POINT
    if side == "BUY":
        stop_hit, target_hit, stop_fill = low <= stop, high >= target, stop - slip
    else:
        stop_hit, target_hit, stop_fill = high + spread >= stop, low + spread <= target, stop + slip
    i_stop = int(np.argmax(stop_hit)) if stop_hit.any() else len(high)
    i_tp = int(np.argmax(target_hit)) if target_hit.any() else len(high)
    if i_stop == len(high) and i_tp == len(high):
        last = hi - 1
        close = float(m1.close[last])
        price = close if side == "BUY" else close + float(m1.spread[last]) * POINT
        return Resolution("HORIZON", price, int(m1.open_us[last]), hi - lo, False, False)
    if i_stop <= i_tp:
        k = lo + i_stop
        bar_open = float(m1.open[k])
        gap = bar_open < stop if side == "BUY" else bar_open + float(m1.spread[k]) * POINT > stop
        return Resolution(
            "STOP_LOSS", stop_fill, int(m1.open_us[k]), i_stop + 1, i_tp == i_stop, gap
        )
    k = lo + i_tp
    return Resolution("TAKE_PROFIT", target, int(m1.open_us[k]), i_tp + 1, False, False)


def episodes(signals: Sequence[tuple[datetime, str]]) -> list[int]:
    """Episode number of each (time, side) signal (input sorted by time): same side, gaps <= 60 minutes."""
    out: list[int] = []
    last: dict[str, datetime] = {}
    current: dict[str, int] = {}
    nxt = 0
    for at, side in signals:
        if side not in last or at - last[side] > EPISODE_GAP:
            nxt += 1
            current[side] = nxt
        last[side] = at
        out.append(current[side])
    return out


def r_net(
    side: str, fill: float, exit_price: float, nights: int, risk_dist: float
) -> tuple[float, float, float]:
    """(price R, swap R, total R) of a closed trade; the price path already contains spread and slippage."""
    direction = 1 if side == "BUY" else -1
    swap_points = SWAP_LONG_POINTS if side == "BUY" else SWAP_SHORT_POINTS
    price = direction * (exit_price - fill) / risk_dist
    swap = swap_points * nights * POINT / risk_dist
    return price, swap, price + swap


@dataclass(frozen=True)
class Counters:
    signal_rows: int
    episodes: int
    attempted: int
    refused: dict[str, int]
    unresolved: int
    executed: int


def run_variant(
    variant: str,
    signals: list[dict[str, Any]],
    m1: M1Series,
    *,
    cfg: GovernorConfig | None = None,
) -> tuple[list[Trade], Counters]:
    """Episodes -> one attempt at each episode's first signal -> governor -> simulated trade."""
    cfg = cfg or GovernorConfig()
    rows = sorted(signals, key=lambda r: r["ts"])
    keys = [(r["ts"], str(r["side"])) for r in rows]
    ep_no = episodes(keys)
    seen: set[int] = set()
    trades: list[Trade] = []
    refused: dict[str, int] = {}
    unresolved = attempted = 0
    for row, ep in zip(rows, ep_no, strict=True):
        if ep in seen:
            continue
        seen.add(ep)
        attempted += 1
        now: datetime = row["ts"]
        opens = [
            OpenRecord(t.opened_at, t.session, RISK_PCT, closed=t.closed_at <= now) for t in trades
        ]
        closes = [
            CloseRecord(t.closed_at, t.r_net * RISK_USD) for t in trades if t.closed_at <= now
        ]
        day = now.astimezone(UTC).date()
        opens_today = [o for o in opens if o.opened_at.astimezone(UTC).date() == day]
        day_pnl = sum(c.pnl for c in closes if c.closed_at.astimezone(UTC).date() == day)
        codes = governor_check(
            cfg,
            now,
            str(row["session"]),
            RISK_PCT,
            opens=opens,
            opens_today=opens_today,
            closes=closes,
            day_start_equity=EQUITY,
            equity=EQUITY + day_pnl,
        )
        if codes:
            for c in codes:
                refused[c] = refused.get(c, 0) + 1
            continue
        side = str(row["side"])
        quote, stop, target = (
            float(row["entry"]),
            float(row["sl"]),
            float(row["tp"]),
        )
        fill = entry_fill("BUY" if side == "BUY" else "SELL", quote, POINT)
        res = resolve(side, stop, target, us(now), m1)
        if res is None:
            unresolved += 1
            continue
        closed_at = datetime.fromtimestamp(res.exit_us / _MICROS, UTC) + timedelta(minutes=1)
        risk = abs(quote - stop)
        nights = rollover_nights(now, closed_at)
        price_r, swap_r, total = r_net(side, fill, res.exit_price, nights, risk)
        spread_entry = (float(row["ask"]) - float(row["bid"])) / risk
        trades.append(
            Trade(
                variant=variant,
                episode=ep,
                opened_at=now,
                closed_at=closed_at,
                side=side,
                session=str(row["session"]),
                entry_quote=quote,
                fill=fill,
                stop=stop,
                target=target,
                exit_price=res.exit_price,
                reason=res.reason,
                ambiguous=res.ambiguous,
                gap=res.gap,
                risk_dist=risk,
                r_price=price_r,
                r_spread=spread_entry,
                r_slip=(SLIPPAGE_POINTS * POINT * (1 + (res.reason == "STOP_LOSS"))) / risk,
                r_swap=swap_r,
                r_net=total,
                bars_held=res.bars_held,
                false_positive=res.reason == "STOP_LOSS"
                and res.bars_held <= FALSE_POSITIVE_BARS * 5,
                net_rr_plan=float(row["net_rr"]),
                cost_r_plan=None if row.get("cost_r") is None else float(row["cost_r"]),
            )
        )
    return trades, Counters(len(rows), len(seen), attempted, refused, unresolved, len(trades))
