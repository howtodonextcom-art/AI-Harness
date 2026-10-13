"""Deterministic replay: the SAME engine on closed bars for paper, sanity backtest and parity.

``run_decisions`` calls ``build_market_state`` and ``decide`` at each decision time using only the
bars closed at that time. ``simulate`` then plays the BUY/SELL decisions forward on the M5 bars with
the position manager, one position at a time, charging the spread, the slippage and the swap-free
cost of the round trip. It is a SANITY check of the pipeline (frequency, payoff, cost sensitivity,
pathologies), never evidence of an edge: it must only be run on development (burned) data.

``parity_mismatches`` proves research/paper/demo parity: for every decision time the decision from
the full frames must equal the decision from frames truncated to what was closed at that time (what
a live process would hold). Any mismatch is a blocker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide
from xau_edge.trading.frames import MultiTfBars
from xau_edge.trading.governor import GovernorConfig, TradeGovernor
from xau_edge.trading.market_state import MarketState, StateConfig, build_market_state
from xau_edge.trading.position_manager import (
    ManagerConfig,
    ManagerContext,
    PositionState,
    apply,
    evaluate,
)
from xau_edge.trading.schema import TradeDecision, TradingSignal


@dataclass(frozen=True)
class CostAssumptions:
    """Round-trip costs of the simulated fills (points of 0.01)."""

    slippage_points: float = 3.0
    spread_multiplier: float = 1.0
    point: float = 0.01


@dataclass(frozen=True)
class ReplayTrade:
    """One simulated trade with its outcome in R and in price."""

    signal_id: str
    direction: int
    decided_at: datetime
    entry_time: datetime
    entry: float
    stop_loss: float
    take_profit: float
    exit_time: datetime
    exit_price: float
    exit_reason: str
    r_gross: float
    r_net: float
    mfe_r: float
    mae_r: float
    bars: int


@dataclass
class ReplayResult:
    """Decisions and trades of one replay."""

    decisions: list[tuple[datetime, TradingSignal]] = field(default_factory=list)
    trades: list[ReplayTrade] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {"BUY": 0, "SELL": 0, "WAIT": 0}
        for _, s in self.decisions:
            out[s.decision.value] += 1
        return out


def decision_times(
    bars: MultiTfBars, start: datetime, end: datetime, step: Timeframe = Timeframe.M5
) -> list[datetime]:
    """The close times of the ``step`` bars inside ``[start, end)`` (decisions are at closes)."""
    frame = bars.frames[step]
    closes = frame.filter((pl.col("available_at") >= start) & (pl.col("available_at") < end))
    return list(closes["available_at"].to_list())


def state_at(
    bars: MultiTfBars,
    at: datetime,
    *,
    news_state: str = "CLEAR",
    state_config: StateConfig | None = None,
) -> MarketState:
    """The market state at ``at`` using the spread of the last closed M5 bar."""
    m5 = bars.as_of(Timeframe.M5, at)
    spread = float(m5["spread"][-1]) if m5 is not None and m5.height else None
    return build_market_state(
        bars, at, spread_points=spread, news_state=news_state, config=state_config
    )


def run_decisions(
    bars: MultiTfBars,
    times: list[datetime],
    ctx: DecisionContext,
    cfg: BaselineConfig | None = None,
    *,
    news_state: str = "CLEAR",
) -> list[tuple[datetime, TradingSignal]]:
    """One decision per time, each from the bars closed at that time only."""
    return [
        (t, decide(state_at(bars, t, news_state=news_state), ctx, cfg or BaselineConfig()))
        for t in times
    ]


def parity_mismatches(
    bars: MultiTfBars,
    times: list[datetime],
    ctx: DecisionContext,
    cfg: BaselineConfig | None = None,
) -> list[datetime]:
    """Decision times where the full-frame decision differs from the live-style truncated one."""
    bad: list[datetime] = []
    cfg = cfg or BaselineConfig()
    for t in times:
        full = decide(state_at(bars, t), ctx, cfg)
        live = decide(state_at(bars.truncated(t), t), ctx, cfg)
        if full != live:
            bad.append(t)
    return bad


def _fill_cost_price(spread_points: float, costs: CostAssumptions) -> float:
    return (spread_points * costs.spread_multiplier + 2 * costs.slippage_points) * costs.point


def simulate(  # noqa: PLR0915 - one forward pass per trade
    bars: MultiTfBars,
    decisions: list[tuple[datetime, TradingSignal]],
    manager: ManagerConfig,
    *,
    costs: CostAssumptions | None = None,
    governor: GovernorConfig | None = None,
    equity: float = 100_000.0,
) -> list[ReplayTrade]:
    """Play the BUY/SELL decisions forward on M5 bars, one position at a time."""
    costs = costs or CostAssumptions()
    gov = TradeGovernor(governor or GovernorConfig())
    m5 = bars.frames[Timeframe.M5]
    opens = m5["timestamp"].to_list()
    highs = m5["high"].to_numpy()
    lows = m5["low"].to_numpy()
    open_px = m5["open"].to_numpy()
    close_px = m5["close"].to_numpy()
    spreads = m5["spread"].to_numpy().astype(np.float64)
    index_of = {t: i for i, t in enumerate(opens)}
    trades: list[ReplayTrade] = []
    busy_until: datetime | None = None
    for decided_at, signal in decisions:
        if signal.decision is TradeDecision.WAIT:
            continue
        if busy_until is not None and decided_at < busy_until:
            continue
        if gov.check(
            decided_at, "ANY", signal.risk_pct or 0.25, day_start_equity=equity, equity=equity
        ):
            continue
        start = index_of.get(decided_at)  # the M5 bar opening at the decision close
        if start is None or signal.entry_price is None or signal.stop_loss is None:
            continue
        if signal.signal_expiry is not None and decided_at > signal.signal_expiry:
            continue
        direction = 1 if signal.decision is TradeDecision.BUY else -1
        half = spreads[start] * costs.spread_multiplier * costs.point / 2
        fill = open_px[start] + direction * (half + costs.slippage_points * costs.point)
        assert signal.take_profit is not None  # noqa: S101 - BUY/SELL always have a target
        # keep the signal's distances, re-anchored on the actual fill
        sl = fill - direction * abs(signal.entry_price - signal.stop_loss)
        tp = fill + direction * abs(signal.take_profit - signal.entry_price)
        pos = PositionState(
            ticket=signal.signal_id,
            direction=direction,
            lots=signal.position_size or 0.0,
            entry=fill,
            initial_sl=sl,
            sl=sl,
            tp=tp,
            opened_at=opens[start],
        )
        risk = pos.risk
        gov.record_open(signal.signal_id, decided_at, "ANY", signal.risk_pct or 0.25)
        mfe = mae = 0.0
        exit_i = start
        exit_price = close_px[start]
        reason = "END_OF_DATA"
        for j in range(start, len(opens)):
            now = opens[j] + timedelta(minutes=5)
            ctx = ManagerContext(
                now=now,
                bar_high=float(highs[j]),
                bar_low=float(lows[j]),
                last_price=float(close_px[j]),
                atr=signal.atr,
                highest_since_entry=float(np.max(highs[start : j + 1])),
                lowest_since_entry=float(np.min(lows[start : j + 1])),
                spread_points=float(spreads[j]),
            )
            fav = (highs[j] - fill) if direction > 0 else (fill - lows[j])
            adv = (fill - lows[j]) if direction > 0 else (highs[j] - fill)
            mfe, mae = max(mfe, fav / risk), max(mae, adv / risk)
            action = evaluate(pos, ctx, manager)
            if action.kind == "CLOSE":
                exit_i, reason = j, action.reason
                if reason == "STOP_LOSS":
                    exit_price = pos.sl - direction * costs.slippage_points * costs.point
                elif reason == "TAKE_PROFIT":
                    exit_price = pos.tp
                else:
                    exit_price = float(close_px[j])
                break
            pos = apply(pos, action)
            exit_i = j
            exit_price = float(close_px[j])
        gross = direction * (exit_price - fill) / risk
        exit_half = spreads[exit_i] * costs.spread_multiplier * costs.point / 2
        net_price = direction * (exit_price - direction * exit_half - fill)
        r_net = net_price / risk
        exit_time = opens[exit_i] + timedelta(minutes=5)
        trades.append(
            ReplayTrade(
                signal_id=signal.signal_id,
                direction=direction,
                decided_at=decided_at,
                entry_time=opens[start],
                entry=float(fill),
                stop_loss=float(sl),
                take_profit=float(tp),
                exit_time=exit_time,
                exit_price=float(exit_price),
                exit_reason=reason,
                r_gross=float(gross),
                r_net=float(r_net),
                mfe_r=float(mfe),
                mae_r=float(mae),
                bars=exit_i - start + 1,
            )
        )
        gov.record_close(signal.signal_id, exit_time, r_net)
        busy_until = exit_time
    return trades


def summarise(trades: list[ReplayTrade], days: float) -> dict[str, float | int | None]:
    """Frequency, payoff and distribution of the simulated trades (a sanity check, not evidence)."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "per_day": 0.0, "mean_r_net": None, "mean_r_gross": None}
    net = np.array([t.r_net for t in trades])
    gross = np.array([t.r_gross for t in trades])
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    return {
        "trades": n,
        "per_day": n / days if days > 0 else None,
        "mean_r_net": float(net.mean()),
        "mean_r_gross": float(gross.mean()),
        "win_rate": float((net > 0).mean()),
        "worst_r": float(net.min()),
        "best_r": float(net.max()),
        "mean_mfe_r": float(np.mean([t.mfe_r for t in trades])),
        "mean_mae_r": float(np.mean([t.mae_r for t in trades])),
        **{f"exit_{k.lower()}": v for k, v in reasons.items()},
    }
